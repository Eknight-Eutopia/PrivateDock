import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.logger.logger import log_event, LOG_LEVEL_INFO


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        latency = time.monotonic() - start
        log_event("API", "Request",
                  f"{request.method} {request.url.path} -> {response.status_code} ({latency*1000:.1f}ms)",
                  LOG_LEVEL_INFO)
        return response
