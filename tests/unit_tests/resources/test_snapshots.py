"""Named snapshot catalog: create, list, activate, restore wiring."""

import httpx
import pytest

from tests.utils import AGENTS_BASE, VALID_UUID

SNAP_BASE = f"{AGENTS_BASE}/snapshots"

_SNAP = {
    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "name": "ckpt-1",
    "description": "",
    "kind": "hot",
    "state": "active",
    "cloud": "aws",
    "region": "us-east-1",
    "vcpu_count": 2,
    "memory_mb": 1024,
    "disk_size_mb": 4096,
    "visibility": "private",
    "is_active": True,
    "source": "runtime",
    "source_template_id": VALID_UUID,
    "source_runtime_id": VALID_UUID,
    "distribution_status": "ready",
    "size_bytes": 1024,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


class TestSnapshots:
    def test_create_defaults_cold(self, client, mock_api):
        body = {**_SNAP, "kind": "cold"}
        mock_api.post(SNAP_BASE).mock(return_value=httpx.Response(201, json=body))
        snap = client.snapshots.create(VALID_UUID, "ckpt-1")
        assert snap.kind == "cold"
        assert b'"kind":"cold"' in mock_api.calls.last.request.content

    def test_create_hot_and_rejects_unknown_kind(self, client, mock_api):
        mock_api.post(SNAP_BASE).mock(return_value=httpx.Response(201, json=_SNAP))
        snap = client.snapshots.create(VALID_UUID, "ckpt-1", kind="HOT")
        assert snap.kind == "hot"
        assert snap.is_active is True
        with pytest.raises(ValueError, match="hot"):
            client.snapshots.create(VALID_UUID, "bad", kind="warm")

    def test_activate_parses_full_snapshot(self, client, mock_api):
        mock_api.post(f"{SNAP_BASE}/ckpt-1/activate").mock(
            return_value=httpx.Response(200, json=_SNAP)
        )
        snap = client.snapshots.activate("ckpt-1")
        assert snap.id == _SNAP["id"]
        assert snap.kind == "hot"
        assert snap.name == "ckpt-1"
        assert snap.is_active is True

    def test_list_filters(self, client, mock_api):
        mock_api.get(url__startswith=SNAP_BASE).mock(
            return_value=httpx.Response(
                200, json={"snapshots": [_SNAP], "total": 1, "limit": 20, "offset": 0}
            )
        )
        listed = client.snapshots.list(kind="hot", runtime_id=VALID_UUID)
        assert listed.total == 1
        assert listed.snapshots[0].kind == "hot"
        assert "kind=hot" in str(mock_api.calls.last.request.url)
