import re
from dataclasses import dataclass
from typing import Protocol

from app.config import settings


@dataclass(frozen=True)
class FollowUpProposal:
    question: str | None
    reason: str


class FollowUpPolicy(Protocol):
    def propose(self, answer: str, moment_question: str) -> FollowUpProposal: ...


class KeywordFollowUpPolicy:
    """Rule-based stand-in for the model that will choose follow-ups.

    It asks for more when an answer is very short, or when the participant
    uses a word that points at reasoning or attention without spelling it out.
    """

    SHORT_ANSWER_WORDS = 8

    CUES = [
        (r"\b(worried|afraid|concerned|nervous)\b", "What were you concerned might happen?"),
        (r"\b(noticed|saw|realized|realised)\b", "What was it that caught your attention?"),
        (r"\b(decided|chose|choice)\b", "What other options did you consider?"),
        (
            r"\b(usually|normally|always)\b",
            "How was this time different from what usually happens?",
        ),
        (r"\bbecause\b", "What led you to that?"),
    ]

    def propose(self, answer: str, moment_question: str) -> FollowUpProposal:
        words = len(answer.split())
        if words < self.SHORT_ANSWER_WORDS:
            return FollowUpProposal(
                "Can you walk me through that in a bit more detail?",
                f"short answer ({words} words)",
            )
        for pattern, question in self.CUES:
            match = re.search(pattern, answer, re.IGNORECASE)
            if match:
                return FollowUpProposal(question, f'cue word "{match.group(0).lower()}"')
        return FollowUpProposal(None, "no cue found")


def get_followup_policy() -> FollowUpPolicy:
    if settings.followup_policy == "keyword":
        return KeywordFollowUpPolicy()
    raise ValueError(f"Unknown follow-up policy: {settings.followup_policy}")
