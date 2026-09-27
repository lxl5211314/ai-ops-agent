const BASE = "/api/v1";

export class ApiError extends Error {
  code: string;
  detail: unknown;
  constructor(code: string, message: string, detail?: unknown) {
    super(message);
    this.code = code;
    this.detail = detail;
  }
}

export async function request<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers:
      options.body instanceof FormData
        ? undefined
        : { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (res.status === 204) return undefined as T;
  let payload: any = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }
  if (!res.ok) {
    const err = payload?.error;
    throw new ApiError(err?.code || "INTERNAL", err?.message || `请求失败 (${res.status})`, err?.detail);
  }
  return payload as T;
}

export const api = {
  createConversation: (title?: string) =>
    request<{ id: string }>("/conversations", { method: "POST", body: JSON.stringify({ title }) }),
  listConversations: () => request<any[]>("/conversations"),
  getConversation: (id: string) => request<any>(`/conversations/${id}`),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
  postMessage: (cid: string, content: string) =>
    request<{ message_id: string; stream_url: string }>(`/conversations/${cid}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  listFolders: () => request<any[]>("/folders"),
  createFolder: (name: string) =>
    request<any>("/folders", { method: "POST", body: JSON.stringify({ name }) }),
  deleteFolder: (id: string) => request<void>(`/folders/${id}`, { method: "DELETE" }),

  listProjects: () => request<any[]>("/projects"),
  getProject: (id: string) => request<any>(`/projects/${id}`),
  getProjectFiles: (id: string, page = 1, size = 50) =>
    request<any[]>(`/projects/${id}/files?page=${page}&size=${size}`),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  connectPath: (folder_id: string, name: string, source_path: string) =>
    request<any>("/projects", {
      method: "POST",
      body: JSON.stringify({ folder_id, name, source_type: "path", source_path }),
    }),
  uploadProject: (folder_id: string, name: string, files: File[]) => {
    const form = new FormData();
    form.append("folder_id", folder_id);
    form.append("name", name);
    files.forEach((f) => form.append("files", f));
    return request<any>("/projects/upload", { method: "POST", body: form });
  },

  createAnalysis: (projectId: string, description: string) =>
    request<{ analysis_id: string; stream_url: string; deduplicated: boolean }>(
      `/projects/${projectId}/analyses`,
      { method: "POST", body: JSON.stringify({ description }) },
    ),
  getAnalysis: (id: string) => request<any>(`/analyses/${id}`),
  listAnalyses: (projectId: string) => request<any[]>(`/projects/${projectId}/analyses`),
  retryAnalysis: (id: string) =>
    request<any>(`/analyses/${id}/retry`, { method: "POST" }),

  listDocuments: () => request<any[]>("/kb/documents"),
  getDocument: (id: string) => request<any>(`/kb/documents/${id}`),
  deleteDocument: (id: string) => request<void>(`/kb/documents/${id}`, { method: "DELETE" }),
  uploadDocument: (category: string, file: File, title = "") => {
    const form = new FormData();
    form.append("category", category);
    form.append("title", title);
    form.append("file", file);
    return request<any>("/kb/documents", { method: "POST", body: form });
  },

  health: () => request<any>("/health"),
};

export { BASE };
