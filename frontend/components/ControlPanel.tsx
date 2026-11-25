"use client";

import { useEffect, useState } from "react";
import { MODE_LABELS } from "@/components/StartInterview";
import type { Interview, InterviewAction, InterviewMode } from "@/lib/api";
import { formatClock, formatTimestamp } from "@/lib/format";

const APPROVAL_SECONDS = 15;

const REASONS: Record<string, string> = {
  followup_limit_reached: "Follow-up limit reached for this moment",
  moment_time_used: "This moment has used its share of the time",
  nothing_to_follow_up: "Nothing in the answer called for a follow-up",
  would_repeat_question: "The follow-up would repeat an earlier question",
  time_up: "The time budget is used up",
};

type Props = {
  interview: Interview;
  elapsed: number;
  busy: boolean;
  onAction: (action: InterviewAction, body?: object) => void;
};

export function ControlPanel({ interview, elapsed, busy, onAction }: Props) {
  const finished = interview.state === "finished";
  const used = Math.min(100, (elapsed / interview.budget_seconds) * 100);
  const covered = Math.min(interview.moment_index, interview.moments_total);

  return (
    <aside className="flex flex-col gap-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">
        Researcher only
      </p>

      <section className="rounded-lg border bg-white p-4">
        <div className="flex items-baseline justify-between">
          <span className="font-semibold">
            {formatClock(elapsed)} / {formatClock(interview.budget_seconds)}
          </span>
          <span className="text-sm text-stone-600">
            {covered} of {interview.moments_total} moments
          </span>
        </div>
        <div
          role="img"
          aria-label={`${Math.round(used)}% of the time used`}
          className="mt-2 h-2 overflow-hidden rounded bg-stone-200"
        >
          <div className="h-2 bg-blue-700" style={{ width: `${used}%` }} />
        </div>
      </section>

      {!finished && (
        <div role="group" aria-label="Who leads" className="flex overflow-hidden rounded-md border">
          {(Object.keys(MODE_LABELS) as InterviewMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              aria-pressed={interview.mode === mode}
              disabled={busy}
              onClick={() => onAction("mode", { mode })}
              className={`flex-1 px-2 py-2 text-sm ${
                interview.mode === mode
                  ? "bg-blue-700 font-semibold text-white"
                  : "bg-white hover:bg-stone-100"
              }`}
            >
              {MODE_LABELS[mode]}
            </button>
          ))}
        </div>
      )}

      {interview.state === "awaiting_approval" && interview.pending_question && (
        <ApprovalCard
          key={interview.pending_question}
          question={interview.pending_question}
          busy={busy}
          onAction={onAction}
        />
      )}

      {interview.state === "researcher_turn" && (
        <ResearcherTurnCard
          key={interview.turns.length}
          suggestion={interview.suggested_question}
          busy={busy}
          onAction={onAction}
        />
      )}

      {interview.current_moment && (
        <section className="rounded-lg border bg-white p-4 text-sm">
          <h2 className="font-semibold">
            Moment {interview.moment_index + 1} · {formatTimestamp(interview.current_moment.timestamp_ms)}
          </h2>
          {interview.current_moment.reason && (
            <p className="mt-1 text-stone-600">{interview.current_moment.reason}</p>
          )}
          <dl className="mt-3 flex flex-col gap-1">
            <Row label="Follow-ups used">
              {interview.followups_used} of {interview.max_followups}
            </Row>
            <Row label="Time allowed for this moment">
              {formatClock(interview.moment_allowance_seconds)}
            </Row>
          </dl>
        </section>
      )}

      {interview.last_decision && (
        <section className="rounded-lg border bg-white p-4 text-sm">
          <h2 className="font-semibold">Last decision</h2>
          <p className="mt-1">
            {interview.last_decision.decision === "follow_up" ? "Follow up" : "Move on"}:{" "}
            {REASONS[String(interview.last_decision.reason)] ?? interview.last_decision.reason}
          </p>
          {interview.last_decision.blocked_question && (
            <p className="mt-2 text-amber-800">
              Blocked as leading: “{interview.last_decision.blocked_question}”
            </p>
          )}
        </section>
      )}

      {finished ? (
        <p className="rounded-lg border bg-white p-4 text-sm">
          Interview finished: {String(interview.finished_reason).replaceAll("_", " ")}.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => onAction("next")}
            className="rounded-md border px-3 py-2 text-sm hover:bg-stone-100"
          >
            Next moment
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onAction("end")}
            className="rounded-md border px-3 py-2 text-sm hover:bg-stone-100"
          >
            End interview
          </button>
        </div>
      )}
    </aside>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-stone-600">{label}</dt>
      <dd className="font-semibold">{children}</dd>
    </div>
  );
}

type CardProps = {
  busy: boolean;
  onAction: (action: InterviewAction, body?: object) => void;
};

function ApprovalCard({ question, busy, onAction }: CardProps & { question: string }) {
  const [draft, setDraft] = useState(question);
  const [secondsLeft, setSecondsLeft] = useState(APPROVAL_SECONDS);
  const editing = draft !== question;

  // The countdown stops once the researcher starts editing: they are clearly
  // engaged, and expiring under their hands would throw the edit away.
  useEffect(() => {
    if (editing) return;
    if (secondsLeft <= 0) {
      onAction("expire");
      return;
    }
    const timer = setTimeout(() => setSecondsLeft((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [editing, secondsLeft, onAction]);

  return (
    <section className="flex flex-col gap-3 rounded-lg border-2 border-blue-700 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">Approve this question?</h2>
        {!editing && (
          <span className="rounded bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-900">
            {secondsLeft} s left
          </span>
        )}
      </div>
      <label className="flex flex-col gap-1 text-xs font-medium text-stone-600">
        The AI will say this only if you approve
        <textarea
          rows={3}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          className="rounded-md border px-3 py-2 text-sm font-normal text-stone-900"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || !draft.trim()}
          onClick={() => onAction("approve", { text: draft })}
          className="rounded-md bg-blue-700 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-800"
        >
          {editing ? "Approve edited" : "Approve"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onAction("skip")}
          className="rounded-md border px-3 py-2 text-sm hover:bg-stone-100"
        >
          Skip
        </button>
        <button
          type="button"
          disabled={busy || !editing || !draft.trim()}
          onClick={() => onAction("say", { text: draft })}
          className="rounded-md border px-3 py-2 text-sm hover:bg-stone-100 disabled:opacity-50"
        >
          Ask it myself
        </button>
      </div>
    </section>
  );
}

function ResearcherTurnCard({
  suggestion,
  busy,
  onAction,
}: CardProps & { suggestion: string | null }) {
  const [draft, setDraft] = useState(suggestion ?? "");

  return (
    <section className="flex flex-col gap-3 rounded-lg border-2 border-blue-700 bg-white p-4">
      <h2 className="font-semibold">Your turn</h2>
      <label className="flex flex-col gap-1 text-xs font-medium text-stone-600">
        {suggestion ? "Suggested question, edit as you like" : "The AI has nothing to suggest"}
        <textarea
          rows={3}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type your question"
          className="rounded-md border px-3 py-2 text-sm font-normal text-stone-900"
        />
      </label>
      <button
        type="button"
        disabled={busy || !draft.trim()}
        onClick={() => onAction("say", { text: draft })}
        className="self-start rounded-md bg-blue-700 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-50"
      >
        Ask
      </button>
    </section>
  );
}
