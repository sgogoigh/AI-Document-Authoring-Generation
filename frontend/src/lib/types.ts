export type DocType = "docx" | "pptx";
export type LikeStatus = "like" | "dislike" | "none";
export type PaletteName = "executive_navy" | "emerald_slate" | "obsidian_gold" | "warm_editorial";
export type EditorialTone = "executive" | "analytical" | "persuasive" | "technical";

export interface ThemeConfig {
  palette: PaletteName;
  tone: EditorialTone;
  audience: string;
  include_images: boolean;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  auth_provider: "local" | "google" | "hybrid";
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface SectionComment {
  id: string;
  section_id: string;
  user_id: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentAsset {
  id: string;
  section_id: string | null;
  asset_type: string;
  prompt: string;
  mime_type: string;
  caption: string;
  width: number;
  height: number;
  is_active: boolean;
  created_at: string;
}

export interface DocumentSection {
  id: string;
  project_id: string;
  order_index: number;
  title: string;
  section_kind: "section" | "slide";
  current_revision_id: string | null;
  current_content_json: Record<string, unknown> | null;
  current_content_text: string;
  like_status: LikeStatus;
  revision_count: number;
  comments: SectionComment[];
  assets: DocumentAsset[];
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  title: string;
  doc_type: DocType;
  main_topic: string;
  status: string;
  theme_config_json: ThemeConfig;
  ai_outline_suggested: boolean;
  current_version: number;
  section_count: number;
  like_count: number;
  dislike_count: number;
  export_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail {
  id: string;
  user_id: string;
  title: string;
  doc_type: DocType;
  main_topic: string;
  status: string;
  theme_config_json: ThemeConfig;
  ai_outline_suggested: boolean;
  current_version: number;
  sections: DocumentSection[];
  created_at: string;
  updated_at: string;
}

export interface OutlineSuggestion {
  recommended_title: string;
  rationale: string;
  items: string[];
}

export interface SectionRevision {
  id: string;
  section_id: string;
  project_id: string;
  revision_number: number;
  project_version: number;
  source: string;
  refinement_prompt: string | null;
  previous_content_json: Record<string, unknown> | null;
  new_content_json: Record<string, unknown>;
  diff_summary_json: {
    changed_fields?: string[];
    before_word_count?: number;
    after_word_count?: number;
    word_count_delta?: number;
  };
  created_at: string;
}

export interface AuditLogItem {
  seq_id: number;
  event_id: string;
  trace_id: string;
  user_id: string | null;
  project_id: string | null;
  section_id: string | null;
  event_type: string;
  severity: string;
  entity_type: string;
  entity_id: string | null;
  http_method: string | null;
  endpoint: string | null;
  status_code: number | null;
  duration_ms: number | null;
  before_state_json: Record<string, unknown> | null;
  after_state_json: Record<string, unknown> | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface LLMMetricItem {
  id: string;
  trace_id: string;
  project_id: string | null;
  section_id: string | null;
  operation: string;
  provider: string;
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  status: string;
  error_message: string | null;
  prompt_preview: string;
  created_at: string;
}

export interface MonitoringMetrics {
  analytics: {
    llm: {
      total_calls: number;
      successful_calls: number;
      failed_calls: number;
      error_rate: number;
      total_input_tokens: number;
      total_output_tokens: number;
      total_tokens: number;
      avg_latency_ms: number;
      p50_latency_ms: number;
      p95_latency_ms: number;
      operations_breakdown: Record<
        string,
        { count: number; total_tokens: number; avg_latency_ms: number; errors: number }
      >;
    };
    feedback: {
      like_count: number;
      dislike_count: number;
      none_count: number;
      satisfaction_rate_pct: number | null;
    };
    exports: { total_exports: number };
    audit: { total_events: number; event_type_counts: Record<string, number> };
  };
  recent_llm_calls: LLMMetricItem[];
  total_llm_records: number;
}

export interface SnapshotSummary {
  id: string;
  project_id: string;
  version_number: number;
  trigger_event_type: string;
  trigger_event_id: string | null;
  created_at: string;
}

export interface ProjectTimeline {
  project_id: string;
  current_version: number;
  snapshots: SnapshotSummary[];
  events: AuditLogItem[];
}

export interface ReconstructionResult {
  project_id: string;
  reconstruction_mode: string;
  reconstructed_state: {
    title: string;
    doc_type: DocType;
    main_topic: string;
    version_number: number;
    sections: Array<{
      id: string;
      order_index: number;
      title: string;
      current_content_json: Record<string, unknown> | null;
      current_content_text: string;
      like_status: LikeStatus;
      comments: Array<{ id: string; body: string; created_at: string }>;
    }>;
  };
  diff_against_live: Array<{
    section_id: string;
    title: string;
    change: string;
    content_diff?: {
      changed_fields?: string[];
      word_count_delta?: number;
    };
    like_changed?: boolean;
  }>;
}
