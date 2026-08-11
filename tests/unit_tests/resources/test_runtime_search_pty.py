"""
Tests for native filesystem search (``client.runtime.file.find`` / ``.replace``)
and the connection-managing PTY handles (``client.runtime.pty.handle``).
"""

import base64
import json

import httpx
import pytest

from tests.utils import AGENTS_BASE, TEST_API_KEY, TEST_BASE_URL, VALID_UUID

from gravixlayer import AsyncGravixLayer
from gravixlayer.types.runtime import (
    FileFindResponse,
    FileReplaceResponse,
    FileSearchMatch,
    PtySession,
)


SB = f"{AGENTS_BASE}/runtime"
SESSION_ID = "pty-0001"

_FIND_OK = {
    "success": True,
    "matches": [
        {"path": "/workspace/a.py", "line": 3, "column": 5, "content": "x = TODO"},
        {"path": "/workspace/b.py", "line": 11, "column": 1, "content": "TODO later"},
    ],
    "truncated": False,
    "files_scanned": 42,
}

_REPLACE_OK = {
    "success": True,
    "files": [
        {"path": "/workspace/a.py", "replacements": 2},
        {"path": "/workspace/b.py", "replacements": 1},
    ],
    "total_replacements": 3,
    "files_scanned": 42,
    "dry_run": False,
}


def _sse(*frames: dict) -> str:
    return "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames)


def _pty_data(payload: bytes) -> dict:
    return {"type": "data", "data": base64.b64encode(payload).decode("ascii")}


def _session_json(status: str = "running", exit_code: int = 0) -> dict:
    return {
        "session_id": SESSION_ID,
        "runtime_id": VALID_UUID,
        "pid": 1234,
        "shell": "/bin/bash",
        "args": [],
        "working_dir": "/workspace",
        "cols": 80,
        "rows": 24,
        "status": status,
        "exit_code": exit_code,
    }


# ===================================================================
# Sync — Filesystem Search
# ===================================================================


class TestSyncRuntimeFind:
    def test_find_by_pattern_and_glob(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/find").mock(
            return_value=httpx.Response(200, json=_FIND_OK)
        )
        result = client.runtime.file.find(VALID_UUID, "/workspace", "TODO", glob="*.py")
        assert isinstance(result, FileFindResponse)
        assert result.success is True
        assert len(result) == 2
        assert isinstance(result.matches[0], FileSearchMatch)
        assert result.matches[0].path == "/workspace/a.py"
        assert result.matches[0].line == 3
        assert result.files_scanned == 42
        assert [m.line for m in result] == [3, 11]

        body = json.loads(mock_api.calls[-1].request.content)
        assert body["path"] == "/workspace"
        assert body["pattern"] == "TODO"
        assert body["glob"] == "*.py"
        assert body["regex"] is False
        assert body["case_sensitive"] is False
        assert body["include_hidden"] is False

    def test_find_glob_only_omits_pattern(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/find").mock(
            return_value=httpx.Response(200, json={"success": True, "matches": []})
        )
        result = client.runtime.file.find(VALID_UUID, "/workspace", glob="*.rs")
        assert result.matches == []
        assert result.truncated is False

        body = json.loads(mock_api.calls[-1].request.content)
        assert "pattern" not in body
        assert body["glob"] == "*.rs"

    def test_find_forwards_limits(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/find").mock(
            return_value=httpx.Response(200, json=_FIND_OK)
        )
        client.runtime.file.find(
            VALID_UUID,
            "/workspace",
            "needle",
            regex=True,
            case_sensitive=True,
            include_hidden=True,
            max_results=25,
            max_depth=4,
        )
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["regex"] is True
        assert body["case_sensitive"] is True
        assert body["include_hidden"] is True
        assert body["max_results"] == 25
        assert body["max_depth"] == 4

    def test_find_requires_pattern_or_glob(self, client, mock_api):
        with pytest.raises(ValueError, match="pattern or glob"):
            client.runtime.file.find(VALID_UUID, "/workspace")

    def test_find_rejects_non_positive_limits(self, client, mock_api):
        with pytest.raises(ValueError, match="max_results must be positive"):
            client.runtime.file.find(VALID_UUID, "/workspace", "x", max_results=0)
        with pytest.raises(ValueError, match="max_depth must be positive"):
            client.runtime.file.find(VALID_UUID, "/workspace", "x", max_depth=-1)

    def test_find_rejects_path_traversal(self, client, mock_api):
        with pytest.raises(ValueError, match="traversal"):
            client.runtime.file.find(VALID_UUID, "../../etc", "root")

    def test_find_reports_truncation(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/find").mock(
            return_value=httpx.Response(
                200, json={"success": True, "matches": [], "truncated": True, "files_scanned": 9}
            )
        )
        result = client.runtime.file.find(VALID_UUID, "/workspace", "x")
        assert result.truncated is True
        assert result.files_scanned == 9


