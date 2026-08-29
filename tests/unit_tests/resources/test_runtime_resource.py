"""
Tests for sync and async runtime resources.

Covers: create, list, get, kill, connect, set_timeout, get_metrics,
``client.runtime.service.*``, ``client.runtime.file.*``, git (``client.runtime.git.*``), command/code execution,
SSH, pause/resume, code contexts.
"""

import io
import json
from urllib.parse import parse_qs, urlparse

import pytest
import httpx
import respx

from tests.utils import (
    TEST_API_KEY,
    TEST_BASE_URL,
    AGENTS_BASE,
    VALID_UUID,
    make_runtime_response,
    make_list_response,
    make_metrics_response,
    make_code_run_response,
    make_cmd_run_response,
)

from gravixlayer import GravixLayer, AsyncGravixLayer
from gravixlayer.resources.runtime_files import _file_read_response, _write_result_from_upload
from gravixlayer.types.exceptions import GravixLayerBadRequestError
from gravixlayer.types.runtime import (
    Runtime,
    RuntimeList,
    RuntimeMetrics,
    RuntimeTimeoutResponse,
    RuntimeKillResponse,
    SSHInfo,
    SSHStatus,
    FileReadResponse,
    FileWriteResponse,
    FileInfo,
    DirectoryCreateResponse,
    CommandRunResponse,
    CodeRunResponse,
    CodeContext,
    CodeContextDeleteResponse,
    WriteEntry,
    WriteResult,
    WriteFilesResponse,
    GitOperationResult,
)


SB = f"{AGENTS_BASE}/runtime"

_GIT_OK = {"success": True, "exit_code": 0, "stdout": "ok\n", "stderr": "", "error": ""}


def _uploaded_path(request: httpx.Request) -> str:
    """The destination the client asked for, read back off the query string."""
    return parse_qs(urlparse(str(request.url)).query)["path"][0]


def _echo_upload(request: httpx.Request) -> httpx.Response:
    """Answer an upload the way the API does: with the path it wrote."""
    path = _uploaded_path(request)
    return httpx.Response(
        200, json=[{"path": path, "name": path.rsplit("/", 1)[-1], "type": "file"}]
    )


# ===================================================================
# Sync Runtime Resource — Lifecycle
# ===================================================================


class TestSyncRuntimeLifecycle:
    def test_create(self, client, mock_api):
        mock_api.post(f"{SB}").mock(
            return_value=httpx.Response(200, json=make_runtime_response())
        )
        rt = client.runtime.create(template="base-small")
        assert isinstance(rt, Runtime)
        assert rt.runtime_id == VALID_UUID
        assert rt.status == "running"
        assert rt._client is client

    def test_create_normalizes_go_runtime_response_keys(self, client, mock_api):
        """API JSON may use id / compute_* / tags; SDK maps to runtime model fields."""
        mock_api.post(f"{SB}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": VALID_UUID,
                    "status": "running",
                    "template_id": "tmpl-001",
                    "compute_provider": "aws",
                    "compute_region": "us-east-1",
                    "tags": {"team": "preview"},
                },
            )
        )
        rt = client.runtime.create(template="base-small")
        assert rt.runtime_id == VALID_UUID
        assert rt.cloud == "aws"
        assert rt.region == "us-east-1"
        assert rt.metadata == {"team": "preview"}

    def test_create_with_all_params(self, client, mock_api):
        mock_api.post(f"{SB}").mock(
            return_value=httpx.Response(200, json=make_runtime_response())
        )
        rt = client.runtime.create(
            cloud="aws",
            region="us-west-2",
            template="node-v1",
            timeout=600,
            env_vars={"NODE_ENV": "production"},
            metadata={"team": "ml"},
            internet_access=True,
            agent_id="agent-001",
            providers=["provider-uuid-1"],
            network_policy_ids=["policy-uuid-1", "policy-uuid-2"],
        )
        assert isinstance(rt, Runtime)

        # Verify the request payload
        request = mock_api.calls[-1].request
        import json
        body = json.loads(request.content)
        assert body["cloud"] == "aws"
        assert body["region"] == "us-west-2"
        assert body["template"] == "node-v1"
        assert body["timeout"] == 600
        assert body["env_vars"] == {"NODE_ENV": "production"}
        assert body["internet_access"] is True
        assert body["providers"] == ["provider-uuid-1"]
        assert body["network_policy_ids"] == ["policy-uuid-1", "policy-uuid-2"]

    def test_list(self, client, mock_api):
        mock_api.get(url__regex=rf"{SB}\?").mock(
            return_value=httpx.Response(200, json=make_list_response(3))
        )
        result = client.runtime.list(limit=10)
        assert isinstance(result, RuntimeList)
        assert result.total == 3
        assert len(result.runtimes) == 3

    def test_get(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json=make_runtime_response())
        )
        rt = client.runtime.get(VALID_UUID)
        assert rt.runtime_id == VALID_UUID

    def test_get_invalid_id_raises(self, client, mock_api):
        with pytest.raises(ValueError, match="Invalid runtime_id"):
            client.runtime.get("not-a-uuid")

    def test_kill(self, client, mock_api):
        mock_api.delete(f"{SB}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200,
                json={"message": "Terminated", "runtime_id": VALID_UUID, "status": "killed"},
            )
        )
        result = client.runtime.kill(VALID_UUID)
        assert isinstance(result, RuntimeKillResponse)
        assert result.message == "Terminated"
        assert result.runtime_id == VALID_UUID

    def test_connect(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/connect").mock(
            return_value=httpx.Response(200, json={"runtime_id": VALID_UUID, "status": "connected"})
        )
        result = client.runtime.connect(VALID_UUID)
        assert result["status"] == "connected"


