/**
 * FastAPI 백엔드 클라이언트
 * 브라우저: Next.js rewrite /backend/* → FastAPI
 * 서버:    BACKEND_URL 환경변수 직접 사용
 */

const BASE =
  typeof window !== "undefined"
    ? "/backend/api/v1"
    : `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/v1`;

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// -------------------------------------------------------------------------
// 세션 (대화 목록)
// -------------------------------------------------------------------------
export type Session = {
  id: string;
  title: string;
  summary: string | null;
  provider: string;
  model: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiResponse<T> = { success: boolean; data: T; error: null | object; meta: object };

export const sessionsApi = {
  list: (cursor?: string) =>
    request<ApiResponse<Session[]>>(
      `/sessions${cursor ? `?cursor=${cursor}&limit=30` : "?limit=30"}`
    ),

  create: (title = "New Chat", provider = "claude") =>
    request<ApiResponse<Session>>("/sessions", {
      method: "POST",
      body: JSON.stringify({ title, provider }),
    }),

  update: (id: string, data: { title?: string; system_prompt?: string }) =>
    request<ApiResponse<Session>>(`/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    request<ApiResponse<{ deleted: string }>>(`/sessions/${id}`, {
      method: "DELETE",
    }),

  messages: (id: string, cursor?: string) =>
    request<ApiResponse<object[]>>(
      `/sessions/${id}/messages${cursor ? `?cursor=${cursor}&limit=50` : "?limit=50"}`
    ),

  searchMessages: (id: string, query: string) =>
    request<ApiResponse<object[]>>(
      `/sessions/${id}/messages/search?q=${encodeURIComponent(query)}`
    ),
};

// -------------------------------------------------------------------------
// 파일
// -------------------------------------------------------------------------
export type UploadedFile = {
  id: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  chunk_count: number;
  parsed_text?: string;
  session_id: string | null;
  created_at: string;
  expires_at: string | null;
};

export const filesApi = {
  list: (sessionId?: string) =>
    request<ApiResponse<UploadedFile[]>>(
      `/files${sessionId ? `?session_id=${sessionId}` : ""}`
    ),

  get: (id: string) =>
    request<ApiResponse<UploadedFile & { parsed_text: string }>>(`/files/${id}`),

  delete: (id: string) =>
    request<ApiResponse<{ deleted: string }>>(`/files/${id}`, {
      method: "DELETE",
    }),
};
