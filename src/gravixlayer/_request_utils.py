from types import MappingProxyType
from typing import Any, Callable, Dict, Generator, Optional, Tuple

import httpx

RETRYABLE_STATUS = frozenset((502, 503, 504))
# GET, PUT and DELETE are safe to send again. POST and PATCH are not: a lost
# response may already have created the resource.
REPLAYABLE_METHODS = frozenset(("GET", "HEAD", "PUT", "DELETE", "OPTIONS"))
SUCCESS_STATUS = frozenset((200, 201, 202, 204, 207))
JSON_HEADERS = MappingProxyType({"Content-Type": "application/json"})
_ABSOLUTE_URL_PREFIXES = ("http://", "https://")
# httpx drops a written default port only when the scheme is already lowercase.
_DEFAULT_PORTS = MappingProxyType({"http": 80, "https": 443})
MAX_RETRY_AFTER_SECS = 60.0

# Shared by sync and async clients. Keepalive must cover concurrent create+exec
# (never a 1-connection pool). Expiry is longer than httpx's 5s default so a
# warmed connection is still there for the next request in a short CLI.
HTTP_LIMITS = httpx.Limits(
    max_connections=20,
    max_keepalive_connections=20,
    keepalive_expiry=30.0,
)


def url_origin(url: httpx.URL) -> Tuple[str, str, Optional[int]]:
    """Scheme, host, and port of ``url``. An omitted port is the scheme's default."""
    return (url.scheme, url.host, url.port or _DEFAULT_PORTS.get(url.scheme))


def split_authorization(api_key: str, headers: Optional[Dict[str, str]]) -> Tuple[str, Dict[str, str]]:
    """The client's ``Authorization`` value, and its other default headers.

    An ``Authorization`` entry in ``headers`` replaces the API key.
    """
    authorization = f"Bearer {api_key}"
    rest: Dict[str, str] = {}
    for name, value in (headers or {}).items():
        if name.lower() == "authorization":
            authorization = value
        else:
            rest[name] = value
    return authorization, rest


class ApiKeyAuth(httpx.Auth):
    """Sends the client's credential only to the API's own origin.

    A request to another origin, such as a deployed agent's URL, goes without
    it. A request that sets its own ``Authorization`` header keeps that header.
    """

    def __init__(self, authorization: str, base_url: str) -> None:
        self._authorization = authorization
        self._origin = url_origin(httpx.URL(base_url))

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        if "Authorization" not in request.headers and url_origin(request.url) == self._origin:
            request.headers["Authorization"] = self._authorization
        yield request


def response_text(resp: httpx.Response) -> str:
    """Error body of a response, including one opened with ``stream=True``.

    Reading ``.text`` before ``read()`` raises ``ResponseNotRead`` and hides
    the status the server actually returned.
    """
    if not resp.is_stream_consumed:
        resp.read()
    return resp.text


async def aresponse_text(resp: httpx.Response) -> str:
    """Async form of :func:`response_text`."""
    if not resp.is_stream_consumed:
        await resp.aread()
    return resp.text


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
