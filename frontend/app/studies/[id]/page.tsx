"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { getStudy, listMaterials, type Material, type Study, uploadMaterial } from "@/lib/api";
import { formatSize } from "@/lib/format";

const STATUS_STYLE: Record<Material["status"], string> = {
  uploaded: "bg-stone-100 text-stone-700",
  transcribing: "bg-amber-100 text-amber-900",
  ready: "bg-blue-100 text-blue-900",
  failed: "bg-red-100 text-red-800",
};

export default function StudyPage() {
  const { id } = useParams<{ id: string }>();
  const [study, setStudy] = useState<Study | null>(null);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([getStudy(id), listMaterials(id)])
      .then(([loadedStudy, loadedMaterials]) => {
        setStudy(loadedStudy);
        setMaterials(loadedMaterials);
      })
      .catch(() => setError("Could not load this study."));
  }, [id]);

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const material = await uploadMaterial(id, file);
      setMaterials((current) => [material, ...current]);
      if (fileInput.current) fileInput.current.value = "";
    } catch {
      setError("Upload failed. Use an audio or video file.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-8 px-6 py-12">
      <div>
        <Link href="/" className="text-sm text-blue-700 hover:underline">
          All studies
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">{study?.title ?? "Study"}</h1>
        {study?.research_questions && (
          <p className="mt-1 text-sm text-stone-600">{study.research_questions}</p>
        )}
      </div>

      <form onSubmit={handleUpload} className="flex flex-col gap-3 rounded-lg border bg-white p-5">
        <label className="flex flex-col gap-1 text-sm font-medium">
          Add a recording
          <input
            ref={fileInput}
            type="file"
            accept="audio/*,video/*"
            required
            className="rounded-md border px-3 py-2 font-normal"
          />
        </label>
        <button
          type="submit"
          disabled={uploading}
          className="self-start rounded-md bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
        >
          {uploading ? "Uploading and transcribing…" : "Upload"}
        </button>
      </form>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="font-semibold">Materials</h2>
        {materials.length === 0 && (
          <p className="text-sm text-stone-500">No recordings yet.</p>
        )}
        <ul className="flex flex-col gap-3">
          {materials.map((material) => (
            <li
              key={material.id}
              className="flex items-center justify-between gap-4 rounded-lg border bg-white p-4"
            >
              <div className="min-w-0">
                <Link
                  href={`/materials/${material.id}`}
                  className="block truncate font-medium hover:underline"
                >
                  {material.filename}
                </Link>
                <p className="text-xs text-stone-500">{formatSize(material.size_bytes)}</p>
              </div>
              <span
                className={`rounded px-2 py-1 text-xs font-semibold ${STATUS_STYLE[material.status]}`}
              >
                {material.status}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
