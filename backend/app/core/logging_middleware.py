import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Return the active request trace_id or generate a fresh one."""
    current = _trace_id_ctx.get()
    if not current:
        current = str(uuid.uuid4())
        _trace_id_ctx.set(current)
    return current


class TraceAndTimingMiddleware(BaseHTTPMiddleware):
    """Assign correlation trace_id and measure request latency."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming_trace = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        token = _trace_id_ctx.set(incoming_trace)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
            response.headers["X-Trace-Id"] = incoming_trace
            response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
            return response
        finally:
            _trace_id_ctx.reset(token)
