"use client";

import { type FormEvent, useEffect, useState } from "react";
import { createStudy, listStudies, type Study } from "@/lib/api";

export default function StudiesPage() {
  const [studies, setStudies] = useState<Study[]>([]);
  const [title, setTitle] = useState("");
  const [questions, setQuestions] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listStudies()
      .then(setStudies)
      .catch(() => setError("Could not reach the API. Is the backend running?"));
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      const study = await createStudy(title.trim(), questions.trim());
      setStudies((current) => [study, ...current]);
      setTitle("");
      setQuestions("");
      setError(null);
    } catch {
      setError("Could not create the study.");
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-8 px-6 py-12">
      <h1 className="text-2xl font-semibold">Studies</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3 rounded-lg border bg-white p-5">
        <label className="flex flex-col gap-1 text-sm font-medium">
          Title
          <input
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="rounded-md border px-3 py-2 font-normal"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Research questions
          <textarea
            rows={3}
            value={questions}
            onChange={(event) => setQuestions(event.target.value)}
            className="rounded-md border px-3 py-2 font-normal"
          />
        </label>
        <button
          type="submit"
          className="self-start rounded-md bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800"
        >
          Create study
        </button>
      </form>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      <ul className="flex flex-col gap-3">
        {studies.map((study) => (
          <li key={study.id} className="rounded-lg border bg-white p-5">
            <h2 className="font-semibold">{study.title}</h2>
            {study.research_questions && (
              <p className="mt-1 text-sm text-stone-600">{study.research_questions}</p>
            )}
            <p className="mt-2 text-xs text-stone-500">
              {study.participants.length} participant{study.participants.length === 1 ? "" : "s"}
            </p>
          </li>
        ))}
        {studies.length === 0 && !error && (
          <li className="text-sm text-stone-500">No studies yet. Create the first one above.</li>
        )}
      </ul>
    </main>
  );
}
