"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  addCoding,
  type Code,
  type Coding,
  type CodingSummary,
  codingsCsvUrl,
  getCodings,
  getInterview,
  getMaterial,
  listCodes,
  reviewCoding,
  runCoding,
} from "@/lib/api";

export default function CodingPage() {
  const { id } = useParams<{ id: string }>();
  const [summary, setSummary] = useState<CodingSummary | null>(null);
  const [codebook, setCodebook] = useState<Code[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => getCodings(id).then(setSummary), [id]);

  useEffect(() => {
    async function load() {
      const interview = await getInterview(id);
      const material = await getMaterial(interview.material_id);
      setCodebook(await listCodes(material.study_id));
      await refresh();
    }
    load().catch(() => setError("Could not load this interview."));
  }, [id, refresh]);

  async function run(action: () => Promise<unknown>, failure: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await refresh();
    } catch {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  const handleRun = () =>
    run(
      () => runCoding(id),
      "Coding needs a finished interview and at least one code in the codebook.",
    );

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-12">
      <div>
        <Link href={`/interviews/${id}`} className="text-sm text-blue-700 hover:underline">
          Back to interview
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Coding</h1>
        {summary && (
          <p className="mt-1 text-sm text-stone-600">
            {summary.needs_review === 0
              ? "Nothing is waiting for review."
              : `${summary.needs_review} coding${summary.needs_review === 1 ? "" : "s"} waiting for review.`}
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={handleRun}
          className="rounded-md bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
        >
          Suggest codes
        </button>
        <a
          href={codingsCsvUrl(id)}
          className="rounded-md border px-4 py-2 text-sm font-semibold hover:bg-stone-100"
        >
          Export accepted (CSV)
        </a>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      <ol className="flex flex-col gap-4">
        {summary?.turns.map((turn) => (
          <li key={turn.position} className="flex flex-col gap-3 rounded-lg border bg-white p-4">
            <p className="text-sm">{turn.text}</p>
            <ul className="flex flex-col gap-2">
              {turn.codings.map((coding) => (
                <CodingRow
                  key={coding.id}
                  coding={coding}
                  busy={busy}
                  onReview={(status) =>
                    run(() => reviewCoding(coding.id, status), "Could not save the review.")
                  }
                />
              ))}
            </ul>
            <AddCode
              codebook={codebook.filter(
                (code) =>
                  !turn.codings.some((c) => c.code_id === code.id && c.status === "accepted"),
              )}
              busy={busy}
              onAdd={(codeId) =>
                run(() => addCoding(id, turn.position, codeId), "Could not add the code.")
              }
            />
          </li>
        ))}
      </ol>
    </main>
  );
}

const STATUS_STYLE: Record<Coding["status"], string> = {
  accepted: "border-stone-400",
  needs_review: "border-dashed border-amber-600 bg-amber-50",
  rejected: "border-stone-200 text-stone-400 line-through",
};

function CodingRow({
  coding,
  busy,
  onReview,
}: {
  coding: Coding;
  busy: boolean;
  onReview: (status: "accepted" | "rejected") => void;
}) {
  return (
    <li className="flex flex-wrap items-center gap-2 text-sm">
      <span className={`rounded-md border px-2 py-1 ${STATUS_STYLE[coding.status]}`}>
        {coding.code_name}
      </span>
      <span className="text-xs text-stone-600">
        {coding.source === "ai"
          ? `${coding.status === "needs_review" ? "Uncertain" : "Suggested"} · ${Math.round(coding.confidence * 100)}%`
          : "Added by you"}
        {coding.rationale && ` · ${coding.rationale}`}
      </span>
      <span className="ml-auto flex gap-2">
        {coding.status !== "accepted" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onReview("accepted")}
            className="rounded-md border px-2 py-1 text-xs font-semibold hover:bg-stone-100"
          >
            Accept
          </button>
        )}
        {coding.status !== "rejected" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onReview("rejected")}
            className="rounded-md border px-2 py-1 text-xs hover:bg-stone-100"
          >
            Reject
          </button>
        )}
      </span>
    </li>
  );
}

function AddCode({
  codebook,
  busy,
  onAdd,
}: {
  codebook: Code[];
  busy: boolean;
  onAdd: (codeId: string) => void;
}) {
  if (codebook.length === 0) return null;
  return (
    <label className="flex items-center gap-2 text-xs text-stone-600">
      Add a code
      <select
        value=""
        disabled={busy}
        onChange={(event) => event.target.value && onAdd(event.target.value)}
        className="rounded-md border px-2 py-1 text-sm text-stone-900"
      >
        <option value="">Choose…</option>
        {codebook.map((code) => (
          <option key={code.id} value={code.id}>
            {code.name}
          </option>
        ))}
      </select>
    </label>
  );
}
