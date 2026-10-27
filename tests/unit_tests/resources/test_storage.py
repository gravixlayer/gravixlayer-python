"""Tests for sync and async storage resources.

Covers buckets, runtime mounts, and ``runtime.create(mounts=...)``.
"""

from __future__ import annotations

import json

import httpx
import pytest

from gravixlayer import AsyncGravixLayer, GravixLayer
from gravixlayer.types.storage import (
    RuntimeMount,
    StorageBucket,
    build_mount_spec,
)
from tests.utils import AGENTS_BASE, TEST_API_KEY, TEST_BASE_URL

BUCKET = {
    "id": "bkt-1",
    "name": "datasets",
    "provider": "s3",
    "region": "us-east-1",
    "bucket": "glx-a1b2-datasets",
    "status": "active",
    "error": "",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}

EXTERNAL = {
    "id": "bkt-ext-1",
    "name": "byo-data",
    "source": "external",
    "provider": "s3_compatible",
    "bucket": "acme-data",
    "prefix": "models/",
    "region": "eu-west-1",
    "endpoint": "https://objects.example.com",
    "path_style": True,
    "auth_mode": "static",
    "status": "verified",
    "verify_error": "",
    "last_verified_at": "2026-01-02T00:00:00Z",
    "created_at": "2026-01-01T00:00:00Z",
}

RUNTIME_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

MOUNT = {
    "id": "att-1",
    "runtime_id": RUNTIME_ID,
    "kind": "bucket",
    "target_id": "bkt-1",
    "mount_path": "/mnt/data",
    "mode": "rw",
    "state": "attached",
    "error": "",
    "provenance": "s3://glx-a1b2-datasets",
    "created_at": "2026-01-01T00:00:00Z",
}

BUCKETS_URL = f"{AGENTS_BASE}/buckets"
MOUNTS_URL = f"{AGENTS_BASE}/runtime/{RUNTIME_ID}/mounts"


class TestBuckets:
    def test_create(self, client, mock_api):
        mock_api.post(BUCKETS_URL).mock(return_value=httpx.Response(201, json={"bucket": BUCKET}))
        bucket = client.storage.buckets.create("datasets", region="us-east-1")
        assert isinstance(bucket, StorageBucket)
        assert bucket.id == "bkt-1"
        assert bucket.bucket == "glx-a1b2-datasets"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"name": "datasets", "region": "us-east-1"}

    def test_create_scoped_to_project(self, client, mock_api):
        mock_api.post(BUCKETS_URL).mock(return_value=httpx.Response(201, json={"bucket": BUCKET}))
        client.storage.buckets.create("datasets", project_id="proj-9")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["project_id"] == "proj-9"

    def test_create_rejects_empty_name(self, client, mock_api):
        with pytest.raises(ValueError, match="name"):
            client.storage.buckets.create("  ")
        assert len(mock_api.calls) == 0

    def test_list(self, client, mock_api):
        mock_api.get(BUCKETS_URL).mock(return_value=httpx.Response(200, json={"buckets": [BUCKET], "total": 1}))
        result = client.storage.buckets.list(project_id="proj-1")
        assert result.total == 1
        assert result.buckets[0].name == "datasets"
        assert "project_id=proj-1" in mock_api.calls[-1].request.url.query.decode()

    def test_get_and_delete(self, client, mock_api):
        mock_api.get(f"{BUCKETS_URL}/bkt-1").mock(return_value=httpx.Response(200, json={"bucket": BUCKET}))
        mock_api.delete(f"{BUCKETS_URL}/bkt-1").mock(return_value=httpx.Response(200, json={"deleted": True}))
        assert client.storage.buckets.get("bkt-1").status == "active"
        assert client.storage.buckets.delete("bkt-1") is True


