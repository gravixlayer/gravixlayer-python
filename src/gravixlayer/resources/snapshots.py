"""Named snapshot catalog resource for the synchronous client."""

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

# Capture pauses the guest, packs overlay extents, and (for hot) writes a Full
# Firecracker snapshot. The control plane uses a 10-minute gRPC deadline.
_SNAPSHOT_CREATE_TIMEOUT = httpx.Timeout(600.0)


def _snapshot_path(ref: str) -> str:
    ref = (ref or "").strip()
    if not ref:
        raise ValueError("snapshot id or name is required")
    return f"snapshots/{quote(ref, safe='-_.')}"


class Snapshots:
    """Named snapshot catalog.

    Exposes methods for the Gravix Layer snapshot API:
        POST   /v1/agents/snapshots
        GET    /v1/agents/snapshots
        GET    /v1/agents/snapshots/:id_or_name
        POST   /v1/agents/snapshots/:id/activate
        POST   /v1/agents/snapshots/:id/deactivate
        DELETE /v1/agents/snapshots/:id_or_name

    Example:
        >>> from gravixlayer import GravixLayer
        >>> client = GravixLayer(api_key="...")
        >>> snap = client.snapshots.create(runtime_id=rid, name="ckpt-1", kind="hot")
        >>> sandbox = client.runtime.create(snapshot="ckpt-1")
    """

    def __init__(self, client):
        self.client = client

    def _make_agents_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        return self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    def create(
        self,
        runtime_id: str,
        name: str,
        kind: str = "cold",
        description: Optional[str] = None,
    ) -> Snapshot:
        """Capture a running or paused runtime into the snapshot catalog.

        Args:
            runtime_id: Source runtime UUID.
            name: Project-unique snapshot name.
            kind: ``hot`` (memory + disk) or ``cold`` (disk only). Defaults to cold.
            description: Optional description.
        """
        payload: Dict[str, Any] = {
            "runtime_id": runtime_id,
            "name": name,
            "kind": kind,
        }
        if description is not None:
            payload["description"] = description
        response = self._make_agents_request(
            "POST",
            "snapshots",
            payload,
            timeout=_SNAPSHOT_CREATE_TIMEOUT,
        )
        return _parse_snapshot(response.json())

    def list(
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
        response = self._make_agents_request("GET", endpoint)
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

    def get(self, snapshot: str) -> Snapshot:
        """Get a snapshot by UUID or project-unique name."""
        response = self._make_agents_request("GET", _snapshot_path(snapshot))
        return _parse_snapshot(response.json())

    def activate(self, snapshot: str) -> Snapshot:
        """Mark an inactive snapshot creatable again."""
        response = self._make_agents_request("POST", f"{_snapshot_path(snapshot)}/activate")
        return _parse_snapshot(response.json())

    def deactivate(self, snapshot: str) -> Snapshot:
        """Stop new runtime creates from this snapshot."""
        response = self._make_agents_request("POST", f"{_snapshot_path(snapshot)}/deactivate")
        return _parse_snapshot(response.json())

    def delete(self, snapshot: str) -> SnapshotDeleteResponse:
        """Delete a private snapshot. Running children keep already-opened files."""
        self._make_agents_request("DELETE", _snapshot_path(snapshot))
        return SnapshotDeleteResponse(snapshot_id=snapshot, deleted=True)
