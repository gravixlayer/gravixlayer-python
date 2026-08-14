"""Type definitions for the named snapshot catalog API."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Snapshot:
    """A project-scoped named snapshot from GET/POST /v1/agents/snapshots."""

    id: str
    name: str
    description: str
    kind: str
    state: str
    cloud: str
    region: str
    vcpu_count: int
    memory_mb: int
    disk_size_mb: int
    visibility: str
    is_active: bool
    source: str
    source_template_id: str
    distribution_status: str
    size_bytes: int
    created_at: str
    updated_at: str
    source_runtime_id: Optional[str] = None
    last_used_at: Optional[str] = None


@dataclass
class SnapshotListResponse:
    """Response from GET /v1/agents/snapshots."""

    snapshots: List[Snapshot]
    limit: int
    offset: int
    total: int


@dataclass
class SnapshotDeleteResponse:
    """Result of DELETE /v1/agents/snapshots/:id (HTTP 204 No Content)."""

    snapshot_id: str
    deleted: bool = True


def _parse_snapshot(data: Dict[str, Any]) -> Snapshot:
    return Snapshot(
        id=data["id"],
        name=data.get("name", ""),
        description=data.get("description", ""),
        kind=data.get("kind", "cold"),
        state=data.get("state", ""),
        cloud=data.get("cloud") or data.get("provider") or "",
        region=data.get("region", ""),
        vcpu_count=data.get("vcpu_count", 0),
        memory_mb=data.get("memory_mb", 0),
        disk_size_mb=data.get("disk_size_mb", 0),
        visibility=data.get("visibility", "private"),
        is_active=bool(data.get("is_active", False)),
        source=data.get("source", ""),
        source_template_id=data.get("source_template_id", ""),
        source_runtime_id=data.get("source_runtime_id") or None,
        distribution_status=data.get("distribution_status", ""),
        size_bytes=int(data.get("size_bytes") or 0),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        last_used_at=data.get("last_used_at"),
    )
