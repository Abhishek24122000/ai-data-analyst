import type { ChatResponse, ProfileResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function loadSampleDataset(): Promise<ProfileResponse> {
  const res = await fetch(`${API_BASE}/api/sample`);
  return handle<ProfileResponse>(res);
}

export async function uploadDataset(file: File): Promise<ProfileResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
  return handle<ProfileResponse>(res);
}

export async function sendChatMessage(
  sessionId: string,
  datasetId: string,
  message: string
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, dataset_id: datasetId, message }),
  });
  return handle<ChatResponse>(res);
}

export async function checkHealth(): Promise<{ status: string; llm_provider: string; llm_enabled: boolean }> {
  const res = await fetch(`${API_BASE}/api/health`);
  return handle(res);
}
