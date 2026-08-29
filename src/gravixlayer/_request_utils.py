from types import MappingProxyType
from typing import Any, Callable, Dict, Optional

import httpx

RETRYABLE_STATUS = frozenset((502, 503, 504))
SUCCESS_STATUS = frozenset((200, 201, 202, 204, 207))
JSON_HEADERS = MappingProxyType({"Content-Type": "application/json"})
_ABSOLUTE_URL_PREFIXES = ("http://", "https://")
MAX_RETRY_AFTER_SECS = 60.0

# Shared by sync and async clients. Keepalive must cover concurrent create+exec
# (never a 1-connection pool). Expiry is longer than httpx's 5s default so a
# warmed connection is still there for the next request in a short CLI.
HTTP_LIMITS = httpx.Limits(
    max_connections=20,
    max_keepalive_connections=20,
    keepalive_expiry=30.0,
)


def build_url(
    endpoint: str,
    service: str,
    service_urls: Dict[str, str],
    base_url: str,
) -> str:
    """Build request URL for either absolute endpoints or service-relative paths."""
    if endpoint and endpoint.startswith(_ABSOLUTE_URL_PREFIXES):
        return endpoint

    if service:
        service_base = service_urls.get(service, f"{base_url}/{service}")
    else:
        service_base = base_url

    if not endpoint:
        return service_base
    # Query-only endpoints (e.g. "?project_id=…") must not insert a path slash.
    if endpoint.startswith("?"):
        return f"{service_base}{endpoint}"
    return f"{service_base}/{endpoint.lstrip('/')}"


def prepare_request_kwargs(
    data: Optional[Dict[str, Any]],
    kwargs: Dict[str, Any],
) -> None:
    """Mutate kwargs in place for JSON or multipart requests."""
    has_files = "files" in kwargs
    if has_files:
        if data is not None:
            kwargs["data"] = data
        return

    if data is not None:
        kwargs["json"] = data
        existing = kwargs.get("headers")
        if existing:
            headers = dict(existing)
            headers.setdefault("Content-Type", "application/json")
            kwargs["headers"] = headers
        else:
            kwargs["headers"] = JSON_HEADERS


def next_retry_delay(
    attempt: int,
    rand: Callable[[], float],
    retry_after: Optional[str] = None,
) -> float:
    """Compute retry delay with optional Retry-After header override.

    Numeric Retry-After is honoured and clamped so a bad header cannot stall
    the client. Non-numeric values fall through to exponential backoff.
    """
    if retry_after:
        try:
            delay = float(retry_after)
        except ValueError:
            delay = None
        else:
            if delay >= 0.0:
                return min(delay, MAX_RETRY_AFTER_SECS)

    return (1 << attempt) + rand()


def can_retry(attempt: int, max_retries: int) -> bool:
    return attempt < max_retries
