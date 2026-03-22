from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, TypeVar
from urllib.parse import urlencode

T = TypeVar("T")


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