class TestSyncRuntimeReplace:
    def test_replace(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/replace").mock(
            return_value=httpx.Response(200, json=_REPLACE_OK)
        )
        result = client.runtime.file.replace(VALID_UUID, "/workspace", "v1", "v2", glob="*.py")
        assert isinstance(result, FileReplaceResponse)
        assert result.total_replacements == 3
        assert len(result) == 2
        assert result.files[0].replacements == 2
        assert result.dry_run is False

        body = json.loads(mock_api.calls[-1].request.content)
        assert body["pattern"] == "v1"
        assert body["replacement"] == "v2"
        assert body["glob"] == "*.py"
        assert body["dry_run"] is False

    def test_replace_dry_run(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/replace").mock(
            return_value=httpx.Response(200, json={**_REPLACE_OK, "dry_run": True})
        )
        result = client.runtime.file.replace(
            VALID_UUID, "/workspace", "v1", "v2", dry_run=True, regex=True
        )
        assert result.dry_run is True

        body = json.loads(mock_api.calls[-1].request.content)
        assert body["dry_run"] is True
        assert body["regex"] is True

    def test_replace_allows_empty_replacement(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/replace").mock(
            return_value=httpx.Response(200, json=_REPLACE_OK)
        )
        client.runtime.file.replace(VALID_UUID, "/workspace", "drop-me", "")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["replacement"] == ""

    def test_replace_requires_pattern(self, client, mock_api):
        with pytest.raises(ValueError, match="pattern must not be empty"):
            client.runtime.file.replace(VALID_UUID, "/workspace", "", "x")

    def test_bound_find_and_replace(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/find").mock(
            return_value=httpx.Response(200, json=_FIND_OK)
        )
        mock_api.post(f"{SB}/{VALID_UUID}/files/replace").mock(
            return_value=httpx.Response(200, json=_REPLACE_OK)
        )
        runtime = client.runtime.file  # resource stays reachable
        assert runtime is not None

        from gravixlayer.types.runtime import Runtime

        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        assert len(rt.file.find("/workspace", "TODO", glob="*.py")) == 2
        assert rt.file.replace("/workspace", "v1", "v2").total_replacements == 3


# ===================================================================
# Async — Filesystem Search
# ===================================================================