# ===================================================================
# Sync Runtime Resource — Configuration
# ===================================================================


class TestSyncRuntimeConfig:
    def test_set_timeout(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/timeout").mock(
            return_value=httpx.Response(200, json={"message": "Updated", "timeout": 300})
        )
        result = client.runtime.set_timeout(VALID_UUID, 300)
        assert isinstance(result, RuntimeTimeoutResponse)
        assert result.timeout == 300

    def test_get_metrics(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/metrics").mock(
            return_value=httpx.Response(200, json=make_metrics_response())
        )
        metrics = client.runtime.get_metrics(VALID_UUID)
        assert isinstance(metrics, RuntimeMetrics)
        assert metrics.cpu_usage == 45.2
        assert metrics.memory_total == 512.0

    def test_service_web_url_and_handle(self, client, mock_api):
        payload = {
            "runtime_id": VALID_UUID,
            "port": 3000,
            "url": "https://3000-abc.service.gravixlayer.ai",
            "web_url": "https://3000-abc.service.gravixlayer.ai",
            "browser_url": "https://3000-abc.service.gravixlayer.ai/_ws/auth?token=t",
            "service_url": "https://3000-abc.service.gravixlayer.ai/",
            "token": "t",
            "is_public": False,
            "expires_at": "2026-07-18T12:00:00Z",
            "subdomain": "3000-abc",
        }
        mock_api.post(f"{SB}/{VALID_UUID}/services").mock(
            return_value=httpx.Response(200, json=payload)
        )
        info = client.runtime.service.web_url(VALID_UUID, 3000)
        assert info.port == 3000
        assert info.token == "t"
        handle = client.runtime.service(VALID_UUID, 3000)
        assert handle.web_url.endswith("service.gravixlayer.ai")
        handle.close()


# ===================================================================
# Sync Runtime Resource — Git (nested client.runtime.git.*)
# ===================================================================


