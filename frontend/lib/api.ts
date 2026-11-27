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

export type InterviewMode = "ai_leads" | "ai_asks_first" | "researcher_leads";

export type Turn = {
  position: number;
  speaker: "ai" | "researcher" | "participant";
  text: string;
  moment_id: string | null;
};

export type Interview = {
  id: string;
  material_id: string;
  mode: InterviewMode;
  state: "awaiting_answer" | "awaiting_approval" | "researcher_turn" | "finished";
  budget_seconds: number;
  elapsed_seconds: number;
  remaining_seconds: number;
  moments_total: number;
  moment_index: number;
  current_moment: Moment | null;
  moment_seconds: number;
  moment_allowance_seconds: number;
  followups_used: number;
  max_followups: number;
  pending_question: string | null;
  suggested_question: string | null;
  last_decision: Record<string, string | number | null> | null;
  finished_reason: string | null;
  turns: Turn[];
};

export type InterviewAction =
  | "answer"
  | "approve"
  | "skip"
  | "expire"
  | "say"
  | "next"
  | "mode"
  | "end";

export const startInterview = (materialId: string, mode: InterviewMode, budgetMinutes: number) =>
  sendJson<Interview>("POST", `/materials/${materialId}/interviews`, {
    mode,
    budget_minutes: budgetMinutes,
  });

export const getInterview = (id: string) => request<Interview>(`/interviews/${id}`);

export const interviewAction = (id: string, action: InterviewAction, body?: object) =>
  sendJson<Interview>("POST", `/interviews/${id}/${action}`, body);

export type Code = { id: string; name: string; description: string };

export type Coding = {
  id: string;
  turn_position: number;
  code_id: string;
  code_name: string;
  confidence: number;
  rationale: string;
  source: "ai" | "researcher";
  status: "accepted" | "needs_review" | "rejected";
};

export type CodedTurn = {
  position: number;
  text: string;
  moment_id: string | null;
  codings: Coding[];
};

export type CodingSummary = { interview_id: string; needs_review: number; turns: CodedTurn[] };

export const listCodes = (studyId: string) => request<Code[]>(`/studies/${studyId}/codes`);

export const addCode = (studyId: string, name: string, description: string) =>
  sendJson<Code>("POST", `/studies/${studyId}/codes`, { name, description });

export const getCodings = (interviewId: string) =>
  request<CodingSummary>(`/interviews/${interviewId}/codings`);

export const runCoding = (interviewId: string) =>
  sendJson<CodingSummary>("POST", `/interviews/${interviewId}/code`);

export const reviewCoding = (id: string, status: "accepted" | "rejected") =>
  sendJson<Coding>("PATCH", `/codings/${id}`, { status });

export const addCoding = (interviewId: string, turnPosition: number, codeId: string) =>
  sendJson<Coding>("POST", `/interviews/${interviewId}/codings`, {
    turn_position: turnPosition,
    code_id: codeId,
  });

export const codingsCsvUrl = (interviewId: string) =>
  `${BASE_URL}/interviews/${interviewId}/codings.csv`;
