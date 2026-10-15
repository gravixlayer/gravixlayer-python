"""Storage mounts resource for the asynchronous GravixLayer client.

Same endpoints and semantics as :mod:`gravixlayer.resources.storage`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from urllib.parse import quote

from ..types.runtime import _validate_runtime_id
from ..types.storage import (
    BucketLink,
    BucketLinkList,
    LINK_PROVIDERS,
    RuntimeMount,
    RuntimeMountList,
    StorageBucket,
    StorageBucketList,
    build_mount_spec,
)


class AsyncStorageBuckets:
    """Managed buckets at ``client.storage.buckets``."""

    def __init__(self, client):
        self._client = client

    async def _req(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kw):
        return await self._client._make_request(
            method, endpoint, data, _service="v1/agents", **kw
        )

    async def create(
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
        resp = await self._req("POST", "buckets", body)
        return StorageBucket.from_api(resp.json()["bucket"])

    async def list(self, project_id: Optional[str] = None) -> StorageBucketList:
        """List managed buckets, optionally project-scoped."""
        endpoint = "buckets"
        if project_id:
            endpoint = f"buckets?project_id={project_id}"
        data = (await self._req("GET", endpoint)).json()
        buckets = [StorageBucket.from_api(b) for b in (data.get("buckets") or [])]
        return StorageBucketList(buckets=buckets, total=int(data.get("total", len(buckets))))

    async def get(self, id_or_name: str) -> StorageBucket:
        """Fetch one bucket by id or name."""
        resp = await self._req("GET", f"buckets/{quote(id_or_name, safe='-_.')}")
        return StorageBucket.from_api(resp.json()["bucket"])

    async def delete(self, bucket_id: str) -> bool:
        """Delete a managed bucket by id. The API refuses while it is mounted."""
        if not bucket_id or not bucket_id.strip():
            raise ValueError("bucket id is required")
        data = (await self._req("DELETE", f"buckets/{quote(bucket_id, safe='-_.')}")).json()
        return bool(data.get("deleted", True))


class AsyncBucketLinks:
    """Bucket links at ``client.storage.links``."""

    def __init__(self, client):
        self._client = client

    async def _req(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kw):
        return await self._client._make_request(
            method, endpoint, data, _service="v1/agents", **kw
        )

    async def create(
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
    ) -> BucketLink:
        """Link an existing bucket. See :meth:`BucketLinks.create`."""
        if not name or not name.strip():
            raise ValueError("link name is required")
        if not bucket or not bucket.strip():
            raise ValueError("link bucket is required")
        if provider not in LINK_PROVIDERS:
            raise ValueError(f"provider must be one of {LINK_PROVIDERS}, got {provider!r}")
        if auth_mode not in ("static", "oidc"):
            raise ValueError(f"auth_mode must be 'static' or 'oidc', got {auth_mode!r}")
        if endpoint is not None:
            if not endpoint.lower().startswith("https://"):
                raise ValueError("endpoint must be an https:// URL")
            if provider == "s3":
                raise ValueError("endpoint is for s3_compatible links only")
        if provider == "s3_compatible" and endpoint is None:
            raise ValueError("s3_compatible links need an https endpoint")
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

        body: Dict[str, Any] = {
            "name": name,
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
            ("project_id", project_id),
        ):
            if value is not None:
                body[key] = value
        resp = await self._req("POST", "bucket-links", body)
        return BucketLink.from_api(resp.json()["link"])

    async def list(self, project_id: Optional[str] = None) -> BucketLinkList:
        """List bucket links, optionally project-scoped."""
        endpoint = "bucket-links"
        if project_id:
            endpoint = f"bucket-links?project_id={project_id}"
        data = (await self._req("GET", endpoint)).json()
        links = [BucketLink.from_api(l) for l in (data.get("links") or [])]
        return BucketLinkList(links=links, total=int(data.get("total", len(links))))

    async def get(self, id_or_name: str) -> BucketLink:
        """Fetch one link by id or name."""
        resp = await self._req("GET", f"bucket-links/{quote(id_or_name, safe='-_.')}")
        return BucketLink.from_api(resp.json()["link"])

    async def verify(self, link_id: str) -> BucketLink:
        """Probe the link's credentials against the provider."""
        if not link_id or not link_id.strip():
            raise ValueError("link id is required")
        resp = await self._req("POST", f"bucket-links/{quote(link_id, safe='-_.')}/verify")
        return BucketLink.from_api(resp.json()["link"])

    async def delete(self, link_id: str) -> bool:
        """Delete a link. The API refuses while a runtime mounts it."""
        if not link_id or not link_id.strip():
            raise ValueError("link id is required")
        data = (await self._req("DELETE", f"bucket-links/{quote(link_id, safe='-_.')}")).json()
        return bool(data.get("deleted", True))


class AsyncRuntimeMounts:
    """Mounts on a runtime: ``client.storage.mounts`` or ``sandbox.mounts``."""

    def __init__(self, client):
        self._client = client

    async def _req(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kw):
        return await self._client._make_request(
            method, endpoint, data, _service="v1/agents", **kw
        )

    async def attach(self, runtime_id: str, mount: Dict[str, Any]) -> RuntimeMount:
        """Attach a bucket, link, or git mount to a running runtime."""
        _validate_runtime_id(runtime_id)
        body = build_mount_spec(mount)
        resp = await self._req("POST", f"runtime/{runtime_id}/mounts", body)
        return RuntimeMount.from_api(resp.json()["attachment"])

    async def list(self, runtime_id: str) -> RuntimeMountList:
        """List a runtime's mounts and their states."""
        _validate_runtime_id(runtime_id)
        data = (await self._req("GET", f"runtime/{runtime_id}/mounts")).json()
        mounts = [RuntimeMount.from_api(m) for m in (data.get("mounts") or [])]
        return RuntimeMountList(mounts=mounts)

    async def detach(self, runtime_id: str, attachment_id: str) -> bool:
        """Detach a mount by attachment id."""
        _validate_runtime_id(runtime_id)
        if not attachment_id or "/" in attachment_id:
            raise ValueError("attachment id is required")
        data = (
            await self._req("DELETE", f"runtime/{runtime_id}/mounts/{quote(attachment_id, safe='-_.')}")
        ).json()
        return bool(data.get("detached", True))


class AsyncStorage:
    """Storage surface at ``client.storage``."""

    def __init__(self, client):
        self._client = client
        self.buckets = AsyncStorageBuckets(client)
        self.links = AsyncBucketLinks(client)
        self.mounts = AsyncRuntimeMounts(client)
