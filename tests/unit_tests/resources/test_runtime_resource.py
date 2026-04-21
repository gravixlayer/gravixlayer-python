"""
Tests for sync and async runtime resources.

Covers: create, list, get, kill, connect, set_timeout, get_metrics,
get_host_url, ``client.runtime.file.*``, git (``client.runtime.git.*``), command/code execution,
SSH, pause/resume, code contexts.
"""

import io
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
from gravixlayer.types.runtime import (
    Runtime,
    RuntimeList,
    RuntimeMetrics,
    RuntimeTimeoutResponse,
    RuntimeHostURL,
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


# ===================================================================
# Sync Runtime Resource — Lifecycle
# ===================================================================


class TestSyncRuntimeLifecycle:
    def test_create(self, client, mock_api):
        mock_api.post(f"{SB}").mock(
            return_value=httpx.Response(200, json=make_runtime_response())
        )
        rt = client.runtime.create(template="python-3.14-base-small")
        assert isinstance(rt, Runtime)
        assert rt.runtime_id == VALID_UUID
        assert rt.status == "running"
        assert rt._client is client

    def test_create_normalizes_go_runtime_response_keys(self, client, mock_api):
        """Control plane JSON uses id / compute_* / tags; SDK maps to runtime model fields."""
        mock_api.post(f"{SB}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": VALID_UUID,
                    "status": "running",
                    "template_id": "tmpl-001",
                    "compute_provider": "azure",
                    "compute_region": "eastus2",
                    "tags": {"team": "preview"},
                },
            )
        )
        rt = client.runtime.create(template="python-3.14-base-small")
        assert rt.runtime_id == VALID_UUID
        assert rt.provider == "azure"
        assert rt.region == "eastus2"
        assert rt.metadata == {"team": "preview"}

    def test_create_with_all_params(self, client, mock_api):
        mock_api.post(f"{SB}").mock(
            return_value=httpx.Response(200, json=make_runtime_response())
        )
        rt = client.runtime.create(
            provider="aws",
            region="us-west-2",
            template="node-v1",
            timeout=600,
            env_vars={"NODE_ENV": "production"},
            metadata={"team": "ml"},
            internet_access=True,
            agent_id="agent-001",
        )
        assert isinstance(rt, Runtime)

        # Verify the request payload
        request = mock_api.calls[-1].request
        import json
        body = json.loads(request.content)
        assert body["provider"] == "aws"
        assert body["region"] == "us-west-2"
        assert body["template"] == "node-v1"
        assert body["timeout"] == 600
        assert body["env_vars"] == {"NODE_ENV": "production"}
        assert body["internet_access"] is True

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
            return_value=httpx.Response(200, json={"message": "Terminated", "runtime_id": VALID_UUID})
        )
        result = client.runtime.kill(VALID_UUID)
        assert isinstance(result, RuntimeKillResponse)
        assert result.message == "Terminated"

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

    def test_get_host_url(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/host/8080").mock(
            return_value=httpx.Response(200, json={"url": "https://runtime.example.com:8080"})
        )
        result = client.runtime.get_host_url(VALID_UUID, 8080)
        assert isinstance(result, RuntimeHostURL)
        assert "8080" in result.url


# ===================================================================
# Sync Runtime Resource — Git (nested client.runtime.git.*)
# ===================================================================


class TestSyncRuntimeGit:
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
        result = client.runtime.file.list(VALID_UUID, "/home/user")
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
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files").mock(
            return_value=httpx.Response(200, json=[
                {"path": "/tmp/a.py", "name": "a.py", "type": "file"},
                {"path": "/tmp/b.py", "name": "b.py", "type": "file"},
            ])
        )
        entries = [
            WriteEntry(path="/tmp/a.py", data="code_a"),
            WriteEntry(path="/tmp/b.py", data="code_b"),
        ]
        resp = client.runtime.file.write_many(VALID_UUID, entries)
        assert isinstance(resp, WriteFilesResponse)
        assert len(resp.files) == 2

    def test_write_files_empty_list(self, client, mock_api):
        resp = client.runtime.file.write_many(VALID_UUID, [])
        assert resp.files == []
        assert resp.partial_failure is False

    def test_write_files_partial_failure(self, client, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files").mock(
            return_value=httpx.Response(207, json=[
                {"path": "/tmp/ok.py", "name": "ok.py", "type": "file"},
                {"path": "/tmp/fail.py", "name": "fail.py", "type": "file", "error": "permission denied"},
            ])
        )
        entries = [
            WriteEntry(path="/tmp/ok.py", data="ok"),
            WriteEntry(path="/tmp/fail.py", data="fail"),
        ]
        resp = client.runtime.file.write_many(VALID_UUID, entries)
        assert resp.partial_failure is True
        assert resp.files[1].error == "permission denied"

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

    def test_run_cmd_with_timeout_converts_to_ms(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/commands/run").mock(
            return_value=httpx.Response(200, json=make_cmd_run_response())
        )
        client.runtime.run_cmd(VALID_UUID, "sleep 5", timeout=10)
        import json
        request = mock_api.calls[-1].request
        body = json.loads(request.content)
        assert body["timeout"] == 10000  # 10s -> 10000ms

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
            return_value=httpx.Response(200, json={"id": "ctx-1", "language": "python", "cwd": "/home/user"})
        )
        ctx = client.runtime.create_context(VALID_UUID)
        assert isinstance(ctx, CodeContext)
        assert ctx.context_id == "ctx-1"

    def test_get_context(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/code/contexts/ctx-1").mock(
            return_value=httpx.Response(200, json={"id": "ctx-1", "language": "python", "cwd": "/home/user"})
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
            rt = await client.runtime.create(template="python-3.14-base-small")
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
    async def test_write_files(self, mock_api):
        mock_api.post(url__regex=rf"{SB}/{VALID_UUID}/files").mock(
            return_value=httpx.Response(200, json=[
                {"path": "/tmp/a.py", "name": "a.py", "type": "file"},
            ])
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            entries = [WriteEntry(path="/tmp/a.py", data="code")]
            resp = await client.runtime.file.write_many(VALID_UUID, entries)
            assert len(resp.files) == 1

    @pytest.mark.asyncio
    async def test_write_files_empty(self, mock_api):
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            resp = await client.runtime.file.write_many(VALID_UUID, [])
            assert resp.files == []
