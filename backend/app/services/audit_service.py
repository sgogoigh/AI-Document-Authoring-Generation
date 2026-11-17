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
        llm_filters = []
        audit_filters = []
        export_filters = []
        section_filters = [DocumentSection.is_deleted.is_(False)]

        if user_id:
            llm_filters.append(LLMCallMetric.user_id == user_id)
            audit_filters.append(AuditEventLog.user_id == user_id)
            export_filters.append(ExportRecord.user_id == user_id)
        if project_id:
            llm_filters.append(LLMCallMetric.project_id == project_id)
            audit_filters.append(AuditEventLog.project_id == project_id)
            export_filters.append(ExportRecord.project_id == project_id)
            section_filters.append(DocumentSection.project_id == project_id)
        elif user_id:
            from app.models.project import Project

            user_proj_subq = select(Project.id).where(Project.user_id == user_id)
            section_filters.append(DocumentSection.project_id.in_(user_proj_subq))

        # 1. SQL-aggregated LLM metrics (avoids hydrating ORM rows)
        llm_agg_rows = db.execute(
            select(
                LLMCallMetric.operation,
                LLMCallMetric.status,
                func.count(LLMCallMetric.id),
                func.coalesce(func.sum(LLMCallMetric.input_tokens), 0),
                func.coalesce(func.sum(LLMCallMetric.output_tokens), 0),
                func.coalesce(func.sum(LLMCallMetric.total_tokens), 0),
                func.coalesce(func.sum(LLMCallMetric.latency_ms), 0.0),
            )
            .where(*llm_filters)
            .group_by(LLMCallMetric.operation, LLMCallMetric.status)
        ).all()

        total_calls = 0
        successful_calls = 0
        failed_calls = 0
        total_in = 0
        total_out = 0
        total_tok = 0
        total_latency_sum = 0.0
        op_buckets: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "tokens": 0, "lat_sum": 0.0, "errors": 0}
        )

        for op, st, cnt, in_tok, out_tok, tot_tok, lat_sum in llm_agg_rows:
            c = int(cnt or 0)
            total_calls += c
            if st == "success":
                successful_calls += c
            elif st == "error":
                failed_calls += c
            total_in += int(in_tok or 0)
            total_out += int(out_tok or 0)
            total_tok += int(tot_tok or 0)
            total_latency_sum += float(lat_sum or 0.0)

            b = op_buckets[op]
            b["count"] += c
            b["tokens"] += int(tot_tok or 0)
            b["lat_sum"] += float(lat_sum or 0.0)
            if st == "error":
                b["errors"] += c

        operations_breakdown = {
            op: {
                "count": data["count"],
                "total_tokens": data["tokens"],
                "avg_latency_ms": round(data["lat_sum"] / data["count"], 2) if data["count"] else 0.0,
                "errors": data["errors"],
            }
            for op, data in op_buckets.items()
        }

        # 2. Sorted scalar latencies for exact p50/p95 without ORM overhead
        latencies = list(
            db.scalars(
                select(LLMCallMetric.latency_ms)
                .where(*llm_filters)
                .order_by(LLMCallMetric.latency_ms)
            ).all()
        )
        float_latencies = [float(x) for x in latencies if x is not None]

        # 3. SQL-aggregated Audit event counts (skips heavy JSON blobs)
        audit_rows = db.execute(
            select(AuditEventLog.event_type, func.count(AuditEventLog.seq_id))
            .where(*audit_filters)
            .group_by(AuditEventLog.event_type)
        ).all()
        event_type_counts = {ev_type: int(cnt or 0) for ev_type, cnt in audit_rows}
        total_audit_events = sum(event_type_counts.values())

        # 4. SQL-aggregated Feedback satisfaction counts
        fb_rows = db.execute(
            select(DocumentSection.like_status, func.count(DocumentSection.id))
            .where(*section_filters)
            .group_by(DocumentSection.like_status)
        ).all()
        fb_map = {rating: int(cnt or 0) for rating, cnt in fb_rows}
        likes = fb_map.get("like", 0)
        dislikes = fb_map.get("dislike", 0)
        neutral = fb_map.get("none", 0)
        rated_total = likes + dislikes
        satisfaction_rate = round((likes / rated_total) * 100.0, 1) if rated_total else None

        # 5. SQL Export count
        total_exports = (
            db.scalar(select(func.count(ExportRecord.id)).where(*export_filters)) or 0
        )

        return {
            "llm": {
                "total_calls": total_calls,
                "successful_calls": successful_calls,
                "failed_calls": failed_calls,
                "error_rate": round((failed_calls / total_calls) * 100.0, 2) if total_calls else 0.0,
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_tokens": total_tok,
                "avg_latency_ms": round(total_latency_sum / total_calls, 2) if total_calls else 0.0,
                "p50_latency_ms": _percentile(float_latencies, 0.50),
                "p95_latency_ms": _percentile(float_latencies, 0.95),
                "operations_breakdown": operations_breakdown,
            },
            "feedback": {
                "like_count": likes,
                "dislike_count": dislikes,
                "none_count": neutral,
                "satisfaction_rate_pct": satisfaction_rate,
            },
            "exports": {"total_exports": int(total_exports)},
            "audit": {
                "total_events": total_audit_events,
                "event_type_counts": event_type_counts,
            },
        }
