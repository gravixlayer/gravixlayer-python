"""SDK exception hierarchy.

HTTP failures carry a short product message plus ``status``, ``code``, and
``body``. Retry decisions stay on status; these fields are for display and
callers only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping, Optional

_MESSAGE_KEYS = ("message", "error", "detail", "msg")


def format_error_message(text: str, body: Any = None) -> str:
    """Pick the shortest useful product line from an API error body."""
    if isinstance(body, dict):
        for key in _MESSAGE_KEYS:
            found = _string_field(body.get(key))
            if found is not None:
                return found
    trimmed = (text or "").strip()
    return trimmed if trimmed else "Request failed."


def error_code(body: Any) -> Optional[str]:
    if isinstance(body, dict):
        code = body.get("code")
        if isinstance(code, str):
            value = code.strip()
            return value or None
    return None


def error_from_response(
    status: int,
    text: str,
    headers: Optional[Mapping[str, str]] = None,
) -> "GravixLayerError":
    """Map an HTTP response to the matching exception. Status only picks the class."""
    body = _parse_json(text)
    header_map = {str(k).lower(): v for k, v in dict(headers or {}).items()}
    payload: Any = body if body is not None else (text if text else None)
    if status == 401:
        return GravixLayerAuthenticationError(
            "Authentication failed.",
            status=401,
            code=error_code(body),
            body=payload,
            headers=header_map,
        )
    return _class_for_status(status)(
        format_error_message(text, body),
        status=status,
        code=error_code(body),
        body=payload,
        headers=header_map,
    )


def _class_for_status(status: int) -> type["GravixLayerError"]:
    if status == 429:
        return GravixLayerRateLimitError
    if status >= 500:
        return GravixLayerServerError
    if 400 <= status < 500:
        return GravixLayerBadRequestError
    return GravixLayerError


def _parse_json(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _string_field(value: Any) -> Optional[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, dict):
        nested = value.get("message")
        if isinstance(nested, str):
            stripped = nested.strip()
            return stripped or None
    return None


def _request_id(headers: Optional[Mapping[str, str]]) -> Optional[str]:
    if not headers:
        return None
    for key in ("x-request-id", "x-correlation-id"):
        value = headers.get(key)
        if value:
            return value
    return None


class GravixLayerError(Exception):
    """Base SDK exception."""

    def __init__(
        self,
        message: str = "",
        *,
        status: Optional[int] = None,
        code: Optional[str] = None,
        body: Any = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.headers = dict(headers) if headers is not None else None
        self.code = code if code is not None else error_code(body)
        self.request_id = _request_id(self.headers)


class GravixLayerAuthenticationError(GravixLayerError):
    pass


class GravixLayerRateLimitError(GravixLayerError):
    @property
    def retry_after_seconds(self) -> Optional[float]:
        if not self.headers:
            return None
        raw = self.headers.get("retry-after")
        if raw is None:
            return None
        try:
            delay = float(raw)
        except (TypeError, ValueError):
            delay = None
        if delay is not None:
            return delay if delay >= 0.0 else None
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


class GravixLayerServerError(GravixLayerError):
    pass


class GravixLayerBadRequestError(GravixLayerError):
    pass


class GravixLayerConnectionError(GravixLayerError):
    pass