class TestExternalBuckets:
    def test_create_static(self, client, mock_api):
        mock_api.post(BUCKETS_URL).mock(return_value=httpx.Response(201, json={"bucket": EXTERNAL}))
        bucket = client.storage.buckets.connect(
            "byo-data",
            "acme-data",
            provider="s3_compatible",
            prefix="models/",
            region="eu-west-1",
            endpoint="https://objects.example.com",
            path_style=True,
            secret_provider_id="prov-1",
            access_key_secret="AWS_ACCESS_KEY_ID",
            secret_key_secret="AWS_SECRET_ACCESS_KEY",
        )
        assert isinstance(bucket, StorageBucket)
        assert bucket.source == "external"
        assert bucket.path_style is True
        assert bucket.last_verified_at == "2026-01-02T00:00:00Z"
        body = json.loads(mock_api.calls[-1].request.content)
        # Credentials are references only — no secret material leaves.
        assert body["external"]["secret_provider_id"] == "prov-1"
        assert body["external"]["access_key_secret"] == "AWS_ACCESS_KEY_ID"
        assert "AKIA" not in json.dumps(body)

    def test_create_oidc(self, client, mock_api):
        mock_api.post(BUCKETS_URL).mock(return_value=httpx.Response(201, json={"bucket": EXTERNAL}))
        client.storage.buckets.connect(
            "byo-data",
            "acme-data",
            auth_mode="oidc",
            role_arn="arn:aws:iam::1234:role/data-read",
            external_id="ext-9",
        )
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["external"]["auth_mode"] == "oidc"
        assert body["external"]["role_arn"].endswith("data-read")

    def test_rejects_non_https_endpoint(self, client, mock_api):
        with pytest.raises(ValueError, match="https"):
            client.storage.buckets.connect("x", "b", provider="s3_compatible", endpoint="http://a")
        assert len(mock_api.calls) == 0

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"provider": "s3", "endpoint": "https://x"},
            {"provider": "s3_compatible"},
            {"provider": "s3"},  # static without secret refs
            {
                "provider": "s3",
                "auth_mode": "oidc",
                "role_arn": "arn:aws:iam::1:role/r",
            },
            {
                "provider": "s3_compatible",
                "endpoint": "https://x",
                "auth_mode": "oidc",
                "role_arn": "r",
                "external_id": "e",
            },
            {
                "provider": "s3",
                "secret_provider_id": "p",
                "access_key_secret": "a",
                "secret_key_secret": "s",
                "prefix": "/abs",
            },
        ],
        ids=str,
    )
    def test_rejects_bad_external_combinations(self, client, mock_api, kwargs):
        with pytest.raises(ValueError):
            client.storage.buckets.connect("x", "b", **kwargs)
        assert len(mock_api.calls) == 0

    def test_verify_and_delete(self, client, mock_api):
        mock_api.post(f"{BUCKETS_URL}/bkt-ext-1/verify").mock(
            return_value=httpx.Response(200, json={"bucket": EXTERNAL})
        )
        mock_api.delete(f"{BUCKETS_URL}/bkt-ext-1").mock(return_value=httpx.Response(200, json={"deleted": True}))
        assert client.storage.buckets.verify("bkt-ext-1").status == "verified"
        assert client.storage.buckets.delete("bkt-ext-1") is True

    def test_list(self, client, mock_api):
        mock_api.get(BUCKETS_URL).mock(return_value=httpx.Response(200, json={"buckets": [EXTERNAL], "total": 1}))
        result = client.storage.buckets.list()
        assert result.total == 1
        assert result.buckets[0].endpoint == "https://objects.example.com"


class TestBuildMountSpec:
    def test_bucket_by_id(self):
        assert build_mount_spec({"kind": "bucket", "path": "/mnt/data", "mode": "rw", "bucket": "bkt-1"}) == {
            "kind": "bucket",
            "path": "/mnt/data",
            "mode": "rw",
            "bucket": "bkt-1",
        }

    def test_git_full(self):
        assert build_mount_spec(
            {
                "kind": "git",
                "path": "/mnt/repo",
                "url": "https://example.com/r.git",
                "git_ref": "main",
                "depth": 1,
                "refresh_seconds": 300,
                "credential_provider": "prov-1",
                "credential_secret": "GIT_TOKEN",
            }
        ) == {
            "kind": "git",
            "path": "/mnt/repo",
            "url": "https://example.com/r.git",
            "git_ref": "main",
            "depth": 1,
            "refresh_seconds": 300,
            "credential_provider": "prov-1",
            "credential_secret": "GIT_TOKEN",
        }

    @pytest.mark.parametrize(
        "mount",
        [
            {"kind": "bucket", "path": "/m", "bucket": "a", "legacy": "b"},
            {"kind": "bucket", "path": "/m"},
            {"kind": "git", "path": "/m", "url": "https://x/y.git", "mode": "rw"},
            {"kind": "git", "path": "/m", "url": "git@x:y"},
            {"kind": "git", "path": "/m"},
            {"kind": "bucket", "path": "rel", "bucket": "a"},
            {"kind": "bucket", "path": "/", "bucket": "a"},
            {"kind": "bucket", "path": "/a/../x", "bucket": "a"},
            {"kind": "bucket", "path": "/m/", "bucket": "a"},
            {"kind": "bucket", "path": "/m//x", "bucket": "a"},
            {"kind": "git", "path": "/m", "url": "https://x/y.git", "depth": 4294967296},
            {"kind": "bucket", "path": "/m", "bucket": "a", "url": "https://x/y.git"},
            {"kind": "git", "path": "/m", "url": "https://x/y.git", "bucket": "a"},
            {"kind": "bucket", "path": "/m", "bucket": "a", "credential_providers": "x"},
            {"kind": "bucket", "path": "/m", "bucket": "a", "credential_provider": "p", "credential_secret": "s"},
            {"kind": "bucket", "path": "/m", "bucket": "a", "typo_key": "x"},
            {"kind": "git", "path": "/m", "url": "https://x/y.git", "credential_provider": "p"},
            {"kind": "git", "path": "/m", "url": "https://x/y.git", "depth": -1},
            {"kind": "bucket", "path": "/m", "bucket": "a", "mode": "exec"},
        ],
        ids=lambda m: str(sorted(m.items()))[:40],
    )
    def test_rejected_before_request(self, mount):
        with pytest.raises(ValueError):
            build_mount_spec(mount)


