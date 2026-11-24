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

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const listStudies = () => request<Study[]>("/studies");

export const getStudy = (id: string) => request<Study>(`/studies/${id}`);

export const createStudy = (title: string, researchQuestions: string) =>
  postJson<Study>("/studies", { title, research_questions: researchQuestions });

export const listMaterials = (studyId: string) =>
  request<Material[]>(`/studies/${studyId}/materials`);

export const getMaterial = (id: string) => request<MaterialDetail>(`/materials/${id}`);

export function uploadMaterial(studyId: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  return request<MaterialDetail>(`/studies/${studyId}/materials`, { method: "POST", body });
}

export const materialFileUrl = (id: string) => `${BASE_URL}/materials/${id}/file`;
