from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import Clock, as_utc
from app.interview import harness
from app.interview.policy import FollowUpPolicy
from app.models import Interview, InterviewEvent, InterviewTurn, Moment

MODES = ("ai_leads", "ai_asks_first", "researcher_leads")


class InvalidAction(Exception):
    """The action does not make sense in the interview's current state."""


@dataclass
class Decision:
    follow_up: bool
    reason: str
    question: str | None = None
    checks: dict[str, Any] = field(default_factory=dict)


class InterviewEngine:
    """Moves one interview forward, one action at a time.

    Every public method is a single action from the participant or the
    researcher. Each one checks that it is allowed in the current state,
    updates the interview, and appends events describing what was decided
    and why. Time comes from the injected clock, so a run is reproducible.
    """

    def __init__(
        self, db: Session, interview: Interview, policy: FollowUpPolicy, clock: Clock
    ) -> None:
        self.db = db
        self.interview = interview
        self.policy = policy
        self.clock = clock
        self._moments: list[Moment] | None = None

    # --- actions -----------------------------------------------------------

    def start(self) -> None:
        interview = self.interview
        interview.started_at = self.clock.now()
        self._log(
            "started",
            mode=interview.mode,
            budget_seconds=interview.budget_seconds,
            moments=len(self.moments),
        )
        self._open_moment()

    def answer(self, text: str) -> None:
        self._require("awaiting_answer")
        self._add_turn("participant", text)
        self._log("answer_received", words=len(text.split()))

        decision = self._decide(text)
        self._log(
            "followup_decided",
            decision="follow_up" if decision.follow_up else "move_on",
            reason=decision.reason,
            question=decision.question,
            **decision.checks,
        )

        if decision.follow_up and decision.question:
            self._deliver(decision.question, "followup")
        elif self.interview.mode == "researcher_leads":
            # The AI only advises here. Moving on is the researcher's call.
            self.interview.state = "researcher_turn"
        elif decision.reason == "time_up":
            self._close_moment("time_up")
            self._finish("time_up")
        else:
            self._close_moment(decision.reason)
            self._open_moment()

    def approve(self, text: str | None = None) -> None:
        self._require("awaiting_approval")
        proposed = self.interview.pending_text or ""
        question = text.strip() if text and text.strip() else proposed
        edited = question != proposed
        self._log("question_approved", edited=edited, before=proposed, after=question)
        self._ask("ai", question, self.interview.pending_kind or "followup")

    def skip(self) -> None:
        self._require("awaiting_approval")
        self._log(
            "question_skipped",
            kind=self.interview.pending_kind,
            question=self.interview.pending_text,
        )
        self._close_moment("skipped_by_researcher")
        self._open_moment()

    def expire(self) -> None:
        """Approval did not come in time, so the AI stays silent."""
        self._require("awaiting_approval")
        self._log("approval_timed_out", question=self.interview.pending_text)
        self._clear_unsaid()
        self.interview.state = "researcher_turn"

    def say(self, text: str) -> None:
        """The researcher asks their own question."""
        self._require("awaiting_approval", "researcher_turn")
        if self.interview.pending_text:
            self._log("question_replaced", question=self.interview.pending_text)
        self._ask("researcher", text, "researcher")

    def next_moment(self) -> None:
        self._require("awaiting_answer", "awaiting_approval", "researcher_turn")
        self._close_moment("advanced_by_researcher")
        self._open_moment()

    def set_mode(self, mode: str) -> None:
        self._require("awaiting_answer", "awaiting_approval", "researcher_turn")
        interview = self.interview
        if mode == interview.mode:
            return
        self._log("mode_changed", before=interview.mode, after=mode)
        unsaid = interview.pending_text or interview.suggestion_text
        kind = interview.pending_kind or "followup"
        interview.mode = mode
        if unsaid:
            # Re-deliver the question the AI was holding under the new rules.
            self._deliver(unsaid, kind)

    def end(self) -> None:
        self._require("awaiting_answer", "awaiting_approval", "researcher_turn")
        self._close_moment("ended_by_researcher")
        self._finish("ended_by_researcher")

    # --- timing ------------------------------------------------------------

    def elapsed_seconds(self) -> float:
        interview = self.interview
        end = interview.finished_at or self.clock.now()
        return (as_utc(end) - as_utc(interview.started_at)).total_seconds()

    def remaining_seconds(self) -> float:
        return max(0.0, self.interview.budget_seconds - self.elapsed_seconds())

    def moment_elapsed_seconds(self) -> float:
        started = self.interview.moment_started_at
        if started is None:
            return 0.0
        return (as_utc(self.clock.now()) - as_utc(started)).total_seconds()

    @property
    def moments(self) -> list[Moment]:
        if self._moments is None:
            stmt = (
                select(Moment)
                .where(
                    Moment.material_id == self.interview.material_id,
                    Moment.status == "confirmed",
                )
                .order_by(Moment.timestamp_ms, Moment.id)
            )
            self._moments = list(self.db.scalars(stmt))
        return self._moments

    def current_moment(self) -> Moment | None:
        index = self.interview.moment_index
        if self.interview.state == "finished" or index >= len(self.moments):
            return None
        return self.moments[index]

    # --- internals ---------------------------------------------------------

    def _decide(self, answer: str) -> Decision:
        interview = self.interview
        checks: dict[str, Any] = {
            "followups_used": interview.followups_used,
            "max_followups": interview.max_followups,
            "moment_seconds": round(self.moment_elapsed_seconds()),
            "moment_allowance_seconds": interview.moment_allowance_seconds,
            "remaining_seconds": round(self.remaining_seconds()),
        }

        if self.remaining_seconds() <= 0:
            return Decision(False, "time_up", checks=checks)
        if interview.followups_used >= interview.max_followups:
            return Decision(False, "followup_limit_reached", checks=checks)
        if self.moment_elapsed_seconds() >= interview.moment_allowance_seconds:
            return Decision(False, "moment_time_used", checks=checks)

        moment = self.current_moment()
        proposal = self.policy.propose(answer, moment.question if moment else "")
        checks["policy_reason"] = proposal.reason
        if proposal.question is None:
            return Decision(False, "nothing_to_follow_up", checks=checks)

        question = proposal.question
        leading = harness.find_leading_phrase(question)
        if leading:
            checks["blocked_question"] = question
            checks["leading_phrase"] = leading
            question = harness.NEUTRAL_FOLLOWUP

        if self._already_asked(question):
            checks["repeated_question"] = question
            return Decision(False, "would_repeat_question", checks=checks)

        return Decision(True, proposal.reason, question=question, checks=checks)

    def _already_asked(self, question: str) -> bool:
        asked = {
            harness.normalize(turn.text)
            for turn in self.interview.turns
            if turn.speaker != "participant"
        }
        return harness.normalize(question) in asked

    def _open_moment(self) -> None:
        interview = self.interview
        if interview.moment_index >= len(self.moments):
            self._finish("completed")
            return
        remaining = self.remaining_seconds()
        if remaining <= 0:
            self._finish("time_up")
            return

        moment = self.moments[interview.moment_index]
        interview.followups_used = 0
        interview.moment_started_at = self.clock.now()
        interview.moment_allowance_seconds = harness.moment_allowance(
            remaining, len(self.moments) - interview.moment_index
        )
        self._log(
            "moment_opened",
            moment_id=moment.id,
            timestamp_ms=moment.timestamp_ms,
            allowance_seconds=interview.moment_allowance_seconds,
        )
        self._deliver(moment.question, "moment")

    def _close_moment(self, reason: str) -> None:
        moment = self.current_moment()
        if moment is None:
            return
        self._log(
            "moment_closed",
            moment_id=moment.id,
            reason=reason,
            seconds=round(self.moment_elapsed_seconds()),
            followups_used=self.interview.followups_used,
        )
        self._clear_unsaid()
        self.interview.moment_index += 1

    def _deliver(self, question: str, kind: str) -> None:
        """Hand a question to whoever the current mode says should speak."""
        interview = self.interview
        self._clear_unsaid()
        if interview.mode == "ai_leads":
            self._ask("ai", question, kind)
        elif interview.mode == "ai_asks_first":
            interview.pending_text = question
            interview.pending_kind = kind
            interview.state = "awaiting_approval"
            self._log("question_proposed", kind=kind, question=question)
        else:
            interview.suggestion_text = question
            interview.pending_kind = kind
            interview.state = "researcher_turn"
            self._log("question_suggested", kind=kind, question=question)

    def _ask(self, speaker: str, question: str, kind: str) -> None:
        self._add_turn(speaker, question)
        if speaker == "ai" and kind == "followup":
            self.interview.followups_used += 1
        self._clear_unsaid()
        self.interview.state = "awaiting_answer"
        self._log("question_asked", speaker=speaker, kind=kind, question=question)

    def _finish(self, reason: str) -> None:
        interview = self.interview
        skipped = [m.id for m in self.moments[interview.moment_index :]]
        self._clear_unsaid()
        interview.state = "finished"
        interview.finished_at = self.clock.now()
        interview.finished_reason = reason
        self._log(
            "finished",
            reason=reason,
            moments_covered=interview.moment_index,
            moments_skipped=skipped,
            seconds=round(self.elapsed_seconds()),
        )

    def _clear_unsaid(self) -> None:
        self.interview.pending_text = None
        self.interview.suggestion_text = None
        self.interview.pending_kind = None

    def _require(self, *states: str) -> None:
        if self.interview.state not in states:
            raise InvalidAction(f"Not allowed while the interview is {self.interview.state}")

    def _add_turn(self, speaker: str, text: str) -> None:
        moment = self.current_moment()
        self.interview.turns.append(
            InterviewTurn(
                position=len(self.interview.turns),
                speaker=speaker,
                text=text,
                moment_id=moment.id if moment else None,
                created_at=self.clock.now(),
            )
        )

    def _log(self, type_: str, **detail: Any) -> None:
        self.interview.events.append(
            InterviewEvent(
                position=len(self.interview.events),
                type=type_,
                detail=detail,
                created_at=self.clock.now(),
            )
        )
