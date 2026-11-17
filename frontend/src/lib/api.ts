import type {
  AuditLogItem,
  AuthTokenResponse,
  DocType,
  DocumentSection,
  LikeStatus,
  MonitoringMetrics,
  OutlineSuggestion,
  ProjectDetail,
  ProjectSummary,
  ProjectTimeline,
  ReconstructionResult,
  SectionComment,
  SectionRevision,
  ThemeConfig,
  User,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000/api/v1";

const ACCESS_KEY = "doccraft_access_token";
const REFRESH_KEY = "doccraft_refresh_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getStoredTokens(): { accessToken: string | null; refreshToken: string | null } {
  if (typeof window === "undefined") {
    return { accessToken: null, refreshToken: null };
  }
  return {
    accessToken: window.localStorage.getItem(ACCESS_KEY),
    refreshToken: window.localStorage.getItem(REFRESH_KEY),
  };
}

export function setStoredTokens(accessToken: string, refreshToken: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_KEY, accessToken);
  window.localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearStoredTokens(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

async function request<T>(path: string, init: RequestInit = {}, retryRefresh = true): Promise<T> {
  const { accessToken, refreshToken } = getStoredTokens();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (resp.status === 401 && retryRefresh && refreshToken && !path.includes("/auth/")) {
    const refreshResp = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (refreshResp.ok) {
      const data = (await refreshResp.json()) as AuthTokenResponse;
      setStoredTokens(data.access_token, data.refresh_token);
      return request<T>(path, init, false);
    }
    clearStoredTokens();
  }

  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const errBody = await resp.json();
      if (typeof errBody?.detail === "string") detail = errBody.detail;
    } catch {
      // ignore non-json errors
    }
    throw new ApiError(resp.status, detail);
  }

  if (resp.status === 204) {
    return undefined as T;
  }
  return (await resp.json()) as T;
}

