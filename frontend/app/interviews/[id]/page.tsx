"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ControlPanel } from "@/components/ControlPanel";
import {
  getInterview,
  type Interview,
  type InterviewAction,
  interviewAction,
  materialFileUrl,
} from "@/lib/api";

const SPEAKERS = { ai: "AI", researcher: "Researcher", participant: "Participant" };

export default function InterviewPage() {
  const { id } = useParams<{ id: string }>();
  const [interview, setInterview] = useState<Interview | null>(null);
  const [loadedAt, setLoadedAt] = useState(0);
  const [now, setNow] = useState(0);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const player = useRef<HTMLVideoElement>(null);

  const receive = useCallback((next: Interview) => {
    setInterview(next);
    setLoadedAt(Date.now());
    setNow(Date.now());
  }, []);

  useEffect(() => {
    getInterview(id)
      .then(receive)
      .catch(() => setError("Could not load this interview."));
  }, [id, receive]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Park the recording on the moment being discussed.
  const momentMs = interview?.current_moment?.timestamp_ms;
  useEffect(() => {
    if (player.current && momentMs !== undefined) {
      player.current.pause();
      player.current.currentTime = momentMs / 1000;
    }
  }, [momentMs]);

  const act = useCallback(
    async (action: InterviewAction, body?: object) => {
      setBusy(true);
      setError(null);
      try {
        receive(await interviewAction(id, action, body));
      } catch {
        setError("That action is not available right now.");
      } finally {
        setBusy(false);
      }
    },
    [id, receive],
  );

  async function handleAnswer(event: FormEvent) {
    event.preventDefault();
    const text = answer.trim();
    if (!text) return;
    setAnswer("");
    await act("answer", { text });
  }

  if (!interview) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12 text-sm">
        {error ? <p role="alert">{error}</p> : null}
      </main>
    );
  }

  const finished = interview.state === "finished";
  const elapsed = finished
    ? interview.elapsed_seconds
    : interview.elapsed_seconds + Math.max(0, now - loadedAt) / 1000;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-10">
      <div>
        <Link
          href={`/materials/${interview.material_id}`}
          className="text-sm text-blue-700 hover:underline"
        >
          Back to recording
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Interview</h1>
      </div>

      <div className="flex flex-wrap gap-6">
        <section className="flex min-w-0 flex-[1_1_480px] flex-col gap-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-900">
            Shared with the participant
          </p>
          <video
            ref={player}
            src={materialFileUrl(interview.material_id)}
            controls
            className="h-12 w-full"
          />

          <div className="flex flex-col gap-3 rounded-lg border bg-white p-4">
            <h2 className="text-sm font-semibold">Conversation</h2>
            {interview.turns.length === 0 && (
              <p className="text-sm text-stone-500">Nothing has been said yet.</p>
            )}
            <ol className="flex flex-col gap-3">
              {interview.turns.map((turn) => (
                <li key={turn.position} className="flex gap-3 text-sm">
                  <span
                    className={`w-24 shrink-0 font-semibold ${
                      turn.speaker === "participant" ? "" : "text-blue-800"
                    }`}
                  >
                    {SPEAKERS[turn.speaker]}
                  </span>
                  <span>{turn.text}</span>
                </li>
              ))}
            </ol>

            {interview.state === "awaiting_answer" && (
              <form onSubmit={handleAnswer} className="flex flex-col gap-2 border-t pt-3">
                <label className="flex flex-col gap-1 text-sm font-medium">
                  Participant&apos;s answer
                  <textarea
                    rows={3}
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    className="rounded-md border px-3 py-2 font-normal"
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy || !answer.trim()}
                  className="self-start rounded-md bg-stone-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Send answer
                </button>
              </form>
            )}
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
        </section>

        <div className="flex-[1_1_320px]">
          <ControlPanel interview={interview} elapsed={elapsed} busy={busy} onAction={act} />
        </div>
      </div>
    </main>
  );
}
