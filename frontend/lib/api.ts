const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Participant = { id: string; label: string; created_at: string };

export type Study = {
  id: string;
  title: string;
  research_questions: string;
  created_at: string;
  participants: Participant[];
};

export type MaterialStatus = "uploaded" | "transcribing" | "ready" | "failed";

export type Material = {
  id: string;
  study_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: MaterialStatus;
  error: string | null;
  created_at: string;
};

export type Segment = {
  position: number;
  speaker: string;
  start_ms: number;
  end_ms: number;
  text: string;
};

export type MaterialDetail = Material & { segments: Segment[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type Moment = {
  id: string;
  material_id: string;
  timestamp_ms: number;
  reason: string;
  question: string;
  source: "ai" | "researcher";
  status: "candidate" | "confirmed";
  created_at: string;
};

function sendJson<T>(method: string, path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const listStudies = () => request<Study[]>("/studies");

export const getStudy = (id: string) => request<Study>(`/studies/${id}`);

export const createStudy = (title: string, researchQuestions: string) =>
  sendJson<Study>("POST", "/studies", { title, research_questions: researchQuestions });

export const listMaterials = (studyId: string) =>
  request<Material[]>(`/studies/${studyId}/materials`);

export const getMaterial = (id: string) => request<MaterialDetail>(`/materials/${id}`);

export function uploadMaterial(studyId: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  return request<MaterialDetail>(`/studies/${studyId}/materials`, { method: "POST", body });
}

export const materialFileUrl = (id: string) => `${BASE_URL}/materials/${id}/file`;

export const listMoments = (materialId: string) =>
  request<Moment[]>(`/materials/${materialId}/moments`);

export const suggestMoments = (materialId: string) =>
  sendJson<Moment[]>("POST", `/materials/${materialId}/moments/suggest`);

export const addMoment = (materialId: string, timestampMs: number, question: string) =>
  sendJson<Moment>("POST", `/materials/${materialId}/moments`, {
    timestamp_ms: timestampMs,
    question,
  });

export const updateMoment = (
  id: string,
  changes: { status?: "confirmed" | "removed"; question?: string },
) => sendJson<Moment>("PATCH", `/moments/${id}`, changes);