class TestAsyncRuntimeSearch:
    @pytest.mark.asyncio
    async def test_find(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/find").mock(
            return_value=httpx.Response(200, json=_FIND_OK)
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.file.find(VALID_UUID, "/workspace", "TODO")
            assert len(result.matches) == 2

    @pytest.mark.asyncio
    async def test_replace(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/replace").mock(
            return_value=httpx.Response(200, json=_REPLACE_OK)
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.file.replace(VALID_UUID, "/workspace", "v1", "v2")
            assert result.total_replacements == 3

    @pytest.mark.asyncio
    async def test_find_requires_pattern_or_glob(self, mock_api):
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValueError, match="pattern or glob"):
                await client.runtime.file.find(VALID_UUID, "/workspace")


# ===================================================================
# Sync — PTY handle
# ===================================================================


class TestSyncPtyHandle:
    def test_handle_streams_and_completes(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}/stream").mock(
            return_value=httpx.Response(
                200,
                text=_sse(
                    _pty_data(b"hello "),
                    _pty_data(b"world"),
                    {"type": "exit", "exit_code": 7, "status": "exited"},
                ),
                headers={"content-type": "text/event-stream"},
            )
        )
        chunks: list[bytes] = []
        with client.runtime.pty.handle(VALID_UUID, SESSION_ID) as pty:
            pty.connect(on_data=chunks.append)
            assert pty.wait_for_connection(timeout=5) is True
            final = pty.wait_for_completion(timeout=5)
            assert isinstance(final, PtySession)
            assert final.exit_code == 7
            assert pty.exit_code == 7
            assert pty.output == b"hello world"
            assert b"".join(chunks) == b"hello world"

    def test_wait_for_completion_polls_when_detached(self, client, mock_api):
        responses = [
            httpx.Response(200, json=_session_json("running")),
            httpx.Response(200, json=_session_json("exited", exit_code=3)),
        ]
        mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}").mock(side_effect=responses)

        pty = client.runtime.pty.handle(VALID_UUID, SESSION_ID)
        assert pty.is_connected is False
        final = pty.wait_for_completion(timeout=10)
        assert final.status == "exited"
        assert final.exit_code == 3
        assert pty.exit_code == 3

    def test_wait_for_completion_does_not_poll_while_connected(self, client, mock_api):
        """An attached stream carries the exit frame, so no session GETs are needed."""
        mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}/stream").mock(
            return_value=httpx.Response(
                200,
                text=_sse(
                    _pty_data(b"working"),
                    {"type": "exit", "exit_code": 0, "status": "exited"},
                ),
                headers={"content-type": "text/event-stream"},
            )
        )
        get_route = mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}").mock(
            return_value=httpx.Response(200, json=_session_json("running"))
        )

        with client.runtime.pty.handle(VALID_UUID, SESSION_ID) as pty:
            pty.connect()
            pty.wait_for_connection(timeout=5)
            final = pty.wait_for_completion(timeout=5)

        assert final.exit_code == 0
        assert get_route.call_count == 0

    def test_wait_for_completion_times_out(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}").mock(
            return_value=httpx.Response(200, json=_session_json("running"))
        )
        pty = client.runtime.pty.handle(VALID_UUID, SESSION_ID)
        with pytest.raises(TimeoutError, match="still running"):
            pty.wait_for_completion(timeout=0)

    def test_disconnect_does_not_kill_session(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}/stream").mock(
            return_value=httpx.Response(
                200,
                text=_sse(_pty_data(b"tick")),
                headers={"content-type": "text/event-stream"},
            )
        )
        kill_route = mock_api.delete(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        pty = client.runtime.pty.handle(VALID_UUID, SESSION_ID)
        pty.connect()
        pty.wait_for_connection(timeout=5)
        pty.disconnect()
        assert pty.is_connected is False
        assert kill_route.called is False
        pty.disconnect()  # idempotent

    def test_kill_disconnects(self, client, mock_api):
        mock_api.delete(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        pty = client.runtime.pty.handle(VALID_UUID, SESSION_ID)
        assert pty.kill() is True
        assert pty.is_connected is False

    def test_handle_delegates_input_and_resize(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}/input").mock(
            return_value=httpx.Response(200, json={"success": True, "bytes_written": 3})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}/resize").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}/signal").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        pty = client.runtime.pty.handle(VALID_UUID, SESSION_ID)
        assert pty.send_input("ls\n").bytes_written == 3
        assert pty.resize(120, 40) is True
        assert pty.send_signal("INT") is True
        assert pty.runtime_id == VALID_UUID
        assert pty.session_id == SESSION_ID

    def test_handle_validates_ids(self, client):
        with pytest.raises(ValueError, match="Invalid runtime_id"):
            client.runtime.pty.handle("not-a-uuid", SESSION_ID)
        with pytest.raises(ValueError, match="session_id"):
            client.runtime.pty.handle(VALID_UUID, "")

    def test_refresh_caches_session(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}").mock(
            return_value=httpx.Response(200, json=_session_json("running"))
        )
        pty = client.runtime.pty.handle(VALID_UUID, SESSION_ID)
        assert pty.session is None
        session = pty.refresh()
        assert session.pid == 1234
        assert pty.session is session
        assert pty.exit_code is None

    def test_output_buffer_is_bounded(self):
        from gravixlayer.resources.runtime_pty import (
            PTY_HANDLE_BUFFER_BYTES,
            _append_bounded,
        )

        buffer = bytearray()
        _append_bounded(buffer, b"a" * (PTY_HANDLE_BUFFER_BYTES + 16))
        assert len(buffer) == PTY_HANDLE_BUFFER_BYTES
        _append_bounded(buffer, b"tail")
        assert len(buffer) == PTY_HANDLE_BUFFER_BYTES
        assert bytes(buffer[-4:]) == b"tail"


# ===================================================================
# Async — PTY handle
# ===================================================================


class TestAsyncPtyHandle:
    @pytest.mark.asyncio
    async def test_handle_streams_and_completes(self, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}/stream").mock(
            return_value=httpx.Response(
                200,
                text=_sse(
                    _pty_data(b"out"),
                    {"type": "exit", "exit_code": 0, "status": "exited"},
                ),
                headers={"content-type": "text/event-stream"},
            )
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            chunks: list[bytes] = []
            async with client.runtime.pty.handle(VALID_UUID, SESSION_ID) as pty:
                await pty.connect(on_data=chunks.append)
                assert await pty.wait_for_connection(timeout=5) is True
                final = await pty.wait_for_completion(timeout=5)
                assert final.exit_code == 0
                assert pty.output == b"out"
                assert chunks == [b"out"]

    @pytest.mark.asyncio
    async def test_wait_for_completion_polls_when_detached(self, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}").mock(
            side_effect=[
                httpx.Response(200, json=_session_json("running")),
                httpx.Response(200, json=_session_json("exited", exit_code=2)),
            ]
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            pty = client.runtime.pty.handle(VALID_UUID, SESSION_ID)
            final = await pty.wait_for_completion(timeout=10)
            assert final.exit_code == 2

    @pytest.mark.asyncio
    async def test_disconnect_is_idempotent(self, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/pty/{SESSION_ID}/stream").mock(
            return_value=httpx.Response(
                200,
                text=_sse(_pty_data(b"x")),
                headers={"content-type": "text/event-stream"},
            )
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            pty = client.runtime.pty.handle(VALID_UUID, SESSION_ID)
            await pty.connect()
            await pty.wait_for_connection(timeout=5)
            await pty.disconnect()
            assert pty.is_connected is False
            await pty.disconnect()
