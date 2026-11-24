const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Participant = { id: string; label: string; created_at: string };

export type Study = {
  id: string;
  title: string;
  research_questions: string;
  created_at: string;
  participants: Participant[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const listStudies = () => request<Study[]>("/studies");

export const createStudy = (title: string, researchQuestions: string) =>
  request<Study>("/studies", {
    method: "POST",
    body: JSON.stringify({ title, research_questions: researchQuestions }),
  });
