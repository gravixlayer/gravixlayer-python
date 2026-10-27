"""Storage mount types.

A *bucket* is S3 or S3-compatible object storage. The platform can provision
it, or it can connect to a bucket the account already owns. A *mount* attaches
a bucket or git repository to a runtime at a guest path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

BUCKET_PROVIDERS = ("s3", "s3_compatible")

# Mount modes.
MOUNT_RO = "ro"
MOUNT_RW = "rw"

# Attachment lifecycle states.
MOUNT_ATTACHED = "attached"

_MOUNT_FIELDS = frozenset(
    {
        "kind",
        "path",
        "mode",
        "required",
        "bucket",
        "url",
        "git_ref",
        "depth",
        "refresh_seconds",
        "credential_provider",
        "credential_secret",
    }
)
MOUNT_DETACHED = "detached"
MOUNT_FAILED = "failed"


@dataclass
class StorageBucket:
    """An S3 or S3-compatible bucket, managed or externally connected."""

    id: str
    name: str
    source: str  # "managed" | "external"
    provider: str
    region: str
    bucket: str = ""  # provider-side bucket name
    prefix: str = ""
    endpoint: Optional[str] = None
    path_style: bool = False
    auth_mode: str = ""
    status: str = ""
    error: Optional[str] = None
    verify_error: Optional[str] = None
    last_verified_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "StorageBucket":
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            source=data.get("source", "managed"),
            provider=data.get("provider", ""),
            region=data.get("region", ""),
            bucket=data.get("bucket", ""),
            prefix=data.get("prefix", ""),
            endpoint=data.get("endpoint") or None,
            path_style=bool(data.get("path_style", False)),
            auth_mode=data.get("auth_mode", ""),
            status=data.get("status", ""),
            error=data.get("error") or None,
            verify_error=data.get("verify_error") or None,
            last_verified_at=data.get("last_verified_at"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class RuntimeMount:
    """A storage mount attached to a runtime."""

    id: str
    runtime_id: str
    kind: str  # "bucket" | "git"
    mount_path: str
    mode: str = MOUNT_RO
    state: str = ""
    target_id: Optional[str] = None
    error: Optional[str] = None
    provenance: Optional[str] = None  # e.g. the pinned git commit
    created_at: Optional[str] = None
    detached_at: Optional[str] = None

    @property
    def attached(self) -> bool:
        return self.state == MOUNT_ATTACHED

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "RuntimeMount":
        return cls(
            id=data["id"],
            runtime_id=data.get("runtime_id", ""),
            kind=data.get("kind", ""),
            mount_path=data.get("mount_path", ""),
            mode=data.get("mode", MOUNT_RO),
            state=data.get("state", ""),
            target_id=data.get("target_id") or None,
            error=data.get("error") or None,
            provenance=data.get("provenance") or None,
            created_at=data.get("created_at"),
            detached_at=data.get("detached_at"),
        )


@dataclass
class StorageBucketList:
    buckets: List[StorageBucket] = field(default_factory=list)
    total: int = 0


@dataclass
class RuntimeMountList:
    mounts: List[RuntimeMount] = field(default_factory=list)


def build_mount_spec(mount: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a mount request and emit the wire body.

    Raises ``ValueError`` before any request so a bad mount fails the create
    or attach immediately with a precise message.
    """
    if not isinstance(mount, dict):
        raise ValueError("mount must be a dict")
    for key in mount:
        if key not in _MOUNT_FIELDS:
            raise ValueError(f"{key!r} is not a supported mount field")
    kind = str(mount.get("kind", ""))
    if kind not in ("bucket", "git"):
        raise ValueError(f"mount kind must be 'bucket' or 'git', got {kind!r}")

    path = str(mount.get("path", ""))
    if (
        not path.startswith("/")
        or path == "/"
        or path.endswith("/")
        or "//" in path
        or ".." in path.split("/")
        or "\x00" in path
    ):
        raise ValueError(f"mount path must be a normalized absolute path below the guest root, got {path!r}")

    body: Dict[str, Any] = {"kind": kind, "path": path}

    mode = mount.get("mode")
    if mode is not None:
        mode = str(mode).lower()
        if mode not in (MOUNT_RO, MOUNT_RW):
            raise ValueError(f"mount mode must be 'ro' or 'rw', got {mode!r}")
        if kind == "git" and mode == MOUNT_RW:
            raise ValueError("git mounts are read-only")
        body["mode"] = mode

    if mount.get("required") is not None:
        body["required"] = bool(mount["required"])

    if kind == "bucket":
        for stray in (
            "url",
            "git_ref",
            "depth",
            "refresh_seconds",
            "credential_provider",
            "credential_secret",
        ):
            if mount.get(stray) is not None:
                raise ValueError(f"{stray!r} is for git mounts, not bucket")
        bucket = mount.get("bucket")
        if not bucket:
            raise ValueError("a bucket mount needs bucket (id or name)")
        body["bucket"] = bucket
        return body

    if mount.get("bucket") is not None:
        raise ValueError("bucket is for bucket mounts, not git")
    url = str(mount.get("url") or "")
    if not url.lower().startswith("https://"):
        raise ValueError("git mount url must be an https:// clone URL")
    body["url"] = url
    if mount.get("git_ref") is not None:
        body["git_ref"] = mount["git_ref"]
    if mount.get("depth") is not None:
        depth = int(mount["depth"])
        if depth < 0 or depth > 0xFFFFFFFF:
            raise ValueError("git depth must be between 0 and 4294967295")
        body["depth"] = depth
    if mount.get("refresh_seconds") is not None:
        refresh = int(mount["refresh_seconds"])
        if refresh < 0 or refresh > 0xFFFFFFFF:
            raise ValueError("git refresh_seconds must be between 0 and 4294967295")
        body["refresh_seconds"] = refresh
    provider, secret = mount.get("credential_provider"), mount.get("credential_secret")
    if (provider is None) != (secret is None):
        raise ValueError("git credentials need credential_provider and credential_secret")
    if provider is not None:
        body["credential_provider"] = provider
        body["credential_secret"] = secret
    return body
