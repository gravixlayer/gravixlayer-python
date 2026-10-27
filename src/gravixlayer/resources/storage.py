"""Storage mounts resource for the synchronous client.

Maps to the storage API:

    POST   /v1/agents/buckets
    GET    /v1/agents/buckets
    GET    /v1/agents/buckets/:id
    POST   /v1/agents/buckets/:id/verify
    DELETE /v1/agents/buckets/:id
    POST   /v1/agents/runtime/:id/mounts
    GET    /v1/agents/runtime/:id/mounts
    DELETE /v1/agents/runtime/:id/mounts/:attachment_id

A bucket is S3 or S3-compatible object storage. `create` provisions a managed
bucket; `connect` registers a bucket the account already owns. Mounts always
reference `bucket` by id or name. Credentials are secret-provider references
and resolve server-side; they never pass through the SDK.

Example:
    >>> client = GravixLayer()
    >>> bucket = client.storage.buckets.create("datasets")
    >>> sandbox = client.runtime.create(
    ...     mounts=[{"kind": "bucket", "path": "/mnt/data", "mode": "rw",
    ...              "bucket": bucket.id}],
    ... )
    >>> sandbox.mounts.list()
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from urllib.parse import quote

from ..types.runtime import _validate_runtime_id
from ..types.storage import (
    BUCKET_PROVIDERS,
    RuntimeMount,
    RuntimeMountList,
    StorageBucket,
    StorageBucketList,
    build_mount_spec,
)


def _validate_external(
    provider: str,
    auth_mode: str,
    endpoint: Optional[str],
    prefix: Optional[str],
    secret_provider_id: Optional[str],
    access_key_secret: Optional[str],
    secret_key_secret: Optional[str],
    role_arn: Optional[str],
    external_id: Optional[str],
) -> None:
    if provider not in BUCKET_PROVIDERS:
        raise ValueError(f"provider must be one of {BUCKET_PROVIDERS}, got {provider!r}")
    if auth_mode not in ("static", "oidc"):
        raise ValueError(f"auth_mode must be 'static' or 'oidc', got {auth_mode!r}")
    if endpoint is not None:
        if not endpoint.lower().startswith("https://"):
            raise ValueError("endpoint must be an https:// URL")
        if provider == "s3":
            raise ValueError("endpoint is for s3_compatible buckets only")
    if provider == "s3_compatible" and endpoint is None:
        raise ValueError("s3_compatible buckets need an https endpoint")
    if auth_mode == "oidc" and provider != "s3":
        raise ValueError("oidc auth is s3-only")
    if auth_mode == "static":
        if not (secret_provider_id and access_key_secret and secret_key_secret):
            raise ValueError(
                "static auth needs secret_provider_id, access_key_secret, "
                "and secret_key_secret"
            )
    elif not (role_arn and external_id):
        raise ValueError("oidc auth needs role_arn and external_id")
    if prefix is not None and (prefix.startswith("/") or ".." in prefix.split("/")):
        raise ValueError('prefix must be relative — no leading "/" or ".." segments')


class StorageBuckets:
    """Buckets at ``client.storage.buckets``."""

    def __init__(self, client):
        self._client = client

    def _req(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kw):
        return self._client._make_request(method, endpoint, data, _service="v1/agents", **kw)

    def create(
        self,
        name: str,
        region: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> StorageBucket:
        """Create a managed bucket."""
        if not name or not name.strip():
            raise ValueError("bucket name is required")
        body: Dict[str, Any] = {"name": name}
        if region:
            body["region"] = region
        if project_id:
            body["project_id"] = project_id
        resp = self._req("POST", "buckets", body)
        return StorageBucket.from_api(resp.json()["bucket"])

    def connect(
        self,
        name: str,
        bucket: str,
        provider: str = "s3",
        prefix: Optional[str] = None,
        region: Optional[str] = None,
        endpoint: Optional[str] = None,
        path_style: Optional[bool] = None,
        auth_mode: str = "static",
        secret_provider_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        secret_key_secret: Optional[str] = None,
        session_token_secret: Optional[str] = None,
        role_arn: Optional[str] = None,
        external_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> StorageBucket:
        """Connect an existing S3 or S3-compatible bucket.

        ``auth_mode="static"`` references secrets in a provider
        (``secret_provider_id`` + ``*_secret`` key names). ``auth_mode="oidc"``
        assumes ``role_arn`` + ``external_id`` on each use.
        """
        if not name or not name.strip():
            raise ValueError("bucket name is required")
        if not bucket or not bucket.strip():
            raise ValueError("bucket is required")
        _validate_external(
            provider,
            auth_mode,
            endpoint,
            prefix,
            secret_provider_id,
            access_key_secret,
            secret_key_secret,
            role_arn,
            external_id,
        )
        external: Dict[str, Any] = {
            "provider": provider,
            "bucket": bucket,
            "auth_mode": auth_mode,
        }
        for key, value in (
            ("prefix", prefix),
            ("region", region),
            ("endpoint", endpoint),
            ("path_style", path_style),
            ("secret_provider_id", secret_provider_id),
            ("access_key_secret", access_key_secret),
            ("secret_key_secret", secret_key_secret),
            ("session_token_secret", session_token_secret),
            ("role_arn", role_arn),
            ("external_id", external_id),
        ):
            if value is not None:
                external[key] = value
        body: Dict[str, Any] = {"name": name, "external": external}
        if project_id:
            body["project_id"] = project_id
        resp = self._req("POST", "buckets", body)
        return StorageBucket.from_api(resp.json()["bucket"])

    def list(self, project_id: Optional[str] = None) -> StorageBucketList:
        """List buckets, optionally project-scoped."""
        endpoint = "buckets"
        if project_id:
            endpoint = f"buckets?project_id={project_id}"
        data = self._req("GET", endpoint).json()
        buckets = [StorageBucket.from_api(b) for b in (data.get("buckets") or [])]
        return StorageBucketList(buckets=buckets, total=int(data.get("total", len(buckets))))

    def get(self, id_or_name: str) -> StorageBucket:
        """Fetch one bucket by id or name."""
        resp = self._req("GET", f"buckets/{quote(id_or_name, safe='-_.')}")
        return StorageBucket.from_api(resp.json()["bucket"])

    def verify(self, bucket_id: str) -> StorageBucket:
        """Probe an external bucket's credentials against the provider."""
        if not bucket_id or not bucket_id.strip():
            raise ValueError("bucket id is required")
        resp = self._req("POST", f"buckets/{quote(bucket_id, safe='-_.')}/verify")
        return StorageBucket.from_api(resp.json()["bucket"])

    def delete(self, bucket_id: str) -> bool:
        """Delete or disconnect a bucket by id. The API refuses mounted buckets."""
        if not bucket_id or not bucket_id.strip():
            raise ValueError("bucket id is required")
        data = self._req("DELETE", f"buckets/{quote(bucket_id, safe='-_.')}").json()
        return bool(data.get("deleted", True))


