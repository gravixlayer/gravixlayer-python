from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Mapping, Optional, Tuple, TypeVar
from urllib.parse import urlencode

T = TypeVar("T")

_SSE_PREFIX = "data:"
_SSE_PREFIX_B = b"data:"
_SSE_PREFIX_LEN = 5


def iter_sse_payloads(lines: Any) -> Iterator[str]:
    """Yield the JSON body of each ``data:`` frame in an SSE line iterator.

    Skips comments, empty lines, and non-data frames without decoding them when
    the transport already handed us bytes.
    """
    for line in lines:
        if not line:
            continue
        if isinstance(line, bytes):
            if not line.startswith(_SSE_PREFIX_B):
                continue
            payload = line[_SSE_PREFIX_LEN:].strip().decode("utf-8", errors="replace")
        else:
            if not line.startswith(_SSE_PREFIX):
                continue
            payload = line[_SSE_PREFIX_LEN:].strip()
        if payload:
            yield payload


async def aiter_sse_payloads(lines: Any) -> AsyncIterator[str]:
    """Async counterpart of :func:`iter_sse_payloads`."""
    async for line in lines:
        if not line:
            continue
        if isinstance(line, bytes):
            if not line.startswith(_SSE_PREFIX_B):
                continue
            payload = line[_SSE_PREFIX_LEN:].strip().decode("utf-8", errors="replace")
        else:
            if not line.startswith(_SSE_PREFIX):
                continue
            payload = line[_SSE_PREFIX_LEN:].strip()
        if payload:
            yield payload


def normalize_runtime_api_payload(data: Dict[str, Any]) -> None:
    """Map Gravix Layer API JSON keys to SDK ``Runtime`` field names.

    The API may return ``id``, ``compute_provider``, ``compute_region``, and ``tags``;
    the Python model expects ``runtime_id``, ``cloud``, ``region``, and ``metadata``.
    Mutates *data* in place; safe to call on responses that already use SDK names.
    """
    if data.get("runtime_id") is None:
        rid = data.get("id")
        if rid is not None:
            data["runtime_id"] = rid
    if data.get("cloud") is None:
        cloud = data.get("compute_provider")
        if cloud is None:
            cloud = data.get("provider")
        if cloud is not None:
            data["cloud"] = cloud
    if data.get("region") is None:
        region = data.get("compute_region")
        if region is not None:
            data["region"] = region
    if data.get("metadata") is None:
        tags = data.get("tags")
        if tags is not None:
            data["metadata"] = tags


def build_list_endpoint(
    resource: str,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    extra_params: Optional[Dict[str, Any]] = None,
) -> str:
    """Build an endpoint with optional pagination and extra query parameters."""
    params: Dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if extra_params:
        for key, value in extra_params.items():
            if value is not None:
                params[key] = value

    return f"{resource}?{urlencode(params)}" if params else resource


def parse_total_items(
    payload: Mapping[str, Any],
    items_key: str,
    parser: Callable[[Any], T],
    total_key: str = "total",
) -> Tuple[List[T], int]:
    """Parse list-like payloads with a total count field."""
    items = [parser(item) for item in payload.get(items_key, ())]
    return items, payload.get(total_key, len(items))


def parse_paginated_items(
    payload: Mapping[str, Any],
    items_key: str,
    parser: Callable[[Any], T],
    default_limit: int,
    default_offset: int,
) -> Tuple[List[T], int, int]:
    """Parse paginated payloads that return limit/offset metadata."""
    items = [parser(item) for item in payload.get(items_key, ())]
    return (
        items,
        payload.get("limit", default_limit),
        payload.get("offset", default_offset),
    )