class TestSyncRuntimeGit:
    def test_span_helpers_omit_credentials(self):
        from gravixlayer.resources.runtime_git import (
            _git_span_attributes,
            _git_span_inputs,
        )

        data = {
            "url": "https://github.com/foo/bar.git",
            "path": "/workspace/bar",
            "auth_token": "secret",
            "username": "user",
            "password": "pass",
        }
        inputs = _git_span_inputs(data)
        assert "auth_token" not in inputs
        assert "username" not in inputs
        assert "password" not in inputs
        assert inputs["auth"] is True
        assert inputs["url"] == data["url"]
        attrs = _git_span_attributes(data)
        assert attrs["git.repository_url"] == data["url"]
        assert attrs["file.path"] == data["path"]

    def test_git_clone(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/clone").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        r = client.runtime.git.clone(
            VALID_UUID,
            "https://github.com/foo/bar.git",
            "/workspace/bar",
            branch="main",
            depth=1,
            auth_token="tok",
        )
        assert isinstance(r, GitOperationResult)
        assert r.success is True
        req = mock_api.calls[-1].request
        import json
        body = json.loads(req.content)
        assert body["url"].endswith("bar.git")
        assert body["path"] == "/workspace/bar"
        assert body["branch"] == "main"
        assert body["depth"] == 1
        assert body["auth_token"] == "tok"

    def test_git_status_and_pull(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/status").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        mock_api.post(f"{SB}/{VALID_UUID}/git/pull").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        st = client.runtime.git.status(VALID_UUID, "/workspace/repo")
        assert st.exit_code == 0
        pl = client.runtime.git.pull(VALID_UUID, "/workspace/repo", remote="origin", branch="main")
        assert pl.success
        req = mock_api.calls[-1].request
        import json
        body = json.loads(req.content)
        assert body["repository_path"] == "/workspace/repo"
        assert body["remote"] == "origin"
        assert body["branch"] == "main"

    def test_git_branch_list(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/branches").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        r = client.runtime.git.branch_list(VALID_UUID, "/workspace/repo")
        assert r.success
        import json

        body = json.loads(mock_api.calls[-1].request.content)
        assert body["repository_path"] == "/workspace/repo"
        assert "scope" not in body

        r2 = client.runtime.git.branch_list(VALID_UUID, "/workspace/repo", scope="remote")
        assert r2.success
        body2 = json.loads(mock_api.calls[-1].request.content)
        assert body2["scope"] == "remote"

    def test_git_property_cached(self, client, mock_api):
        g1 = client.runtime.git
        g2 = client.runtime.git
        assert g1 is g2

    def test_git_create_branch(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/branch/create").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        r = client.runtime.git.create_branch(
            VALID_UUID, "/workspace/r", "feature-x", start_point="main"
        )
        assert r.success
        import json
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["repository_path"] == "/workspace/r"
        assert body["branch_name"] == "feature-x"
        assert body["start_point"] == "main"

    def test_git_delete_branch(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/branch/delete").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        r = client.runtime.git.delete_branch(VALID_UUID, "/workspace/r", "old", force=True)
        assert r.success
        import json
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["branch_name"] == "old"
        assert body["force"] is True


# ===================================================================
# Sync Runtime Resource — File Operations
# ===================================================================


class TestSyncRuntimeFiles:
    def test_read_file(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/read").mock(
            return_value=httpx.Response(200, json={"content": "hello world", "path": "/tmp/f.txt"})
        )
        result = client.runtime.file.read(VALID_UUID, "/tmp/f.txt")
        assert result.content == "hello world"
        assert result.size == 11

    def test_read_file_utf8_size_without_server_size(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/read").mock(
            return_value=httpx.Response(200, json={"content": "é", "path": "/tmp/e.txt"})
        )
        result = client.runtime.file.read(VALID_UUID, "/tmp/e.txt")
        assert result.size == 2

    def test_file_read_response_ignores_unknown_fields(self):
        parsed = _file_read_response(
            {"content": "hi", "path": "/tmp/a", "encoding": "utf-8"},
            "/tmp/fallback",
        )
        assert parsed.content == "hi"
        assert parsed.path == "/tmp/a"
        assert parsed.size == 2
        assert not hasattr(parsed, "encoding")

    def test_write_file(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/write").mock(
            return_value=httpx.Response(200, json={"message": "Written", "path": "/tmp/f.txt"})
        )
        result = client.runtime.file.write(VALID_UUID, "/tmp/f.txt", "content")
        assert result.message == "Written"

    def test_list_files(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/list").mock(
            return_value=httpx.Response(200, json={
                "files": [
                    {"name": "main.py", "size": 256, "is_dir": False, "mod_time": "2025-01-01"},
                    {"name": "src", "size": 0, "is_dir": True, "modified_at": "2025-01-01"},
                ]
            })
        )
        result = client.runtime.file.list(VALID_UUID, "/workspace")
        assert len(result.files) == 2
        assert result.files[0].name == "main.py"
        assert result.files[1].is_dir is True

    def test_delete_file(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/delete").mock(
            return_value=httpx.Response(200, json={"message": "Deleted", "path": "/tmp/f.txt"})
        )
        result = client.runtime.file.delete(VALID_UUID, "/tmp/f.txt")
        assert result.message == "Deleted"

    def test_make_directory(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/create-directory").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "message": "Created",
                    "path": "/tmp/newdir",
                },
            )
        )
        result = client.runtime.file.create_directory(VALID_UUID, "/tmp/newdir")
        assert result.message == "Created"

    def test_upload_file(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/upload").mock(
            return_value=httpx.Response(200, json={"message": "Uploaded", "path": "/tmp/upload.bin"})
        )
        f = io.BytesIO(b"binary data")
        result = client.runtime.file.upload_file(VALID_UUID, file=f, path="/tmp/upload.bin")
        assert result.message == "Uploaded"

    def test_download_file(self, client, mock_api):
        mock_api.get(url__regex=rf"{SB}/{VALID_UUID}/download").mock(
            return_value=httpx.Response(200, content=b"file bytes")
        )
        result = client.runtime.file.download_file(VALID_UUID, "/tmp/f.bin")
        assert result == b"file bytes"

    def test_path_validation_empty(self, client, mock_api):
        with pytest.raises(ValueError, match="must not be empty"):
            client.runtime.file.read(VALID_UUID, "")

    def test_path_validation_relative_traversal(self, client, mock_api):
        with pytest.raises(ValueError, match="traversal"):
            client.runtime.file.read(VALID_UUID, "../../../etc/passwd")


# ===================================================================
# Sync Runtime Resource — Write / WriteFiles (Multipart)
# ===================================================================


class TestSyncRuntimeWrite:
    def test_write_string(self, client, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files\?").mock(
            return_value=httpx.Response(200, json=[{"path": "/tmp/f.py", "name": "f.py", "type": "file"}])
        )
        result = client.runtime.file.upload(VALID_UUID, "/tmp/f.py", "print('hi')")
        assert isinstance(result, WriteResult)
        assert result.path == "/tmp/f.py"

    def test_upload_object_files_shape(self, client, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files\?").mock(
            return_value=httpx.Response(
                200,
                json={
                    "files": [
                        {
                            "path": "/workspace/project/config.json",
                            "name": "config.json",
                            "type": "file",
                            "size": 21,
                        }
                    ],
                    "partial_failure": False,
                },
            )
        )
        result = client.runtime.file.upload(
            VALID_UUID, "/workspace/project/config.json", '{"debug": true}'
        )
        assert result.path == "/workspace/project/config.json"
        assert result.name == "config.json"
        assert result.size == 21

    def test_write_result_from_upload_shapes(self):
        listed = _write_result_from_upload(
            [{"path": "/a", "name": "a", "type": "file", "size": 3}],
            "/fallback",
            "fb",
            9,
        )
        assert listed.path == "/a"
        assert listed.size == 3
        single = _write_result_from_upload(
            {"path": "/b", "name": "b", "error": "denied"}, "/fallback", "fb", 4
        )
        assert single.path == "/b"
        assert single.error == "denied"
        assert single.size == 4
        empty = _write_result_from_upload({"files": []}, "/c", "c", 2)
        assert empty.path == "/c"
        assert empty.size == 2
        none = _write_result_from_upload(None, "/d", "d", 1)
        assert none.path == "/d"
        assert none.name == "d"

    def test_write_bytes(self, client, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files\?").mock(
            return_value=httpx.Response(200, json=[{"path": "/tmp/data.bin", "name": "data.bin", "type": "file"}])
        )
        result = client.runtime.file.upload(VALID_UUID, "/tmp/data.bin", b"\x00\x01\x02")
        assert result.name == "data.bin"

    def test_write_file_like(self, client, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files\?").mock(
            return_value=httpx.Response(200, json=[{"path": "/tmp/f.txt", "name": "f.txt", "type": "file"}])
        )
        f = io.BytesIO(b"file content")
        result = client.runtime.file.upload(VALID_UUID, "/tmp/f.txt", f)
        assert result.type == "file"

    def test_write_with_mode_and_user(self, client, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files\?").mock(
            return_value=httpx.Response(200, json=[{"path": "/tmp/run.sh", "name": "run.sh", "type": "file"}])
        )
        result = client.runtime.file.upload(VALID_UUID, "/tmp/run.sh", "#!/bin/bash", user="root", mode=0o755)
        assert result is not None

    def test_write_files_multiple(self, client, mock_api):
        """Every entry keeps its own destination, including the directory."""
        route = mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files").mock(
            side_effect=_echo_upload
        )
        entries = [
            WriteEntry(path="/workspace/project/a.py", data="code_a"),
            WriteEntry(path="/workspace/project/src/b.py", data="code_b"),
        ]
        resp = client.runtime.file.write_many(VALID_UUID, entries)
        assert isinstance(resp, WriteFilesResponse)
        assert [f.path for f in resp.files] == [
            "/workspace/project/a.py",
            "/workspace/project/src/b.py",
        ]
        assert resp.partial_failure is False
        assert sorted(_uploaded_path(call.request) for call in route.calls) == [
            "/workspace/project/a.py",
            "/workspace/project/src/b.py",
        ]

    def test_write_files_per_entry_mode(self, client, mock_api):
        route = mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files").mock(
            side_effect=_echo_upload
        )
        client.runtime.file.write_many(
            VALID_UUID, [WriteEntry(path="/workspace/run.sh", data="#!/bin/sh\n", mode=0o755)]
        )
        query = parse_qs(urlparse(str(route.calls[0].request.url)).query)
        assert query["mode"] == ["0755"]

    def test_write_files_empty_list(self, client, mock_api):
        resp = client.runtime.file.write_many(VALID_UUID, [])
        assert resp.files == []
        assert resp.partial_failure is False

    def test_write_files_partial_failure(self, client, mock_api):
        def respond(request: httpx.Request) -> httpx.Response:
            if _uploaded_path(request).endswith("fail.py"):
                return httpx.Response(403, text="permission denied")
            return _echo_upload(request)

        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files").mock(side_effect=respond)
        entries = [
            WriteEntry(path="/workspace/ok.py", data="ok"),
            WriteEntry(path="/workspace/fail.py", data="fail"),
        ]
        resp = client.runtime.file.write_many(VALID_UUID, entries)
        assert resp.partial_failure is True
        assert resp.files[0].error is None
        assert resp.files[1].path == "/workspace/fail.py"
        assert "permission denied" in resp.files[1].error

    def test_write_files_all_rejected_raises(self, client, mock_api):
        """Nothing was written, so this is a failed call rather than a report."""
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files").mock(
            return_value=httpx.Response(403, text="permission denied")
        )
        entries = [
            WriteEntry(path="/workspace/a.py", data="a"),
            WriteEntry(path="/workspace/b.py", data="b"),
        ]
        with pytest.raises(GravixLayerBadRequestError, match="permission denied"):
            client.runtime.file.write_many(VALID_UUID, entries)

    def test_write_files_rejects_bad_concurrency(self, client):
        with pytest.raises(ValueError, match="concurrency must be positive"):
            client.runtime.file.write_many(
                VALID_UUID, [WriteEntry(path="/workspace/a.py", data="a")], concurrency=0
            )

    def test_coerce_invalid_type_raises(self, client):
        from gravixlayer.resources.runtime_files import RuntimeFileResource

        with pytest.raises(TypeError, match="Expected str, bytes"):
            RuntimeFileResource._coerce_to_bytes(12345)


