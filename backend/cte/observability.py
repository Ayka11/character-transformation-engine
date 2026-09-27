"""Optional API authentication and operational request observability."""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

LOGGER = logging.getLogger("cte.api")
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int = 60):
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        bucket = self._buckets[key]
        cutoff = current - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            retry_after = max(1, int(bucket[0] + self.window_seconds - current + 0.999))
            return False, retry_after
        bucket.append(current)
        return True, 0

PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/science-lab/ui",
}

PUBLIC_PREFIXES = (
    "/science-lab/assets/",
)


class SecurityObservabilityMiddleware(BaseHTTPMiddleware):
    """Enforce configured read/write API keys and emit operational audit events."""

    def __init__(self, app, store=None):
        super().__init__(app)
        self.store = store

    @staticmethod
    def _request_id(request: Request) -> str:
        supplied = request.headers.get("X-Request-ID", "")
        return supplied if SAFE_REQUEST_ID.fullmatch(supplied) else str(uuid.uuid4())

    @staticmethod
    def _public(path: str) -> bool:
        return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)

    @staticmethod
    def _authorized(request: Request) -> tuple[bool, str | None]:
        read_key = os.getenv("CTE_READ_API_KEY")
        write_key = os.getenv("CTE_WRITE_API_KEY")
        fallback = os.getenv("CTE_API_KEY")

        if not any((read_key, write_key, fallback)):
            return True, None

        if fallback:
            write_key = write_key or fallback
            read_key = read_key or fallback

        presented = request.headers.get("X-CTE-API-Key")
        if not presented:
            return False, None

        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return (presented == read_key or presented == write_key), "read"
        return presented == write_key, "write"

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        request_id = self._request_id(request)
        auth_mode = None

        if not self._public(request.url.path):
            authorized, auth_mode = self._authorized(request)
            if not authorized:
                response = JSONResponse({"detail": "authentication required"}, status_code=401)
                response.headers["X-Request-ID"] = request_id
                response.headers["WWW-Authenticate"] = "ApiKey"
                self._audit(request, request_id, 401, started, "auth_failed")
                return response

        try:
            response = await call_next(request)
        except Exception:
            duration = (time.perf_counter() - started) * 1000
            LOGGER.exception(
                "request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
                request_id, request.method, request.url.path, duration
            )
            self._audit(request, request_id, 500, started, "exception", auth_mode)
            raise

        duration = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{duration:.2f}"
        self._audit(request, request_id, response.status_code, started, "complete", auth_mode)
        return response

    def _audit(
        self,
        request: Request,
        request_id: str,
        status: int,
        started: float,
        outcome: str,
        auth_mode: str | None = None,
    ):
        duration = (time.perf_counter() - started) * 1000
        payload = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "duration_ms": round(duration, 3),
            "outcome": outcome,
            "auth_mode": auth_mode,
        }
        if self.store is not None:
            try:
                self.store.append_event(
                    "api:" + request_id,
                    "api",
                    "HTTP_REQUEST",
                    payload,
                    input_hash=request_id,
                    output_hash=str(status),
                    provenance_record_id="cte.api.observability.1.0",
                )
            except Exception:
                LOGGER.exception("operational audit persistence failed request_id=%s", request_id)


def configure_logging():
    logging.basicConfig(
        level=os.getenv("CTE_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
