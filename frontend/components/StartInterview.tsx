"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { type InterviewMode, startInterview } from "@/lib/api";

export const MODE_LABELS: Record<InterviewMode, string> = {
  ai_leads: "AI leads",
  ai_asks_first: "AI asks first",
  researcher_leads: "Researcher leads",
};

export function StartInterview({ materialId }: { materialId: string }) {
  const router = useRouter();
  const [mode, setMode] = useState<InterviewMode>("ai_asks_first");
  const [minutes, setMinutes] = useState(45);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      const interview = await startInterview(materialId, mode, minutes);
      router.push(`/interviews/${interview.id}`);
    } catch {
      setError("Confirm at least one moment before starting an interview.");
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-3 rounded-lg border bg-white p-4"
    >
      <label className="flex flex-col gap-1 text-sm font-medium">
        Who leads
        <select
          value={mode}
          onChange={(event) => setMode(event.target.value as InterviewMode)}
          className="rounded-md border px-3 py-2 font-normal"
        >
          {Object.entries(MODE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium">
        Minutes
        <input
          type="number"
          min={1}
          max={240}
          value={minutes}
          onChange={(event) => setMinutes(Number(event.target.value))}
          className="w-24 rounded-md border px-3 py-2 font-normal"
        />
      </label>
      <button
        type="submit"
        className="rounded-md bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800"
      >
        Start interview
      </button>
      {error && (
        <p role="alert" className="w-full text-sm text-red-700">
          {error}
        </p>
      )}
    </form>
  );
}