# ===================================================================
# Sync Runtime Resource — Command / Code Execution
# ===================================================================


class TestSyncRuntimeExecution:
    def test_run_cmd(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/commands/run").mock(
            return_value=httpx.Response(200, json=make_cmd_run_response())
        )
        result = client.runtime.run_cmd(VALID_UUID, "ls -la")
        assert isinstance(result, CommandRunResponse)
        assert result.success is True
        assert result.exit_code == 0
        import json
        body = json.loads(mock_api.calls[-1].request.content)
        assert "args" not in body

    def test_run_cmd_with_timeout_converts_to_ms(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/commands/run").mock(
            return_value=httpx.Response(200, json=make_cmd_run_response())
        )
        client.runtime.run_cmd(VALID_UUID, "sleep 5", timeout=10)
        import json
        request = mock_api.calls[-1].request
        body = json.loads(request.content)
        assert body["timeout"] == 10000  # 10s -> 10000ms

    def test_run_cmd_streaming_callbacks(self, client, mock_api):
        sse = (
            'data: {"type": "stdout", "data": "hello"}\n\n'
            'data: {"type": "stderr", "data": "warn"}\n\n'
            "data: not-json\n\n"
            "event: ping\n\n"
            'data: {"type": "end", "exit_code": 0}\n\n'
        )
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/commands/run").mock(
            return_value=httpx.Response(
                200,
                text=sse,
                headers={"content-type": "text/event-stream"},
            )
        )
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        exits: list[int] = []
        result = client.runtime.run_cmd(
            VALID_UUID,
            "echo hi",
            args=["-n"],
            working_dir="/tmp",
            environment={"A": "1"},
            on_stdout=stdout_chunks.append,
            on_stderr=stderr_chunks.append,
            on_exit=exits.append,
        )
        assert result.success is True
        assert result.stdout == "hello"
        assert result.stderr == "warn"
        assert stdout_chunks == ["hello"]
        assert stderr_chunks == ["warn"]
        assert exits == [0]
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["args"] == ["-n"]
        assert body["working_dir"] == "/tmp"
        assert body["environment"] == {"A": "1"}
        assert "stream=true" in str(mock_api.calls[-1].request.url)

    def test_run_cmd_streaming_error_event(self, client, mock_api):
        sse = 'data: {"type": "error", "message": "boom"}\n\n'
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/commands/run").mock(
            return_value=httpx.Response(
                200,
                text=sse,
                headers={"content-type": "text/event-stream"},
            )
        )
        stderr_chunks: list[str] = []
        exits: list[int] = []
        result = client.runtime.run_cmd(
            VALID_UUID,
            "fail",
            on_stderr=stderr_chunks.append,
            on_exit=exits.append,
        )
        assert result.success is False
        assert result.exit_code == 1
        assert result.stderr == "boom"
        assert stderr_chunks == ["boom"]
        assert exits == [1]

    def test_run_code(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/code/run").mock(
            return_value=httpx.Response(200, json=make_code_run_response())
        )
        result = client.runtime.run_code(VALID_UUID, "print('hello')")
        assert isinstance(result, CodeRunResponse)
        assert result.text == "Hello, World!"
        assert result.success is True

    def test_run_code_with_context(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/code/run").mock(
            return_value=httpx.Response(200, json=make_code_run_response())
        )
        client.runtime.run_code(VALID_UUID, "x = 42", context_id="ctx-1")
        import json
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["context_id"] == "ctx-1"