class RuntimeMounts:
    """Mounts on a runtime: ``client.storage.mounts`` or ``sandbox.mounts``."""

    def __init__(self, client):
        self._client = client

    def _req(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kw):
        return self._client._make_request(method, endpoint, data, _service="v1/agents", **kw)

    def attach(
        self,
        runtime_id: str,
        mount: Dict[str, Any],
    ) -> RuntimeMount:
        """Attach a bucket or git mount to a running runtime."""
        _validate_runtime_id(runtime_id)
        body = build_mount_spec(mount)
        resp = self._req("POST", f"runtime/{runtime_id}/mounts", body)
        return RuntimeMount.from_api(resp.json()["attachment"])

    def list(self, runtime_id: str) -> RuntimeMountList:
        """List a runtime's mounts and their states."""
        _validate_runtime_id(runtime_id)
        resp = self._req("GET", f"runtime/{runtime_id}/mounts")
        data = resp.json()
        mounts = [RuntimeMount.from_api(m) for m in (data.get("mounts") or [])]
        return RuntimeMountList(mounts=mounts)

    def detach(self, runtime_id: str, attachment_id: str) -> bool:
        """Detach a mount by attachment id."""
        _validate_runtime_id(runtime_id)
        if not attachment_id or "/" in attachment_id:
            raise ValueError("attachment id is required")
        data = self._req("DELETE", f"runtime/{runtime_id}/mounts/{quote(attachment_id, safe='-_.')}").json()
        return bool(data.get("detached", True))


class Storage:
    """Storage surface at ``client.storage``."""

    def __init__(self, client):
        self._client = client
        self.buckets = StorageBuckets(client)
        self.mounts = RuntimeMounts(client)
