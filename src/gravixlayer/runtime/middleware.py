"""ASGI middleware for request tracking and CORS."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from .. import telemetry

logger = logging.getLogger("gravixlayer.runtime")


class RequestMiddleware:
    """Adds X-Request-ID header and logs request timing."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())[:8]
        start = time.monotonic()
        method = scope.get("method", "")
        path = scope.get("path", "")
        carrier = {
            key.decode("latin-1"): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        status_holder = {"code": 0}

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message.get("status", 0)
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                elapsed = time.monotonic() - start
                headers.append(
                    (b"x-response-time", f"{elapsed * 1000:.1f}ms".encode())
                )
                message["headers"] = headers
            await send(message)

        span_name = f"{method} {path}" if method else path
        with telemetry.server_span(span_name, carrier) as span:
            if span is not None:
                span.set_attribute("http.request.method", method)
                span.set_attribute("url.path", path)
                span.set_attribute("gravixlayer.request_id", request_id)
            logger.debug("[%s] %s %s", request_id, method, path)
            await self.app(scope, receive, send_wrapper)
            if span is not None and status_holder["code"]:
                span.set_attribute("http.response.status_code", status_holder["code"])


class CORSMiddleware:
    """Simple CORS middleware with configurable origins."""

    def __init__(
        self,
        app: Any,
        allow_origins: list[str] | None = None,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
    ) -> None:
        self.app = app
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Handle preflight OPTIONS
        if scope.get("method") == "OPTIONS":
            headers = [
                (b"access-control-allow-origin", ", ".join(self.allow_origins).encode()),
                (b"access-control-allow-methods", ", ".join(self.allow_methods).encode()),
                (b"access-control-allow-headers", ", ".join(self.allow_headers).encode()),
                (b"access-control-max-age", b"86400"),
            ]
            await send({"type": "http.response.start", "status": 204, "headers": headers})
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append(
                    (b"access-control-allow-origin", ", ".join(self.allow_origins).encode())
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