# ===================================================================
# Sync Runtime Resource — Code Contexts
# ===================================================================


class TestSyncRuntimeCodeContexts:
    def test_create_context(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/code/contexts").mock(
            return_value=httpx.Response(200, json={"id": "ctx-1", "language": "python", "cwd": "/workspace"})
        )
        ctx = client.runtime.create_context(VALID_UUID)
        assert isinstance(ctx, CodeContext)
        assert ctx.context_id == "ctx-1"

    def test_get_context(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/code/contexts/ctx-1").mock(
            return_value=httpx.Response(200, json={"id": "ctx-1", "language": "python", "cwd": "/workspace"})
        )
        ctx = client.runtime.get_context(VALID_UUID, "ctx-1")
        assert ctx.language == "python"

    def test_delete_context(self, client, mock_api):
        mock_api.delete(f"{SB}/{VALID_UUID}/code/contexts/ctx-1").mock(
            return_value=httpx.Response(200, json={"message": "Deleted", "context_id": "ctx-1"})
        )
        result = client.runtime.delete_context(VALID_UUID, "ctx-1")
        assert result.message == "Deleted"


# ===================================================================
# Sync Runtime Resource — SSH
# ===================================================================


class TestSyncRuntimeSSH:
    def test_enable_ssh(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/ssh/enable").mock(
            return_value=httpx.Response(200, json={
                "runtime_id": VALID_UUID, "enabled": True, "port": 22,
                "username": "user", "connect_cmd": "ssh user@host",
                "private_key": "key", "public_key": "pub",
            })
        )
        info = client.runtime.enable_ssh(VALID_UUID)
        assert isinstance(info, SSHInfo)
        assert info.enabled is True
        assert info.private_key == "key"

    def test_enable_ssh_regenerate(self, client, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/ssh/enable\?regenerate_keys=true").mock(
            return_value=httpx.Response(200, json={
                "runtime_id": VALID_UUID, "enabled": True, "port": 22,
                "username": "user", "connect_cmd": "ssh user@host",
            })
        )
        info = client.runtime.enable_ssh(VALID_UUID, regenerate_keys=True)
        assert info.enabled is True

    def test_disable_ssh(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/ssh/disable").mock(
            return_value=httpx.Response(200, json={})
        )
        client.runtime.disable_ssh(VALID_UUID)

    def test_ssh_status(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/ssh/status").mock(
            return_value=httpx.Response(200, json={
                "runtime_id": VALID_UUID, "enabled": True, "port": 22,
                "username": "user", "daemon_running": True,
            })
        )
        status = client.runtime.ssh_status(VALID_UUID)
        assert isinstance(status, SSHStatus)
        assert status.daemon_running is True


# ===================================================================
# Sync Runtime Resource — State Management
# ===================================================================


class TestSyncRuntimeState:
    def test_pause(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/pause").mock(
            return_value=httpx.Response(200, json={})
        )
        client.runtime.pause(VALID_UUID)

    def test_resume(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/resume").mock(
            return_value=httpx.Response(200, json={})
        )
        client.runtime.resume(VALID_UUID)


# ===================================================================
# Sync Runtime Resource — RuntimeResource Delegation
# ===================================================================