export const api = {
  baseUrl: API_BASE,

  // Auth
  register: (payload: { email: string; full_name: string; password: string }) =>
    request<AuthTokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: (payload: { email: string; password: string }) =>
    request<AuthTokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getGoogleAuthUrl: (state?: string) =>
    request<{ authorize_url: string; client_id: string; redirect_uri: string }>(
      `/auth/google/url${state ? `?state=${encodeURIComponent(state)}` : ""}`
    ),

  loginWithGoogleToken: (id_token: string) =>
    request<AuthTokenResponse>("/auth/google", {
      method: "POST",
      body: JSON.stringify({ id_token }),
    }),

  exchangeGoogleCode: (code: string, redirect_uri?: string) =>
    request<AuthTokenResponse>("/auth/google/callback", {
      method: "POST",
      body: JSON.stringify({ code, redirect_uri }),
    }),

  me: () => request<User>("/auth/me"),

  // Projects & Configuration
  listProjects: (params?: { doc_type?: string; status?: string; search?: string }) => {
    const qs = new URLSearchParams();
    if (params?.doc_type) qs.set("doc_type", params.doc_type);
    if (params?.status) qs.set("status", params.status);
    if (params?.search) qs.set("search", params.search);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<ProjectSummary[]>(`/projects${suffix}`);
  },

  createProject: (payload: {
    title: string;
    doc_type: DocType;
    main_topic: string;
    theme_config?: Partial<ThemeConfig>;
    sections?: Array<{ title: string }>;
    ai_outline_suggested?: boolean;
  }) =>
    request<ProjectDetail>("/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),

  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, {
      method: "DELETE",
    }),

  updateOutline: (
    id: string,
    sections: Array<{ id?: string; title: string }>,
    ai_outline_suggested?: boolean
  ) =>
    request<ProjectDetail>(`/projects/${id}/outline`, {
      method: "PUT",
      body: JSON.stringify({ sections, ai_outline_suggested }),
    }),

  // AI Generation & Refinement
  suggestOutline: (payload: {
    doc_type: DocType;
    main_topic: string;
    target_count?: number;
    project_id?: string;
  }) =>
    request<OutlineSuggestion>("/projects/suggest-outline", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  generateProject: (id: string, payload?: { generate_images?: boolean; only_missing?: boolean }) =>
    request<ProjectDetail>(`/projects/${id}/generate`, {
      method: "POST",
      body: JSON.stringify(payload ?? { generate_images: true }),
    }),

  refineSection: (sectionId: string, payload: { refinement_prompt: string; regenerate_image?: boolean }) =>
    request<DocumentSection>(`/sections/${sectionId}/refine`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  regenerateSectionImage: (sectionId: string, payload?: { image_prompt?: string; caption?: string }) =>
    request<DocumentSection>(`/sections/${sectionId}/regenerate-image`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    }),

  setFeedback: (sectionId: string, rating: LikeStatus, note?: string) =>
    request<DocumentSection>(`/sections/${sectionId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ rating, note }),
    }),

  addComment: (sectionId: string, body: string) =>
    request<SectionComment>(`/sections/${sectionId}/comments`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),

  deleteComment: (commentId: string) =>
    request<void>(`/comments/${commentId}`, { method: "DELETE" }),

  listRevisions: (sectionId: string) =>
    request<SectionRevision[]>(`/sections/${sectionId}/revisions`),

  // Export & Asset Blob Fetch
  downloadExport: async (projectId: string): Promise<{ blob: Blob; filename: string }> => {
    const { accessToken } = getStoredTokens();
    const resp = await fetch(`${API_BASE}/projects/${projectId}/export`, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });
    if (!resp.ok) {
      throw new ApiError(resp.status, "Export download failed");
    }
    const disp = resp.headers.get("Content-Disposition") || "";
    const match = disp.match(/filename="([^"]+)"/);
    return {
      blob: await resp.blob(),
      filename: match?.[1] || `document_${projectId}.docx`,
    };
  },

  fetchAssetBlobUrl: async (assetId: string): Promise<string> => {
    const { accessToken } = getStoredTokens();
    const resp = await fetch(`${API_BASE}/assets/${assetId}`, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });
    if (!resp.ok) throw new ApiError(resp.status, "Failed to load asset");
    const blob = await resp.blob();
    return URL.createObjectURL(blob);
  },

  // Monitoring & Reconstruction
  getAuditLogs: (params?: {
    project_id?: string;
    event_type?: string;
    severity?: string;
    trace_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.project_id) qs.set("project_id", params.project_id);
    if (params?.event_type) qs.set("event_type", params.event_type);
    if (params?.severity) qs.set("severity", params.severity);
    if (params?.trace_id) qs.set("trace_id", params.trace_id);
    if (params?.search) qs.set("search", params.search);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<{ total: number; limit: number; offset: number; items: AuditLogItem[] }>(
      `/monitoring/logs${suffix}`
    );
  },

  getMonitoringMetrics: (projectId?: string) =>
    request<MonitoringMetrics>(
      `/monitoring/metrics${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`
    ),

  getProjectTimeline: (projectId: string) =>
    request<ProjectTimeline>(`/projects/${projectId}/timeline`),

  reconstructProject: (
    projectId: string,
    params: { version?: number; at_timestamp?: string; event_seq_id?: number }
  ) => {
    const qs = new URLSearchParams();
    if (params.version !== undefined) qs.set("version", String(params.version));
    if (params.at_timestamp) qs.set("at_timestamp", params.at_timestamp);
    if (params.event_seq_id !== undefined) qs.set("event_seq_id", String(params.event_seq_id));
    return request<ReconstructionResult>(`/projects/${projectId}/reconstruct?${qs.toString()}`);
  },

  restoreVersion: (projectId: string, version: number) =>
    request<{ project_id: string; restored_from_version: number; new_version: number; restored_sections: number }>(
      `/projects/${projectId}/restore/${version}`,
      { method: "POST" }
    ),
};
