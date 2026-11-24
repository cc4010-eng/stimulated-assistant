"use client";

import { type FormEvent, useEffect, useState } from "react";
import { addMoment, listMoments, type Moment, suggestMoments, updateMoment } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";

type Props = {
  materialId: string;
  positionMs: number;
  onSeek: (ms: number) => void;
};

export function MomentsPanel({ materialId, positionMs, onSeek }: Props) {
  const [moments, setMoments] = useState<Moment[]>([]);
  const [newQuestion, setNewQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMoments(materialId)
      .then(setMoments)
      .catch(() => setError("Could not load moments."));
  }, [materialId]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch {
      setError("That did not go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function replace(updated: Moment) {
    setMoments((current) => current.map((m) => (m.id === updated.id ? updated : m)));
  }

  const handleSuggest = () => run(async () => setMoments(await suggestMoments(materialId)));

  const handleAccept = (moment: Moment) =>
    run(async () => replace(await updateMoment(moment.id, { status: "confirmed" })));

  const handleRemove = (moment: Moment) =>
    run(async () => {
      await updateMoment(moment.id, { status: "removed" });
      setMoments((current) => current.filter((m) => m.id !== moment.id));
    });

  const handleQuestionEdit = (moment: Moment, question: string) => {
    const trimmed = question.trim();
    if (!trimmed || trimmed === moment.question) return;
    void run(async () => replace(await updateMoment(moment.id, { question: trimmed })));
  };

  function handleAdd(event: FormEvent) {
    event.preventDefault();
    const question = newQuestion.trim();
    if (!question) return;
    void run(async () => {
      const added = await addMoment(materialId, Math.round(positionMs), question);
      setMoments((current) =>
        [...current, added].sort((a, b) => a.timestamp_ms - b.timestamp_ms),
      );
      setNewQuestion("");
    });
  }

  const confirmed = moments.filter((m) => m.status === "confirmed").length;

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Moments to discuss</h2>
          <p className="text-xs text-stone-500">
            {confirmed} confirmed · {moments.length - confirmed} to review
          </p>
        </div>
        <button
          type="button"
          onClick={handleSuggest}
          disabled={busy}
          className="rounded-md border border-blue-700 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-60"
        >
          Suggest moments
        </button>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      <ul className="flex flex-col gap-3">
        {moments.map((moment) => (
          <li
            key={moment.id}
            className={`flex flex-col gap-2 rounded-lg border bg-white p-4 ${
              moment.status === "candidate" ? "border-amber-600" : ""
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => onSeek(moment.timestamp_ms)}
                className="font-mono text-sm font-semibold text-blue-700 hover:underline"
              >
                {formatTimestamp(moment.timestamp_ms)}
              </button>
              <span className="text-xs text-stone-600">
                {moment.source === "ai" ? "Suggested" : "Added by you"} ·{" "}
                {moment.status === "candidate" ? "to review" : "confirmed"}
              </span>
            </div>
            {moment.reason && <p className="text-sm text-stone-600">{moment.reason}</p>}
            <label className="flex flex-col gap-1 text-xs font-medium text-stone-600">
              Question
              <textarea
                key={moment.question}
                defaultValue={moment.question}
                rows={2}
                onBlur={(event) => handleQuestionEdit(moment, event.target.value)}
                className="rounded-md border px-3 py-2 text-sm font-normal text-stone-900"
              />
            </label>
            <div className="flex gap-2">
              {moment.status === "candidate" && (
                <button
                  type="button"
                  onClick={() => handleAccept(moment)}
                  disabled={busy}
                  className="rounded-md bg-blue-700 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
                >
                  Accept
                </button>
              )}
              <button
                type="button"
                onClick={() => handleRemove(moment)}
                disabled={busy}
                className="rounded-md border px-3 py-2 text-sm hover:bg-stone-100 disabled:opacity-60"
              >
                Remove
              </button>
            </div>
          </li>
        ))}
        {moments.length === 0 && (
          <li className="text-sm text-stone-500">
            No moments yet. Ask for suggestions, or add your own below.
          </li>
        )}
      </ul>

      <form onSubmit={handleAdd} className="flex flex-col gap-2 rounded-lg border bg-white p-4">
        <label className="flex flex-col gap-1 text-sm font-medium">
          Add a moment at {formatTimestamp(positionMs)}
          <input
            value={newQuestion}
            onChange={(event) => setNewQuestion(event.target.value)}
            placeholder="What do you want to ask here?"
            className="rounded-md border px-3 py-2 font-normal"
          />
        </label>
        <button
          type="submit"
          disabled={busy || !newQuestion.trim()}
          className="self-start rounded-md border px-3 py-2 text-sm font-semibold hover:bg-stone-100 disabled:opacity-60"
        >
          Add moment
        </button>
      </form>
    </section>
  );
}