class TestSyncRuntimeResourceDelegation:
    def test_delegates_to_runtimes(self, client, mock_api):
        """RuntimeResource.__getattr__ should delegate to the inner Runtimes."""
        mock_api.get(f"{SB}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json=make_runtime_response())
        )
        # client.runtime is RuntimeResource; calling .get() should delegate
        rt = client.runtime.get(VALID_UUID)
        assert rt.runtime_id == VALID_UUID

    def test_templates_accessible(self, client, mock_api):
        """RuntimeResource.templates should be a RuntimeTemplates instance."""
        mock_api.get(url__regex=rf"{AGENTS_BASE}/template").mock(
            return_value=httpx.Response(200, json={
                "templates": [
                    {"id": "t1", "name": "python-v1", "description": "", "vcpu_count": 2,
                     "memory_mb": 512, "disk_size_mb": 4096, "visibility": "public",
                     "created_at": "2025-01-01", "updated_at": "2025-01-01"},
                ],
                "limit": 100,
                "offset": 0,
            })
        )
        result = client.runtime.templates.list()
        assert len(result.templates) == 1


# ===================================================================
# Async Runtime Resource — Lifecycle
# ===================================================================


class TestAsyncRuntimeLifecycle:
    @pytest.mark.asyncio
    async def test_create(self, mock_api):
        mock_api.post(f"{SB}").mock(
            return_value=httpx.Response(200, json=make_runtime_response())
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            rt = await client.runtime.create(template="base-small")
            assert isinstance(rt, Runtime)
            assert rt.runtime_id == VALID_UUID

    @pytest.mark.asyncio
    async def test_list(self, mock_api):
        mock_api.get(url__regex=rf"{SB}\?").mock(
            return_value=httpx.Response(200, json=make_list_response(2))
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.list()
            assert result.total == 2

    @pytest.mark.asyncio
    async def test_get(self, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json=make_runtime_response())
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            rt = await client.runtime.get(VALID_UUID)
            assert rt.status == "running"

    @pytest.mark.asyncio
    async def test_kill(self, mock_api):
        mock_api.delete(f"{SB}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json={"message": "Terminated", "runtime_id": VALID_UUID})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.kill(VALID_UUID)
            assert result.message == "Terminated"

    @pytest.mark.asyncio
    async def test_connect(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/connect").mock(
            return_value=httpx.Response(200, json={"status": "connected"})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.connect(VALID_UUID)
            assert result["status"] == "connected"


# ===================================================================
# Async Runtime Resource — Git (nested client.runtime.git.*)
# ===================================================================


class TestAsyncRuntimeGit:
    @pytest.mark.asyncio
    async def test_git_fetch(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/fetch").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            r = await client.runtime.git.fetch(VALID_UUID, "/workspace/repo", remote="origin")
            assert isinstance(r, GitOperationResult)
            assert r.success

    @pytest.mark.asyncio
    async def test_git_branch_list(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/branches").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            r = await client.runtime.git.branch_list(VALID_UUID, "/w/r", scope="all")
            assert r.success
            import json

            body = json.loads(mock_api.calls[-1].request.content)
            assert body["scope"] == "all"

    @pytest.mark.asyncio
    async def test_git_create_branch(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/branch/create").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            r = await client.runtime.git.create_branch(VALID_UUID, "/w/r", "b1")
            assert r.success

    @pytest.mark.asyncio
    async def test_git_property_cached(self, mock_api):
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            g1 = client.runtime.git
            g2 = client.runtime.git
            assert g1 is g2


# ===================================================================
# Async Runtime Resource — File Operations
# ===================================================================


class TestAsyncRuntimeFiles:
    @pytest.mark.asyncio
    async def test_read_file(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/read").mock(
            return_value=httpx.Response(200, json={"content": "async content"})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.file.read(VALID_UUID, "/tmp/f.txt")
            assert result.content == "async content"

    @pytest.mark.asyncio
    async def test_write_file(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/write").mock(
            return_value=httpx.Response(200, json={"message": "Written"})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.file.write(VALID_UUID, "/tmp/f.txt", "data")
            assert result.message == "Written"

    @pytest.mark.asyncio
    async def test_run_code(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/code/run").mock(
            return_value=httpx.Response(200, json=make_code_run_response())
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.run_code(VALID_UUID, "1+1")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_run_cmd(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/commands/run").mock(
            return_value=httpx.Response(200, json=make_cmd_run_response())
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.run_cmd(VALID_UUID, "echo hi")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_run_cmd_optional_fields(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/commands/run").mock(
            return_value=httpx.Response(200, json=make_cmd_run_response())
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.run_cmd(
                VALID_UUID,
                "ls",
                args=["-la"],
                working_dir="/workspace",
                environment={"FOO": "bar"},
                timeout=5,
            )
            assert result.success is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["args"] == ["-la"]
        assert body["working_dir"] == "/workspace"
        assert body["environment"] == {"FOO": "bar"}
        assert body["timeout"] == 5000


# ===================================================================
# Async Runtime Resource — SSH
# ===================================================================


class TestAsyncRuntimeSSH:
    @pytest.mark.asyncio
    async def test_enable_ssh(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/ssh/enable").mock(
            return_value=httpx.Response(200, json={
                "runtime_id": VALID_UUID, "enabled": True, "port": 22,
                "username": "user", "connect_cmd": "ssh user@host",
            })
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            info = await client.runtime.enable_ssh(VALID_UUID)
            assert info.enabled is True

    @pytest.mark.asyncio
    async def test_ssh_status(self, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/ssh/status").mock(
            return_value=httpx.Response(200, json={
                "runtime_id": VALID_UUID, "enabled": False, "port": 0,
                "username": "", "daemon_running": False,
            })
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            status = await client.runtime.ssh_status(VALID_UUID)
            assert status.enabled is False


# ===================================================================
# Async Runtime Resource — State Management
# ===================================================================


class TestAsyncRuntimeState:
    @pytest.mark.asyncio
    async def test_pause(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/pause").mock(
            return_value=httpx.Response(200, json={})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.runtime.pause(VALID_UUID)

    @pytest.mark.asyncio
    async def test_resume(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/resume").mock(
            return_value=httpx.Response(200, json={})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.runtime.resume(VALID_UUID)


# ===================================================================
# Async Runtime Resource — Write / WriteFiles
# ===================================================================


class TestAsyncRuntimeWrite:
    @pytest.mark.asyncio
    async def test_write(self, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files\?").mock(
            return_value=httpx.Response(200, json=[{"path": "/tmp/f.py", "name": "f.py", "type": "file"}])
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.file.upload(VALID_UUID, "/tmp/f.py", "code")
            assert result.path == "/tmp/f.py"

    @pytest.mark.asyncio
    async def test_upload_object_files_shape(self, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files\?").mock(
            return_value=httpx.Response(
                200,
                json={
                    "files": [
                        {
                            "path": "/workspace/project/run.sh",
                            "name": "run.sh",
                            "type": "file",
                            "size": 12,
                        }
                    ],
                    "partial_failure": False,
                },
            )
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.runtime.file.upload(
                VALID_UUID, "/workspace/project/run.sh", "#!/bin/sh\n"
            )
            assert result.path == "/workspace/project/run.sh"
            assert result.size == 12

    @pytest.mark.asyncio
    async def test_write_files(self, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files").mock(side_effect=_echo_upload)
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            entries = [
                WriteEntry(path="/workspace/project/a.py", data="code_a"),
                WriteEntry(path="/workspace/project/src/b.py", data="code_b"),
            ]
            resp = await client.runtime.file.write_many(VALID_UUID, entries)
            assert [f.path for f in resp.files] == [
                "/workspace/project/a.py",
                "/workspace/project/src/b.py",
            ]

    @pytest.mark.asyncio
    async def test_write_files_partial_failure(self, mock_api):
        def respond(request: httpx.Request) -> httpx.Response:
            if _uploaded_path(request).endswith("fail.py"):
                return httpx.Response(403, text="permission denied")
            return _echo_upload(request)

        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files").mock(side_effect=respond)
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            entries = [
                WriteEntry(path="/workspace/ok.py", data="ok"),
                WriteEntry(path="/workspace/fail.py", data="fail"),
            ]
            resp = await client.runtime.file.write_many(VALID_UUID, entries)
            assert resp.partial_failure is True
            assert "permission denied" in resp.files[1].error

    @pytest.mark.asyncio
    async def test_write_files_empty(self, mock_api):
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            resp = await client.runtime.file.write_many(VALID_UUID, [])
            assert resp.files == []


# ===================================================================
# Sync — previously missing file / git ops
# ===================================================================


class TestSyncRuntimeFileMeta:
    def test_get_info_exists(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/info").mock(
            return_value=httpx.Response(
                200,
                json={
                    "exists": True,
                    "info": {
                        "name": "f.txt",
                        "path": "/tmp/f.txt",
                        "size": 12,
                        "is_dir": False,
                        "mod_time": "2025-01-01T00:00:00Z",
                    },
                },
            )
        )
        result = client.runtime.file.get_info(VALID_UUID, "/tmp/f.txt")
        assert result.exists is True
        assert result.info is not None
        assert result.info.name == "f.txt"

    def test_get_info_missing(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/info").mock(
            return_value=httpx.Response(200, json={"exists": False})
        )
        result = client.runtime.file.get_info(VALID_UUID, "/tmp/missing")
        assert result.exists is False
        assert result.info is None

    def test_set_permissions(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/set-mode").mock(
            return_value=httpx.Response(
                200, json={"success": True, "message": "mode set"}
            )
        )
        result = client.runtime.file.set_permissions(VALID_UUID, "/tmp/f.txt", "644")
        assert result.success is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"path": "/tmp/f.txt", "mode": "644"}

    def test_set_permissions_empty_mode_raises(self, client, mock_api):
        with pytest.raises(ValueError, match="mode"):
            client.runtime.file.set_permissions(VALID_UUID, "/tmp/f.txt", "  ")


class TestSyncRuntimeGitWriteOps:
    def test_git_checkout(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/checkout").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        result = client.runtime.git.checkout(VALID_UUID, "/repo", "main")
        assert result.success is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["ref_name"] == "main"

    def test_git_fetch(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/fetch").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        result = client.runtime.git.fetch(VALID_UUID, "/repo", remote="origin")
        assert result.success is True

    def test_git_push(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/push").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        result = client.runtime.git.push(
            VALID_UUID, "/repo", remote="origin", refspec="main"
        )
        assert result.success is True

    def test_git_add(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/add").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        result = client.runtime.git.add(VALID_UUID, "/repo", paths=["a.py"])
        assert result.success is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["paths"] == ["a.py"]

    def test_git_commit(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/git/commit").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        result = client.runtime.git.commit(
            VALID_UUID,
            "/repo",
            message="init",
            author_name="Dev",
            author_email="dev@example.com",
        )
        assert result.success is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["message"] == "init"
        assert body["author_name"] == "Dev"


# ===================================================================
# Async — previously missing lifecycle / file / git ops
# ===================================================================


class TestAsyncRuntimeConfig:
    @pytest.mark.asyncio
    async def test_set_timeout_metrics_service_web_url(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/timeout").mock(
            return_value=httpx.Response(
                200, json={"message": "Updated", "timeout": 600}
            )
        )
        mock_api.get(f"{SB}/{VALID_UUID}/metrics").mock(
            return_value=httpx.Response(200, json=make_metrics_response())
        )
        mock_api.post(f"{SB}/{VALID_UUID}/services").mock(
            return_value=httpx.Response(
                200,
                json={
                    "runtime_id": VALID_UUID,
                    "port": 8080,
                    "url": "https://8080-host.service.gravixlayer.ai",
                    "web_url": "https://8080-host.service.gravixlayer.ai",
                    "browser_url": "https://8080-host.service.gravixlayer.ai/_ws/auth?token=x",
                    "service_url": "https://8080-host.service.gravixlayer.ai/",
                    "token": "x",
                    "is_public": False,
                    "expires_at": "2026-07-18T12:00:00Z",
                    "subdomain": "8080-host",
                },
            )
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            timeout = await client.runtime.set_timeout(VALID_UUID, 600)
            assert timeout.timeout == 600
            metrics = await client.runtime.get_metrics(VALID_UUID)
            assert metrics.cpu_usage == 45.2
            svc = await client.runtime.service.web_url(VALID_UUID, 8080)
            assert "8080" in svc.url
            assert svc.token == "x"


class TestAsyncRuntimeContextsAndSSH:
    @pytest.mark.asyncio
    async def test_contexts_and_disable_ssh(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/code/contexts").mock(
            return_value=httpx.Response(
                200, json={"id": "ctx-1", "language": "python", "cwd": "/"}
            )
        )
        mock_api.get(f"{SB}/{VALID_UUID}/code/contexts/ctx-1").mock(
            return_value=httpx.Response(
                200, json={"id": "ctx-1", "language": "python", "cwd": "/"}
            )
        )
        mock_api.delete(f"{SB}/{VALID_UUID}/code/contexts/ctx-1").mock(
            return_value=httpx.Response(
                200, json={"context_id": "ctx-1", "message": "Deleted"}
            )
        )
        mock_api.post(f"{SB}/{VALID_UUID}/ssh/disable").mock(
            return_value=httpx.Response(200, json={})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            ctx = await client.runtime.create_context(VALID_UUID)
            assert ctx.context_id == "ctx-1"
            got = await client.runtime.get_context(VALID_UUID, "ctx-1")
            assert got.context_id == "ctx-1"
            deleted = await client.runtime.delete_context(VALID_UUID, "ctx-1")
            assert deleted.context_id == "ctx-1"
            await client.runtime.disable_ssh(VALID_UUID)


class TestAsyncRuntimeFileMetaAndGit:
    @pytest.mark.asyncio
    async def test_file_meta_and_git_ops(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/files/info").mock(
            return_value=httpx.Response(
                200,
                json={
                    "exists": True,
                    "info": {
                        "name": "f.txt",
                        "path": "/tmp/f.txt",
                        "size": 1,
                        "is_dir": False,
                    },
                },
            )
        )
        mock_api.post(f"{SB}/{VALID_UUID}/files/set-mode").mock(
            return_value=httpx.Response(200, json={"success": True, "message": "ok"})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/files/delete").mock(
            return_value=httpx.Response(
                200, json={"message": "Deleted", "path": "/tmp/f.txt"}
            )
        )
        mock_api.post(f"{SB}/{VALID_UUID}/files/list").mock(
            return_value=httpx.Response(200, json={"files": []})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/files/create-directory").mock(
            return_value=httpx.Response(
                200, json={"path": "/tmp/d", "success": True, "message": "ok"}
            )
        )
        mock_api.post(f"{SB}/{VALID_UUID}/git/checkout").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        mock_api.post(f"{SB}/{VALID_UUID}/git/push").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        mock_api.post(f"{SB}/{VALID_UUID}/git/add").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        mock_api.post(f"{SB}/{VALID_UUID}/git/commit").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        mock_api.post(f"{SB}/{VALID_UUID}/git/clone").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        mock_api.post(f"{SB}/{VALID_UUID}/git/status").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        mock_api.post(f"{SB}/{VALID_UUID}/git/pull").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )
        mock_api.post(f"{SB}/{VALID_UUID}/git/branch/delete").mock(
            return_value=httpx.Response(200, json=_GIT_OK)
        )

        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            info = await client.runtime.file.get_info(VALID_UUID, "/tmp/f.txt")
            assert info.exists is True
            perms = await client.runtime.file.set_permissions(
                VALID_UUID, "/tmp/f.txt", "755"
            )
            assert perms.success is True
            await client.runtime.file.delete(VALID_UUID, "/tmp/f.txt")
            listed = await client.runtime.file.list(VALID_UUID, "/tmp")
            assert listed.files == []
            await client.runtime.file.create_directory(VALID_UUID, "/tmp/d")

            assert (
                await client.runtime.git.clone(
                    VALID_UUID, "https://example.com/r.git", "/repo"
                )
            ).success
            assert (await client.runtime.git.status(VALID_UUID, "/repo")).success
            assert (await client.runtime.git.pull(VALID_UUID, "/repo")).success
            assert (
                await client.runtime.git.checkout(VALID_UUID, "/repo", "main")
            ).success
            assert (await client.runtime.git.push(VALID_UUID, "/repo")).success
            assert (
                await client.runtime.git.add(VALID_UUID, "/repo", paths=["a.py"])
            ).success
            assert (await client.runtime.git.commit(VALID_UUID, "/repo", "msg")).success
            assert (
                await client.runtime.git.delete_branch(VALID_UUID, "/repo", "old")
            ).success
