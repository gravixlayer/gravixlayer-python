from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, TypeVar
from urllib.parse import urlencode

T = TypeVar("T")


def normalize_runtime_api_payload(data: Dict[str, Any]) -> None:
    """Map control-plane ``RuntimeResponse`` JSON keys to SDK ``Runtime`` field names.

    Handlers emit ``id``, ``compute_provider``, ``compute_region``, and ``tags``;
    the Python model expects ``runtime_id``, ``provider``, ``region``, and ``metadata``.
    Mutates *data* in place; safe to call on responses that already use SDK names.
    """
    if data.get("runtime_id") is None and data.get("id") is not None:
        data["runtime_id"] = data["id"]
    if data.get("provider") is None and data.get("compute_provider") is not None:
        data["provider"] = data["compute_provider"]
    if data.get("region") is None and data.get("compute_region") is not None:
        data["region"] = data["compute_region"]
    if data.get("metadata") is None and data.get("tags") is not None:
        data["metadata"] = data["tags"]


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