class TestRuntimeMounts:
    def test_attach_list_detach(self, client, mock_api):
        mock_api.post(MOUNTS_URL).mock(return_value=httpx.Response(201, json={"attachment": MOUNT}))
        mock_api.get(MOUNTS_URL).mock(return_value=httpx.Response(200, json={"mounts": [MOUNT]}))
        mock_api.delete(f"{MOUNTS_URL}/att-1").mock(return_value=httpx.Response(200, json={"detached": True}))

        mount = client.storage.mounts.attach(
            RUNTIME_ID,
            {"kind": "bucket", "path": "/mnt/data", "mode": "rw", "bucket": "bkt-1"},
        )
        assert isinstance(mount, RuntimeMount)
        assert mount.attached is True
        assert mount.provenance == "s3://glx-a1b2-datasets"

        listed = client.storage.mounts.list(RUNTIME_ID)
        assert listed.mounts[0].mount_path == "/mnt/data"
        assert client.storage.mounts.detach(RUNTIME_ID, "att-1") is True

        methods = [c.request.method for c in mock_api.calls]
        assert methods == ["POST", "GET", "DELETE"]

    def test_attach_validates_locally(self, client, mock_api):
        with pytest.raises(ValueError):
            client.storage.mounts.attach(RUNTIME_ID, {"kind": "git", "path": "/m", "url": "ssh://x"})
        assert len(mock_api.calls) == 0

    def test_create_with_mounts(self, client, mock_api):
        from tests.utils import make_runtime_response

        mock_api.post(f"{AGENTS_BASE}/runtime").mock(return_value=httpx.Response(200, json=make_runtime_response()))
        client.runtime.create(
            mounts=[
                {"kind": "bucket", "path": "/mnt/data", "mode": "rw", "bucket": "bkt-1"},
                {"kind": "git", "path": "/mnt/repo", "url": "https://example.com/r.git"},
            ]
        )
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["mounts"] == [
            {"kind": "bucket", "path": "/mnt/data", "mode": "rw", "bucket": "bkt-1"},
            {"kind": "git", "path": "/mnt/repo", "url": "https://example.com/r.git"},
        ]

    def test_create_rejects_bad_mount_before_request(self, client, mock_api):
        with pytest.raises(ValueError):
            client.runtime.create(mounts=[{"kind": "bucket", "path": "rel", "bucket": "a"}])
        assert len(mock_api.calls) == 0


@pytest.mark.asyncio
class TestAsyncStorage:
    async def test_bucket_lifecycle(self, mock_api):
        mock_api.post(BUCKETS_URL).mock(return_value=httpx.Response(201, json={"bucket": BUCKET}))
        mock_api.get(BUCKETS_URL).mock(return_value=httpx.Response(200, json={"buckets": [BUCKET], "total": 1}))
        mock_api.get(f"{BUCKETS_URL}/bkt-1").mock(return_value=httpx.Response(200, json={"bucket": BUCKET}))
        mock_api.delete(f"{BUCKETS_URL}/bkt-1").mock(return_value=httpx.Response(200, json={"deleted": True}))
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as c:
            bucket = await c.storage.buckets.create("datasets", region="us-east-1")
            assert bucket.id == "bkt-1"
            assert (await c.storage.buckets.list()).total == 1
            assert (await c.storage.buckets.get("bkt-1")).status == "active"
            assert await c.storage.buckets.delete("bkt-1") is True

    async def test_external_verify(self, mock_api):
        mock_api.post(f"{BUCKETS_URL}/bkt-ext-1/verify").mock(
            return_value=httpx.Response(200, json={"bucket": EXTERNAL})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as c:
            bucket = await c.storage.buckets.verify("bkt-ext-1")
            assert bucket.status == "verified"

    async def test_mounts(self, mock_api):
        mock_api.post(MOUNTS_URL).mock(return_value=httpx.Response(201, json={"attachment": MOUNT}))
        mock_api.get(MOUNTS_URL).mock(return_value=httpx.Response(200, json={"mounts": [MOUNT]}))
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as c:
            mount = await c.storage.mounts.attach(
                RUNTIME_ID,
                {"kind": "bucket", "path": "/mnt/data", "bucket": "bkt-1"},
            )
            assert mount.attached is True
            listed = await c.storage.mounts.list(RUNTIME_ID)
            assert len(listed.mounts) == 1

    async def test_create_with_mounts(self, mock_api):
        from tests.utils import make_runtime_response

        mock_api.post(f"{AGENTS_BASE}/runtime").mock(return_value=httpx.Response(200, json=make_runtime_response()))
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as c:
            await c.runtime.create(mounts=[{"kind": "bucket", "path": "/m", "bucket": "bkt-1"}])
            body = json.loads(mock_api.calls[-1].request.content)
            assert body["mounts"][0]["bucket"] == "bkt-1"
