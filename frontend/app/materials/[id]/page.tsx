"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { MomentsPanel } from "@/components/MomentsPanel";
import { getMaterial, type MaterialDetail, materialFileUrl } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";

export default function MaterialPage() {
  const { id } = useParams<{ id: string }>();
  const [material, setMaterial] = useState<MaterialDetail | null>(null);
  const [positionMs, setPositionMs] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const player = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    getMaterial(id)
      .then(setMaterial)
      .catch(() => setError("Could not load this recording."));
  }, [id]);

  function seekTo(ms: number) {
    if (!player.current) return;
    player.current.currentTime = ms / 1000;
    void player.current.play();
  }

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      </main>
    );
  }

  if (!material) return null;

  const isVideo = material.content_type.startsWith("video/");

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-6 py-12">
      <div>
        <Link href={`/studies/${material.study_id}`} className="text-sm text-blue-700 hover:underline">
          Back to study
        </Link>
        <h1 className="mt-2 break-words text-2xl font-semibold">{material.filename}</h1>
      </div>

      {/* A video element plays audio files too, so one player covers both. */}
      <video
        ref={player}
        src={materialFileUrl(material.id)}
        controls
        onTimeUpdate={(event) => setPositionMs(event.currentTarget.currentTime * 1000)}
        className={isVideo ? "w-full rounded-lg bg-black" : "h-12 w-full"}
      />

      {material.status === "failed" && (
        <p role="alert" className="text-sm text-red-700">
          Transcription failed: {material.error}
        </p>
      )}

      {material.status === "ready" && (
        <MomentsPanel materialId={material.id} positionMs={positionMs} onSeek={seekTo} />
      )}

      <section className="flex flex-col gap-2">
        <h2 className="font-semibold">Transcript</h2>
        {material.segments.length === 0 && material.status !== "failed" && (
          <p className="text-sm text-stone-500">No transcript yet.</p>
        )}
        <ol className="flex flex-col gap-1">
          {material.segments.map((segment) => {
            const active = positionMs >= segment.start_ms && positionMs < segment.end_ms;
            return (
              <li key={segment.position}>
                <button
                  type="button"
                  onClick={() => seekTo(segment.start_ms)}
                  className={`flex w-full gap-3 rounded-md px-3 py-2 text-left hover:bg-stone-100 ${
                    active ? "bg-blue-50" : ""
                  }`}
                >
                  <span className="w-12 shrink-0 font-mono text-sm text-stone-500">
                    {formatTimestamp(segment.start_ms)}
                  </span>
                  <span className="w-20 shrink-0 text-sm font-semibold">{segment.speaker}</span>
                  <span className="text-sm">{segment.text}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </section>
    </main>
  );
}
