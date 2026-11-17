from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq_id: int
    event_id: str
    trace_id: str
    user_id: str | None
    project_id: str | None
    section_id: str | None
    event_type: str
    severity: str
    entity_type: str
    entity_id: str | None
    http_method: str | None
    endpoint: str | None
    status_code: int | None
    duration_ms: float | None
    before_state_json: dict | None
    after_state_json: dict | None
    metadata_json: dict
    created_at: datetime


class PaginatedAuditLogsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AuditLogItemResponse]


class LLMMetricItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trace_id: str
    user_id: str | None
    project_id: str | None
    section_id: str | None
    operation: str
    provider: str
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    status: str
    error_message: str | None
    prompt_preview: str
    created_at: datetime


class MonitoringMetricsResponse(BaseModel):
    analytics: dict
    recent_llm_calls: list[LLMMetricItemResponse]
    total_llm_records: int


class SnapshotSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    version_number: int
    trigger_event_type: str
    trigger_event_id: str | None
    created_at: datetime


class ProjectTimelineResponse(BaseModel):
    project_id: str
    current_version: int
    snapshots: list[SnapshotSummaryResponse]
    events: list[AuditLogItemResponse]


class ReconstructionResponse(BaseModel):
    project_id: str
    reconstruction_mode: str
    reconstructed_state: dict
    diff_against_live: list[dict]


class RestoreVersionResponse(BaseModel):
    project_id: str
    restored_from_version: int
    new_version: int
    restored_sections: int
