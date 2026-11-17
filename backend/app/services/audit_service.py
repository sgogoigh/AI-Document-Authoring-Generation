from collections import defaultdict
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.logging_middleware import get_trace_id
from app.models.audit import AuditEventLog
from app.models.metrics import LLMCallMetric
from app.models.project import ExportRecord
from app.models.section import DocumentSection


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    idx = max(0, min(len(sorted_values) - 1, ceil(pct * len(sorted_values)) - 1))
    return round(sorted_values[idx], 2)


class AuditService:
    """Service for immutable audit event logging, LLM metrics, filtering, and analytics."""

    @staticmethod
    def record_event(
        db: Session,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        section_id: str | None = None,
        severity: str = "INFO",
        before_state: dict | None = None,
        after_state: dict | None = None,
        metadata: dict | None = None,
        trace_id: str | None = None,
        http_method: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        duration_ms: float | None = None,
    ) -> AuditEventLog:
        entry = AuditEventLog(
            trace_id=trace_id or get_trace_id(),
            user_id=user_id,
            project_id=project_id,
            section_id=section_id,
            event_type=event_type,
            severity=severity,
            entity_type=entity_type,
            entity_id=entity_id,
            http_method=http_method,
            endpoint=endpoint,
            status_code=status_code,
            duration_ms=duration_ms,
            before_state_json=before_state,
            after_state_json=after_state,
            metadata_json=metadata or {},
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.flush()
        return entry

    @staticmethod
    def record_llm_metric(
        db: Session,
        *,
        operation: str,
        model_name: str,
        user_id: str | None = None,
        project_id: str | None = None,
        section_id: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int | None = None,
        latency_ms: float = 0.0,
        status: str = "success",
        error_message: str | None = None,
        prompt_preview: str = "",
        trace_id: str | None = None,
    ) -> LLMCallMetric:
        metric = LLMCallMetric(
            trace_id=trace_id or get_trace_id(),
            user_id=user_id,
            project_id=project_id,
            section_id=section_id,
            operation=operation,
            provider="gemini",
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens if total_tokens is not None else (input_tokens + output_tokens),
            latency_ms=round(latency_ms, 2),
            status=status,
            error_message=error_message,
            prompt_preview=prompt_preview[:500],
            created_at=datetime.now(timezone.utc),
        )
        db.add(metric)
        db.flush()
        return metric

    @staticmethod
    def query_logs(
        db: Session,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        trace_id: str | None = None,
        entity_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditEventLog], int]:
        stmt = select(AuditEventLog)
        if user_id:
            stmt = stmt.where(AuditEventLog.user_id == user_id)
        if project_id:
            stmt = stmt.where(AuditEventLog.project_id == project_id)
        if event_type:
            stmt = stmt.where(AuditEventLog.event_type == event_type)
        if severity:
            stmt = stmt.where(AuditEventLog.severity == severity)
        if trace_id:
            stmt = stmt.where(AuditEventLog.trace_id == trace_id)
        if entity_type:
            stmt = stmt.where(AuditEventLog.entity_type == entity_type)
        if date_from:
            stmt = stmt.where(AuditEventLog.created_at >= date_from)
        if date_to:
            stmt = stmt.where(AuditEventLog.created_at <= date_to)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    AuditEventLog.event_type.ilike(pattern),
                    AuditEventLog.entity_type.ilike(pattern),
                    AuditEventLog.endpoint.ilike(pattern),
                    AuditEventLog.trace_id.ilike(pattern),
                )
            )

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            db.scalars(
                stmt.order_by(AuditEventLog.seq_id.desc()).offset(offset).limit(limit)
            ).all()
        )
        return items, total

    @staticmethod
    def query_llm_metrics(
        db: Session,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
        operation: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[LLMCallMetric], int]:
        stmt = select(LLMCallMetric)
        if user_id:
            stmt = stmt.where(LLMCallMetric.user_id == user_id)
        if project_id:
            stmt = stmt.where(LLMCallMetric.project_id == project_id)
        if operation:
            stmt = stmt.where(LLMCallMetric.operation == operation)
        if status:
            stmt = stmt.where(LLMCallMetric.status == status)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            db.scalars(
                stmt.order_by(LLMCallMetric.created_at.desc()).offset(offset).limit(limit)
            ).all()
        )
        return items, total

    @staticmethod
    def compute_analytics(
        db: Session,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> dict:
        metric_stmt = select(LLMCallMetric)
        audit_stmt = select(AuditEventLog)
        export_stmt = select(ExportRecord)
        section_stmt = select(DocumentSection).where(DocumentSection.is_deleted.is_(False))

        if user_id:
            metric_stmt = metric_stmt.where(LLMCallMetric.user_id == user_id)
            audit_stmt = audit_stmt.where(AuditEventLog.user_id == user_id)
            export_stmt = export_stmt.where(ExportRecord.user_id == user_id)
        if project_id:
            metric_stmt = metric_stmt.where(LLMCallMetric.project_id == project_id)
            audit_stmt = audit_stmt.where(AuditEventLog.project_id == project_id)
            export_stmt = export_stmt.where(ExportRecord.project_id == project_id)
            section_stmt = section_stmt.where(DocumentSection.project_id == project_id)

        metrics = list(db.scalars(metric_stmt).all())
        latencies = sorted(m.latency_ms for m in metrics if m.latency_ms is not None)
        total_calls = len(metrics)
        successful_calls = sum(1 for m in metrics if m.status == "success")
        failed_calls = sum(1 for m in metrics if m.status == "error")

        op_buckets: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "tokens": 0, "latencies": [], "errors": 0}
        )
        for m in metrics:
            b = op_buckets[m.operation]
            b["count"] += 1
            b["tokens"] += m.total_tokens
            b["latencies"].append(m.latency_ms)
            if m.status == "error":
                b["errors"] += 1

        operations_breakdown = {
            op: {
                "count": data["count"],
                "total_tokens": data["tokens"],
                "avg_latency_ms": round(sum(data["latencies"]) / len(data["latencies"]), 2)
                if data["latencies"]
                else 0.0,
                "errors": data["errors"],
            }
            for op, data in op_buckets.items()
        }

        audit_events = list(db.scalars(audit_stmt).all())
        event_type_counts: dict[str, int] = defaultdict(int)
        for ev in audit_events:
            event_type_counts[ev.event_type] += 1

        if user_id and not project_id:
            from app.models.project import Project

            user_proj_ids = list(
                db.scalars(select(Project.id).where(Project.user_id == user_id)).all()
            )
            if user_proj_ids:
                section_stmt = section_stmt.where(DocumentSection.project_id.in_(user_proj_ids))
            else:
                section_stmt = section_stmt.where(DocumentSection.project_id == "__none__")

        sections = list(db.scalars(section_stmt).all())
        likes = sum(1 for s in sections if s.like_status == "like")
        dislikes = sum(1 for s in sections if s.like_status == "dislike")
        neutral = sum(1 for s in sections if s.like_status == "none")
        rated_total = likes + dislikes
        satisfaction_rate = round((likes / rated_total) * 100.0, 1) if rated_total else None

        total_exports = db.scalar(select(func.count()).select_from(export_stmt.subquery())) or 0

        return {
            "llm": {
                "total_calls": total_calls,
                "successful_calls": successful_calls,
                "failed_calls": failed_calls,
                "error_rate": round((failed_calls / total_calls) * 100.0, 2) if total_calls else 0.0,
                "total_input_tokens": sum(m.input_tokens for m in metrics),
                "total_output_tokens": sum(m.output_tokens for m in metrics),
                "total_tokens": sum(m.total_tokens for m in metrics),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
                "p50_latency_ms": _percentile(latencies, 0.50),
                "p95_latency_ms": _percentile(latencies, 0.95),
                "operations_breakdown": operations_breakdown,
            },
            "feedback": {
                "like_count": likes,
                "dislike_count": dislikes,
                "none_count": neutral,
                "satisfaction_rate_pct": satisfaction_rate,
            },
            "exports": {"total_exports": total_exports},
            "audit": {
                "total_events": len(audit_events),
                "event_type_counts": dict(event_type_counts),
            },
        }
