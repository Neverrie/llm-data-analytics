export type User = {
  id: string;
  email: string;
  display_name: string;
  is_demo: boolean;
};

export type AuthResponse = {
  user: User;
  access_token: string;
  token_type: "bearer";
};

export type Chat = {
  id: string;
  title: string;
  kind: "lab3_chat" | "lab2_pipeline" | "general";
  dataset_name?: string | null;
  created_at: string;
  updated_at: string;
  archived: boolean;
};

export type ChatMessage = {
  id: string;
  chat_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  blocks: unknown[];
  metadata: Record<string, unknown>;
  created_at: string;
};

export type DatasetItem = {
  id: string;
  name: string;
  source: "built_in" | "upload";
  rows_count: number | null;
  columns_count: number | null;
  created_at: string;
  preview_available: boolean;
};

export type ArtifactItem = {
  id: string;
  kind: string;
  title: string;
  filename: string;
  path: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
  preview_url: string;
  download_url: string;
  metadata?: Record<string, unknown>;
};

const TOKEN_KEY = "workspace_access_token";

export function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "/api";
}

export function setAuthToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (!token) {
    window.localStorage.removeItem(TOKEN_KEY);
    return;
  }
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function getAuthToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(init.headers || {});
  headers.set("Accept", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `API error ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return (await response.text()) as T;
  }
  return (await response.json()) as T;
}

async function requestRaw(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getAuthToken();
  const headers = new Headers(init.headers || {});
  headers.set("Accept", "*/*");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });
}

export const api = {
  getHealth: <T = { status: string; service: string }>() => request<T>("/health"),

  demoLogin: () => request<AuthResponse>("/auth/demo-login", { method: "POST" }),
  login: (email: string, password: string) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    }),
  register: (email: string, password: string, display_name: string) =>
    request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name })
    }),
  me: () => request<User>("/auth/me"),

  getWorkspace: () => request<{ user: User; counts: { chats: number; datasets: number; artifacts: number }; recent_chats: Chat[]; recent_artifacts: ArtifactItem[] }>("/workspace"),

  listChats: (params?: { kind?: string; archived?: boolean }) => {
    const search = new URLSearchParams();
    if (params?.kind) search.set("kind", params.kind);
    if (typeof params?.archived === "boolean") search.set("archived", String(params.archived));
    const qs = search.toString() ? `?${search.toString()}` : "";
    return request<{ items: Chat[] }>(`/chats${qs}`);
  },
  createChat: (body: { title: string; kind: "lab3_chat" | "lab2_pipeline" | "general"; dataset_name?: string | null }) =>
    request<Chat>("/chats", { method: "POST", body: JSON.stringify(body) }),
  getChat: (chatId: string) => request<{ chat: Chat; messages: ChatMessage[] }>(`/chats/${chatId}`),
  addMessage: (chatId: string, body: { role: "user" | "assistant" | "system"; content: string; blocks?: unknown[]; metadata?: Record<string, unknown> }) =>
    request<ChatMessage>(`/chats/${chatId}/messages`, { method: "POST", body: JSON.stringify(body) }),
  updateChat: (chatId: string, body: { title?: string; archived?: boolean }) =>
    request<Chat>(`/chats/${chatId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteChat: (chatId: string) => request<Chat>(`/chats/${chatId}`, { method: "DELETE" }),

  listDatasets: () => request<{ items: DatasetItem[] }>("/datasets"),
  uploadDataset: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DatasetItem>("/datasets/upload", { method: "POST", body: form });
  },
  previewDataset: (datasetId: string, limit = 20) => request<{ columns: string[]; rows: Record<string, unknown>[] }>(`/datasets/${datasetId}/preview?limit=${limit}`),
  profileDataset: (datasetId: string) => request<{ rows_count: number; columns_count: number; columns: Array<{ name: string; dtype: string; missing_count: number; unique_count: number }> }>(`/datasets/${datasetId}/profile`),

  listArtifacts: (params?: { kind?: string; chat_id?: string }) => {
    const search = new URLSearchParams();
    if (params?.kind) search.set("kind", params.kind);
    if (params?.chat_id) search.set("chat_id", params.chat_id);
    const qs = search.toString() ? `?${search.toString()}` : "";
    return request<{ items: ArtifactItem[] }>(`/artifacts${qs}`);
  },
  getArtifact: (id: string) => request<ArtifactItem>(`/artifacts/${id}`),
  artifactPreviewUrl: (id: string) => `${getApiBaseUrl()}/artifacts/${id}/preview`,
  artifactDownloadUrl: (id: string) => `${getApiBaseUrl()}/artifacts/${id}/download`,
  fetchArtifactPreview: (id: string) => requestRaw(`/artifacts/${id}/preview`),
  fetchArtifactDownload: (id: string) => requestRaw(`/artifacts/${id}/download`),

  runLab2Pipeline: (body: { limit: number; min_score?: number | null; max_score?: number | null; process_all?: boolean; batch_size?: number }) =>
    request<any>("/lab2/run", { method: "POST", body: JSON.stringify(body) }),
  getLab2SampleData: (params: { limit?: number; min_score?: number | null; max_score?: number | null }) => {
    const search = new URLSearchParams();
    if (typeof params.limit === "number") search.set("limit", String(params.limit));
    if (typeof params.min_score === "number") search.set("min_score", String(params.min_score));
    if (typeof params.max_score === "number") search.set("max_score", String(params.max_score));
    return request<any>(`/lab2/sample-data?${search.toString()}`);
  },
  askLab3Agent: (body: { dataset_name: string; question: string; analysis_mode?: "code_interpreter" | "fast" | "balanced" | "full"; include_history?: boolean; max_code_steps?: number; max_tool_calls?: number; use_critic?: boolean; column_overrides?: Record<string, string | null> }) =>
    request<any>("/lab3/ask", { method: "POST", body: JSON.stringify(body) }),
  getLab3Status: () => request<any>("/lab3/status")
};

