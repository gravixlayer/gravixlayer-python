"""Named snapshot catalog resource for the asynchronous client."""

from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from .._resource_utils import build_list_endpoint, parse_paginated_items
from ..types.snapshots import (
    Snapshot,
    SnapshotDeleteResponse,
    SnapshotListResponse,
    _parse_snapshot,
)

_SNAPSHOT_CREATE_TIMEOUT = httpx.Timeout(600.0)


def _snapshot_path(ref: str) -> str:
    ref = (ref or "").strip()
    if not ref:
        raise ValueError("snapshot id or name is required")
    return f"snapshots/{quote(ref, safe='-_.')}"


class AsyncSnapshots:
    """Async named snapshot catalog. Mirrors :class:`Snapshots`."""

    def __init__(self, client):
        self.client = client

    async def _make_agents_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        return await self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    async def create(
        self,
        runtime_id: str,
        name: str,
        kind: str = "cold",
        description: Optional[str] = None,
    ) -> Snapshot:
        """Capture a running or paused runtime into the snapshot catalog."""
        payload: Dict[str, Any] = {
            "runtime_id": runtime_id,
            "name": name,
            "kind": kind,
        }
        if description is not None:
            payload["description"] = description
        response = await self._make_agents_request(
            "POST",
            "snapshots",
            payload,
            timeout=_SNAPSHOT_CREATE_TIMEOUT,
        )
        return _parse_snapshot(response.json())

    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
        kind: Optional[str] = None,
        runtime_id: Optional[str] = None,
        state: Optional[str] = None,
        source: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> SnapshotListResponse:
        """List persisted snapshots for the current project."""
        endpoint = build_list_endpoint(
            "snapshots",
            limit=limit,
            offset=offset,
            extra_params={
                "kind": kind,
                "runtime_id": runtime_id,
                "state": state,
                "source": source,
                "project_id": project_id,
            },
        )
        response = await self._make_agents_request("GET", endpoint)
        data = response.json()
        snapshots, page_limit, page_offset = parse_paginated_items(
            data,
            "snapshots",
            _parse_snapshot,
            default_limit=limit,
            default_offset=offset,
        )
        total = data.get("total", len(snapshots))
        return SnapshotListResponse(
            snapshots=snapshots,
            limit=page_limit,
            offset=page_offset,
            total=total,
        )

    async def get(self, snapshot: str) -> Snapshot:
        """Get a snapshot by UUID or project-unique name."""
        response = await self._make_agents_request("GET", _snapshot_path(snapshot))
        return _parse_snapshot(response.json())

    async def activate(self, snapshot: str) -> Snapshot:
        """Mark an inactive snapshot creatable again."""
        response = await self._make_agents_request("POST", f"{_snapshot_path(snapshot)}/activate")
        return _parse_snapshot(response.json())

    async def deactivate(self, snapshot: str) -> Snapshot:
        """Stop new runtime creates from this snapshot."""
        response = await self._make_agents_request("POST", f"{_snapshot_path(snapshot)}/deactivate")
        return _parse_snapshot(response.json())

    async def delete(self, snapshot: str) -> SnapshotDeleteResponse:
        """Delete a private snapshot. Running children keep already-opened files."""
        await self._make_agents_request("DELETE", _snapshot_path(snapshot))
        return SnapshotDeleteResponse(snapshot_id=snapshot, deleted=True)
