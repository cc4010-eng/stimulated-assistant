"use client";

import { type FormEvent, useEffect, useState } from "react";
import { addCode, type Code, listCodes } from "@/lib/api";

export function Codebook({ studyId }: { studyId: string }) {
  const [codes, setCodes] = useState<Code[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCodes(studyId)
      .then(setCodes)
      .catch(() => setError("Could not load the codebook."));
  }, [studyId]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      const code = await addCode(studyId, name.trim(), description.trim());
      setCodes((current) => [...current, code].sort((a, b) => a.name.localeCompare(b.name)));
      setName("");
      setDescription("");
      setError(null);
    } catch {
      setError("Could not add the code. Is the name already in use?");
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-semibold">Codebook</h2>
      {codes.length === 0 && <p className="text-sm text-stone-500">No codes yet.</p>}
      <dl className="flex flex-col gap-2">
        {codes.map((code) => (
          <div key={code.id} className="rounded-lg border bg-white p-3 text-sm">
            <dt className="font-medium">{code.name}</dt>
            {code.description && <dd className="text-stone-600">{code.description}</dd>}
          </div>
        ))}
      </dl>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2 rounded-lg border bg-white p-4">
        <label className="flex flex-col gap-1 text-sm font-medium">
          Code name
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="rounded-md border px-3 py-2 font-normal"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Definition
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="rounded-md border px-3 py-2 font-normal"
          />
        </label>
        <button
          type="submit"
          className="self-start rounded-md border px-3 py-2 text-sm font-semibold hover:bg-stone-100"
        >
          Add code
        </button>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
      </form>
    </section>
  );
}
