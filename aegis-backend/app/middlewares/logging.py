import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.utils.logger import logger, reset_correlation_id, set_correlation_id


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach correlation ID for each request and response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request with correlation ID context management."""
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        token = set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            reset_correlation_id(token)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each HTTP request and response metadata."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Measure and log request processing details."""
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            logger.bind(method=request.method, path=request.url.path).exception("HTTP request failed")
            raise
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.bind(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
            ).info("HTTP request processed")
        return response
