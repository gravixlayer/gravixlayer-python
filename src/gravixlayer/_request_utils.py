from typing import Any, Callable, Dict, Optional

RETRYABLE_STATUS = frozenset((502, 503, 504))
SUCCESS_STATUS = frozenset((200, 201, 202, 204, 207))
JSON_HEADERS = {"Content-Type": "application/json"}
_ABSOLUTE_URL_PREFIXES = ("http://", "https://")


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

    return f"{service_base}/{endpoint.lstrip('/')}" if endpoint else service_base


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
    kwargs["headers"] = JSON_HEADERS


def next_retry_delay(
    attempt: int,
    rand: Callable[[], float],
    retry_after: Optional[str] = None,
) -> float:
    """Compute retry delay with optional Retry-After header override."""
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass

    return (1 << attempt) + rand()


def can_retry(attempt: int, max_retries: int) -> bool:
    return attempt < max_retries
