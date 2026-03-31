"""
Tests for template types and resources.

Covers: TemplateBuilder fluent API, validation, serialization,
BuildStep, enums, sync Templates resource, async AsyncTemplates resource,
build_and_wait polling, error/timeout handling, edge cases, backend
field alignment, import verification.
"""

import base64
import json
import os
import time
import tempfile
import pytest
import httpx
import respx

from conftest import (
    TEST_API_KEY,
    TEST_BASE_URL,
    AGENTS_BASE,
    make_template_info,
    make_build_response,
    make_build_status,
)

from gravixlayer.types.templates import (
    BuildStepType,
    BuildStep,
    TemplateBuildStatusEnum,
    TemplateBuildPhase,
    TemplateBuildResponse,
    TemplateBuildStatus,
    TemplateInfo,
    TemplateSnapshot,
    TemplateListResponse,
    TemplateDeleteResponse,
    BuildLogEntry,
    TemplateBuilder,
)
from gravixlayer.resources.templates import Templates, TemplateBuildError, TemplateBuildTimeoutError
from gravixlayer.resources.async_templates import AsyncTemplates, AsyncTemplateBuildError, AsyncTemplateBuildTimeoutError
from gravixlayer import GravixLayer, AsyncGravixLayer


TMPL_BASE = f"{AGENTS_BASE}/template"


# ===================================================================
# BuildStepType Enum
# ===================================================================


class TestBuildStepType:
    def test_values(self):
        assert BuildStepType.RUN == "run"
        assert BuildStepType.PIP_INSTALL == "pip_install"
        assert BuildStepType.NPM_INSTALL == "npm_install"
        assert BuildStepType.APT_INSTALL == "apt_install"
        assert BuildStepType.BUN_INSTALL == "bun_install"
        assert BuildStepType.COPY_FILE == "copy_file"
        assert BuildStepType.GIT_CLONE == "git_clone"
        assert BuildStepType.MKDIR == "mkdir"

    def test_is_string(self):
        assert isinstance(BuildStepType.RUN, str)


# ===================================================================
# BuildStep
# ===================================================================


class TestBuildStep:
    def test_to_dict_basic(self):
        step = BuildStep(type="run", args=["echo hello"])
        d = step.to_dict()
        assert d == {"type": "run", "args": ["echo hello"]}

    def test_to_dict_with_content(self):
        step = BuildStep(type="copy_file", args=["/app/main.py"], content=b"print('hello')")
        d = step.to_dict()
        assert d["content"] == base64.b64encode(b"print('hello')").decode("ascii")

    def test_to_dict_with_options(self):
        step = BuildStep(type="git_clone", args=["https://github.com/user/repo"], options={"branch": "main"})
        d = step.to_dict()
        assert d["options"]["branch"] == "main"

    def test_to_dict_omits_none_content(self):
        step = BuildStep(type="run", args=["ls"])
        d = step.to_dict()
        assert "content" not in d

    def test_to_dict_omits_none_options(self):
        step = BuildStep(type="run", args=["ls"])
        d = step.to_dict()
        assert "options" not in d


# ===================================================================
# TemplateBuildStatus
# ===================================================================


class TestTemplateBuildStatus:
    def test_is_terminal_completed(self):
        s = TemplateBuildStatus(
            build_id="b1", template_id="t1", status="completed",
            phase="completed", progress_percent=100
        )
        assert s.is_terminal is True
        assert s.is_success is True

    def test_is_terminal_failed(self):
        s = TemplateBuildStatus(
            build_id="b1", template_id="t1", status="failed",
            phase="building", progress_percent=50, error="OOM"
        )
        assert s.is_terminal is True
        assert s.is_success is False

    def test_not_terminal_running(self):
        s = TemplateBuildStatus(
            build_id="b1", template_id="t1", status="running",
            phase="building", progress_percent=50
        )
        assert s.is_terminal is False

    def test_not_terminal_pending(self):
        s = TemplateBuildStatus(
            build_id="b1", template_id="t1", status="pending",
            phase="initializing", progress_percent=0
        )
        assert s.is_terminal is False


# ===================================================================
# TemplateBuildStatusEnum and Phase
# ===================================================================


class TestBuildEnums:
    def test_status_values(self):
        assert TemplateBuildStatusEnum.PENDING == "pending"
        assert TemplateBuildStatusEnum.COMPLETED == "completed"
        assert TemplateBuildStatusEnum.FAILED == "failed"

    def test_phase_values(self):
        assert TemplateBuildPhase.INITIALIZING == "initializing"
        assert TemplateBuildPhase.BUILDING == "building"
        assert TemplateBuildPhase.COMPLETED == "completed"


# ===================================================================
# TemplateBuilder — Fluent API
# ===================================================================


class TestTemplateBuilder:
    def test_minimal_template(self):
        builder = TemplateBuilder("test-template")
        d = builder.to_dict()
        assert d["name"] == "test-template"
        assert d["vcpu_count"] == 2
        assert d["memory_mb"] == 512
        assert d["disk_mb"] == 4096

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name is required"):
            TemplateBuilder("")

    def test_from_image(self):
        d = TemplateBuilder("t").from_image("python:3.11-slim").to_dict()
        assert d["docker_image"] == "python:3.11-slim"

    def test_dockerfile(self):
        d = TemplateBuilder("t").dockerfile("FROM ubuntu:22.04").to_dict()
        assert d["dockerfile"] == "FROM ubuntu:22.04"

    def test_cannot_set_both_image_and_dockerfile(self):
        with pytest.raises(ValueError, match="Cannot set dockerfile"):
            TemplateBuilder("t").from_image("python:3.11").dockerfile("FROM x")

    def test_cannot_set_both_dockerfile_and_image(self):
        with pytest.raises(ValueError, match="Cannot set docker_image"):
            TemplateBuilder("t").dockerfile("FROM x").from_image("python:3.11")

    def test_to_dict_raises_if_both_set(self):
        builder = TemplateBuilder("t")
        builder._docker_image = "python:3.11"
        builder._dockerfile = "FROM x"
        with pytest.raises(ValueError, match="Cannot specify both"):
            builder.to_dict()

    def test_vcpu(self):
        d = TemplateBuilder("t").vcpu(4).to_dict()
        assert d["vcpu_count"] == 4

    def test_vcpu_invalid(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            TemplateBuilder("t").vcpu(0)

    def test_memory(self):
        d = TemplateBuilder("t").memory(1024).to_dict()
        assert d["memory_mb"] == 1024

    def test_memory_invalid(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            TemplateBuilder("t").memory(0)

    def test_disk(self):
        d = TemplateBuilder("t").disk(8192).to_dict()
        assert d["disk_mb"] == 8192

    def test_disk_invalid(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            TemplateBuilder("t").disk(-1)

    def test_template_id(self):
        d = TemplateBuilder("t").template_id("custom-id").to_dict()
        assert d["template_id"] == "custom-id"

    def test_start_cmd(self):
        d = TemplateBuilder("t").start_cmd("python serve.py").to_dict()
        assert d["start_cmd"] == "python serve.py"

    def test_ready_cmd(self):
        d = TemplateBuilder("t").ready_cmd("curl localhost:8080", timeout_secs=120).to_dict()
        assert d["ready_cmd"] == "curl localhost:8080"
        assert d["ready_timeout_secs"] == 120

    def test_env_single(self):
        d = TemplateBuilder("t").env("KEY", "VALUE").to_dict()
        assert d["environment"]["KEY"] == "VALUE"

    def test_envs_bulk(self):
        d = TemplateBuilder("t").envs({"A": "1", "B": "2"}).to_dict()
        assert d["environment"] == {"A": "1", "B": "2"}

    def test_tags(self):
        d = TemplateBuilder("t").tags({"team": "ml"}).to_dict()
        assert d["tags"]["team"] == "ml"

    def test_description(self):
        d = TemplateBuilder("t", description="A test template").to_dict()
        assert d["description"] == "A test template"

    # Build steps
    def test_run_step(self):
        d = TemplateBuilder("t").run("echo hello").to_dict()
        assert len(d["build_steps"]) == 1
        assert d["build_steps"][0]["type"] == "run"

    def test_pip_install(self):
        d = TemplateBuilder("t").pip_install("numpy", "pandas").to_dict()
        step = d["build_steps"][0]
        assert step["type"] == "pip_install"
        assert step["args"] == ["numpy", "pandas"]

    def test_pip_install_empty_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            TemplateBuilder("t").pip_install()

    def test_npm_install(self):
        d = TemplateBuilder("t").npm_install("express").to_dict()
        assert d["build_steps"][0]["type"] == "npm_install"

    def test_npm_install_empty_raises(self):
        with pytest.raises(ValueError):
            TemplateBuilder("t").npm_install()

    def test_apt_install(self):
        d = TemplateBuilder("t").apt_install("git", "curl").to_dict()
        assert d["build_steps"][0]["type"] == "apt_install"

    def test_apt_install_empty_raises(self):
        with pytest.raises(ValueError):
            TemplateBuilder("t").apt_install()

    def test_bun_install(self):
        d = TemplateBuilder("t").bun_install("hono").to_dict()
        assert d["build_steps"][0]["type"] == "bun_install"

    def test_bun_install_empty_raises(self):
        with pytest.raises(ValueError):
            TemplateBuilder("t").bun_install()

    def test_copy_file_inline(self):
        d = TemplateBuilder("t").copy_file("print('hello')", "/app/main.py").to_dict()
        step = d["build_steps"][0]
        assert step["type"] == "copy_file"
        assert step["args"] == ["/app/main.py"]
        decoded = base64.b64decode(step["content"]).decode("utf-8")
        assert decoded == "print('hello')"

    def test_copy_file_bytes(self):
        d = TemplateBuilder("t").copy_file(b"\x00\x01", "/app/data.bin").to_dict()
        step = d["build_steps"][0]
        assert base64.b64decode(step["content"]) == b"\x00\x01"

    def test_copy_file_from_disk(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("disk_content")
            f.flush()
            d = TemplateBuilder("t").copy_file(f.name, "/app/f.py").to_dict()
        os.unlink(f.name)
        decoded = base64.b64decode(d["build_steps"][0]["content"]).decode("utf-8")
        assert decoded == "disk_content"

    def test_copy_file_with_mode_and_user(self):
        d = TemplateBuilder("t").copy_file("data", "/app/f", mode="0755", user="root").to_dict()
        step = d["build_steps"][0]
        assert step["options"]["mode"] == "0755"
        assert step["options"]["user"] == "root"

    def test_copy_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a small directory structure
            os.makedirs(os.path.join(tmpdir, "sub"))
            with open(os.path.join(tmpdir, "a.py"), "w") as f:
                f.write("file_a")
            with open(os.path.join(tmpdir, "sub", "b.py"), "w") as f:
                f.write("file_b")

            d = TemplateBuilder("t").copy_dir(tmpdir, "/app").to_dict()
            assert len(d["build_steps"]) == 2
            paths = [s["args"][0] for s in d["build_steps"]]
            assert "/app/a.py" in paths
            assert "/app/sub/b.py" in paths

    def test_copy_dir_not_found(self):
        with pytest.raises(FileNotFoundError):
            TemplateBuilder("t").copy_dir("/nonexistent", "/app")

    def test_copy_dir_not_a_directory(self):
        with tempfile.NamedTemporaryFile() as f:
            with pytest.raises(NotADirectoryError):
                TemplateBuilder("t").copy_dir(f.name, "/app")

    def test_git_clone(self):
        d = TemplateBuilder("t").git_clone(
            "https://github.com/user/repo",
            dest="/app",
            branch="main",
            depth=1,
        ).to_dict()
        step = d["build_steps"][0]
        assert step["type"] == "git_clone"
        assert step["args"] == ["https://github.com/user/repo", "/app"]
        assert step["options"]["branch"] == "main"
        assert step["options"]["depth"] == "1"

    def test_mkdir_step(self):
        d = TemplateBuilder("t").mkdir("/app/data", mode="0755").to_dict()
        step = d["build_steps"][0]
        assert step["type"] == "mkdir"
        assert step["args"] == ["/app/data"]
        assert step["options"]["mode"] == "0755"

    # Ready command helpers
    def test_wait_for_port(self):
        cmd = TemplateBuilder.wait_for_port(8080)
        assert "8080" in cmd

    def test_wait_for_url(self):
        cmd = TemplateBuilder.wait_for_url("http://localhost:8080/health")
        assert "localhost:8080" in cmd

    def test_wait_for_file(self):
        cmd = TemplateBuilder.wait_for_file("/tmp/ready")
        assert "/tmp/ready" in cmd

    def test_wait_for_process(self):
        cmd = TemplateBuilder.wait_for_process("python")
        assert "python" in cmd

    # Chaining
    def test_full_chain(self):
        d = (
            TemplateBuilder("ml-env", description="ML environment")
            .from_image("python:3.11-slim")
            .vcpu(4)
            .memory(2048)
            .disk(8192)
            .apt_install("git", "curl", "build-essential")
            .pip_install("numpy", "pandas", "scikit-learn")
            .run("mkdir -p /app")
            .copy_file("print('ready')", "/app/main.py")
            .env("PYTHONPATH", "/app")
            .start_cmd("python /app/main.py")
            .ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=120)
            .tags({"team": "ml", "env": "production"})
            .to_dict()
        )
        assert d["name"] == "ml-env"
        assert d["docker_image"] == "python:3.11-slim"
        assert d["vcpu_count"] == 4
        assert d["memory_mb"] == 2048
        assert d["disk_mb"] == 8192
        assert len(d["build_steps"]) == 4  # apt, pip, run, copy
        assert d["start_cmd"] == "python /app/main.py"
        assert d["environment"]["PYTHONPATH"] == "/app"
        assert d["tags"]["team"] == "ml"


# ===================================================================
# Sync Templates Resource
# ===================================================================


class TestSyncTemplatesResource:
    @pytest.fixture()
    def client(self, mock_api):
        c = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        yield c
        c.close()

    def test_build(self, client, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        builder = TemplateBuilder("test").from_image("python:3.11")
        resp = client.templates.build(builder)
        assert isinstance(resp, TemplateBuildResponse)
        assert resp.build_id == "build-001"

    def test_build_with_raw_dict(self, client, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        resp = client.templates.build({"name": "test", "docker_image": "python:3.11"})
        assert resp.build_id == "build-001"

    def test_get_build_status(self, client, mock_api):
        mock_api.get(f"{TMPL_BASE}/builds/build-001/status").mock(
            return_value=httpx.Response(200, json=make_build_status())
        )
        status = client.templates.get_build_status("build-001")
        assert isinstance(status, TemplateBuildStatus)
        assert status.is_success is True

    def test_list(self, client, mock_api):
        mock_api.get(url__regex=rf"{TMPL_BASE}\?").mock(
            return_value=httpx.Response(200, json={
                "templates": [make_template_info()],
                "limit": 100,
                "offset": 0,
            })
        )
        result = client.templates.list()
        assert isinstance(result, TemplateListResponse)
        assert len(result.templates) == 1
        assert result.templates[0].name == "python-base-v1"

    def test_get(self, client, mock_api):
        mock_api.get(f"{TMPL_BASE}/tmpl-001").mock(
            return_value=httpx.Response(200, json=make_template_info())
        )
        info = client.templates.get("tmpl-001")
        assert isinstance(info, TemplateInfo)
        assert info.id == "tmpl-001"

    def test_get_snapshot(self, client, mock_api):
        mock_api.get(f"{TMPL_BASE}/tmpl-001/snapshot").mock(
            return_value=httpx.Response(200, json={
                "template_id": "tmpl-001", "name": "python-base-v1",
                "description": "", "has_snapshot": True,
                "vcpu_count": 2, "memory_mb": 512, "created_at": "2025-01-01",
                "envd_version": "1.0.0", "snapshot_size_bytes": 1073741824,
            })
        )
        snap = client.templates.get_snapshot("tmpl-001")
        assert isinstance(snap, TemplateSnapshot)
        assert snap.has_snapshot is True
        assert snap.snapshot_size_bytes == 1073741824

    def test_delete(self, client, mock_api):
        mock_api.delete(f"{TMPL_BASE}/tmpl-001").mock(
            return_value=httpx.Response(204)
        )
        result = client.templates.delete("tmpl-001")
        assert isinstance(result, TemplateDeleteResponse)
        assert result.deleted is True
        assert result.template_id == "tmpl-001"


# ===================================================================
# Sync Templates Resource — build_and_wait
# ===================================================================


class TestSyncBuildAndWait:
    @pytest.fixture()
    def client(self, mock_api):
        c = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        yield c
        c.close()

    def test_build_and_wait_success(self, client, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        mock_api.get(f"{TMPL_BASE}/builds/build-001/status").mock(
            return_value=httpx.Response(200, json=make_build_status("completed"))
        )
        status = client.templates.build_and_wait(
            TemplateBuilder("test").from_image("python:3.11"),
            poll_interval_secs=0.01,
        )
        assert status.is_success is True

    def test_build_and_wait_failure(self, client, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        mock_api.get(f"{TMPL_BASE}/builds/build-001/status").mock(
            return_value=httpx.Response(200, json=make_build_status("failed", error="OOM"))
        )
        with pytest.raises(TemplateBuildError, match="failed"):
            client.templates.build_and_wait(
                TemplateBuilder("test").from_image("python:3.11"),
                poll_interval_secs=0.01,
            )

    def test_build_and_wait_timeout(self, client, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        mock_api.get(f"{TMPL_BASE}/builds/build-001/status").mock(
            return_value=httpx.Response(200, json=make_build_status("running"))
        )
        with pytest.raises(TemplateBuildTimeoutError):
            client.templates.build_and_wait(
                TemplateBuilder("test").from_image("python:3.11"),
                poll_interval_secs=0.01,
                timeout_secs=0,  # immediate timeout
            )

    def test_build_and_wait_with_callback(self, client, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        mock_api.get(f"{TMPL_BASE}/builds/build-001/status").mock(
            return_value=httpx.Response(200, json=make_build_status("completed"))
        )
        log_entries = []
        status = client.templates.build_and_wait(
            TemplateBuilder("test").from_image("python:3.11"),
            poll_interval_secs=0.01,
            on_status=lambda entry: log_entries.append(entry),
        )
        assert status.is_success is True
        assert len(log_entries) > 0
        assert any("started" in e.message.lower() or "completed" in e.message.lower() for e in log_entries)


# ===================================================================
# Sync Templates Build Errors
# ===================================================================


class TestTemplateBuildErrors:
    def test_build_error_message(self):
        err = TemplateBuildError("b1", "OOM killed")
        assert "b1" in str(err)
        assert "OOM killed" in str(err)
        assert err.build_id == "b1"

    def test_build_timeout_error(self):
        err = TemplateBuildTimeoutError("b1", 600)
        assert "600" in str(err)
        assert err.timeout_secs == 600

    def test_async_build_error(self):
        err = AsyncTemplateBuildError("b2", "disk full")
        assert "b2" in str(err)

    def test_async_build_timeout_error(self):
        err = AsyncTemplateBuildTimeoutError("b2", 300)
        assert err.timeout_secs == 300


# ===================================================================
# Async Templates Resource
# ===================================================================


class TestAsyncTemplatesResource:
    @pytest.mark.asyncio
    async def test_build(self, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            resp = await client.templates.build(TemplateBuilder("test").from_image("python:3.11"))
            assert resp.build_id == "build-001"

    @pytest.mark.asyncio
    async def test_get_build_status(self, mock_api):
        mock_api.get(f"{TMPL_BASE}/builds/build-001/status").mock(
            return_value=httpx.Response(200, json=make_build_status())
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            status = await client.templates.get_build_status("build-001")
            assert status.is_success is True

    @pytest.mark.asyncio
    async def test_list(self, mock_api):
        mock_api.get(url__regex=rf"{TMPL_BASE}\?").mock(
            return_value=httpx.Response(200, json={
                "templates": [make_template_info()],
                "limit": 100,
                "offset": 0,
            })
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.templates.list()
            assert len(result.templates) == 1

    @pytest.mark.asyncio
    async def test_get(self, mock_api):
        mock_api.get(f"{TMPL_BASE}/tmpl-001").mock(
            return_value=httpx.Response(200, json=make_template_info())
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            info = await client.templates.get("tmpl-001")
            assert info.name == "python-base-v1"

    @pytest.mark.asyncio
    async def test_get_snapshot(self, mock_api):
        mock_api.get(f"{TMPL_BASE}/tmpl-001/snapshot").mock(
            return_value=httpx.Response(200, json={
                "template_id": "tmpl-001", "name": "test",
                "description": "", "has_snapshot": True,
                "vcpu_count": 2, "memory_mb": 512, "created_at": "2025-01-01",
            })
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            snap = await client.templates.get_snapshot("tmpl-001")
            assert snap.has_snapshot is True

    @pytest.mark.asyncio
    async def test_delete(self, mock_api):
        mock_api.delete(f"{TMPL_BASE}/tmpl-001").mock(
            return_value=httpx.Response(204)
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.templates.delete("tmpl-001")
            assert result.deleted is True

    @pytest.mark.asyncio
    async def test_build_and_wait_success(self, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        mock_api.get(f"{TMPL_BASE}/builds/build-001/status").mock(
            return_value=httpx.Response(200, json=make_build_status("completed"))
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            status = await client.templates.build_and_wait(
                TemplateBuilder("test").from_image("python:3.11"),
                poll_interval_secs=0.01,
            )
            assert status.is_success is True

    @pytest.mark.asyncio
    async def test_build_and_wait_failure(self, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        mock_api.get(f"{TMPL_BASE}/builds/build-001/status").mock(
            return_value=httpx.Response(200, json=make_build_status("failed", error="disk full"))
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(AsyncTemplateBuildError, match="failed"):
                await client.templates.build_and_wait(
                    TemplateBuilder("test").from_image("python:3.11"),
                    poll_interval_secs=0.01,
                )

    @pytest.mark.asyncio
    async def test_build_and_wait_timeout(self, mock_api):
        mock_api.post(f"{TMPL_BASE}/build").mock(
            return_value=httpx.Response(202, json=make_build_response())
        )
        mock_api.get(f"{TMPL_BASE}/builds/build-001/status").mock(
            return_value=httpx.Response(200, json=make_build_status("running"))
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(AsyncTemplateBuildTimeoutError):
                await client.templates.build_and_wait(
                    TemplateBuilder("test").from_image("python:3.11"),
                    poll_interval_secs=0.01,
                    timeout_secs=0,
                )


# ===================================================================
# Supporting Template Types
# ===================================================================


class TestTemplateTypes:
    def test_template_build_response(self):
        r = TemplateBuildResponse(build_id="b1", template_id="t1", status="pending", message="Queued")
        assert r.build_id == "b1"

    def test_template_info(self):
        t = TemplateInfo(
            id="t1", name="test", description="desc",
            vcpu_count=2, memory_mb=512, disk_size_mb=4096,
            visibility="private", created_at="2025-01-01", updated_at="2025-01-01",
        )
        assert t.visibility == "private"

    def test_template_snapshot(self):
        s = TemplateSnapshot(
            template_id="t1", name="test", description="",
            has_snapshot=True, vcpu_count=2, memory_mb=512,
            created_at="2025-01-01", envd_version="1.0", snapshot_size_bytes=1024,
        )
        assert s.envd_version == "1.0"

    def test_template_list_response(self):
        r = TemplateListResponse(templates=[], limit=100, offset=0)
        assert r.limit == 100

    def test_template_delete_response(self):
        r = TemplateDeleteResponse(template_id="t1", deleted=True)
        assert r.deleted is True

    def test_build_log_entry(self):
        e = BuildLogEntry(level="error", message="Build failed")
        assert e.level == "error"
        assert e.timestamp is None


# ===================================================================
# Enum Completeness
# ===================================================================


class TestEnumCompleteness:
    def test_build_step_type_count(self):
        assert len(BuildStepType) == 8

    def test_build_step_type_json_serializable(self):
        payload = {"type": BuildStepType.RUN}
        assert '"run"' in json.dumps(payload)

    def test_build_status_enum_values(self):
        assert TemplateBuildStatusEnum.PENDING == "pending"
        assert TemplateBuildStatusEnum.STARTED == "started"
        assert TemplateBuildStatusEnum.RUNNING == "running"
        assert TemplateBuildStatusEnum.COMPLETED == "completed"
        assert TemplateBuildStatusEnum.FAILED == "failed"
        assert len(TemplateBuildStatusEnum) == 5

    def test_build_phase_enum_values(self):
        expected = {"initializing", "preparing", "building", "finalizing", "completed"}
        actual = {e.value for e in TemplateBuildPhase}
        assert actual == expected


# ===================================================================
# BuildStep Extras
# ===================================================================


class TestBuildStepExtras:
    def test_empty_args_default(self):
        assert BuildStep(type="run").to_dict()["args"] == []

    def test_empty_options_omitted(self):
        assert "options" not in BuildStep(type="run", args=["ls"], options={}).to_dict()


# ===================================================================
# TemplateBuildStatus — optional fields
# ===================================================================


class TestTemplateBuildStatusOptionals:
    def test_optional_fields_default_none(self):
        s = TemplateBuildStatus(
            build_id="b-1", template_id="t-1",
            status="pending", phase="initializing", progress_percent=0,
        )
        assert s.error is None
        assert s.started_at is None
        assert s.completed_at is None


# ===================================================================
# TemplateBuilder — Chaining (all methods return self)
# ===================================================================


class TestTemplateBuilderChaining:
    def test_all_methods_return_self(self):
        b = TemplateBuilder("chain-test")
        assert b.from_image("alpine") is b

        b2 = TemplateBuilder("chain-test-2")
        for method_call in [
            lambda: b2.vcpu(4),
            lambda: b2.memory(1024),
            lambda: b2.disk(8192),
            lambda: b2.start_cmd("echo ok"),
            lambda: b2.ready_cmd("true"),
            lambda: b2.env("K", "V"),
            lambda: b2.envs({"A": "B"}),
            lambda: b2.tags({"t": "v"}),
            lambda: b2.template_id("id-123"),
            lambda: b2.run("ls"),
            lambda: b2.pip_install("x"),
            lambda: b2.npm_install("y"),
            lambda: b2.apt_install("z"),
            lambda: b2.bun_install("w"),
            lambda: b2.copy_file("content", "/dest"),
            lambda: b2.git_clone("https://example.com"),
            lambda: b2.mkdir("/d"),
        ]:
            assert method_call() is b2


# ===================================================================
# TemplateBuilder — Step order and serialization
# ===================================================================


class TestTemplateBuilderSerialization:
    def test_step_order_preserved(self):
        d = (
            TemplateBuilder("t")
            .run("echo 1")
            .pip_install("a")
            .apt_install("b")
            .mkdir("/c")
            .copy_file("content", "/d")
            .npm_install("f")
            .bun_install("g")
            .git_clone("https://x.com")
            .to_dict()
        )
        types = [s["type"] for s in d["build_steps"]]
        assert types == [
            "run", "pip_install", "apt_install", "mkdir",
            "copy_file", "npm_install", "bun_install", "git_clone",
        ]

    def test_json_round_trip(self):
        d = (
            TemplateBuilder("json-test")
            .from_image("python:3.11-slim")
            .pip_install("numpy")
            .copy_file(b"\x00\x01\x02", "/f")
            .env("K", "V")
            .to_dict()
        )
        deserialized = json.loads(json.dumps(d))
        assert deserialized["name"] == "json-test"
        assert base64.b64decode(deserialized["build_steps"][1]["content"]) == b"\x00\x01\x02"

    def test_minimal_no_optional_keys(self):
        d = TemplateBuilder("bare").from_image("ubuntu:22.04").to_dict()
        assert "build_steps" not in d or d["build_steps"] == []
        assert "start_cmd" not in d or d["start_cmd"] is None


# ===================================================================
# Edge Cases
# ===================================================================


class TestEdgeCases:
    def test_unicode_content(self):
        content = "Hello cafe\nSpecial: @#$%^&*()"
        decoded = base64.b64decode(
            TemplateBuilder("t").copy_file(content, "/f").to_dict()["build_steps"][0]["content"]
        ).decode("utf-8")
        assert decoded == content

    def test_large_binary_round_trip(self):
        raw = os.urandom(100_000)
        decoded = base64.b64decode(
            TemplateBuilder("t").copy_file(raw, "/f").to_dict()["build_steps"][0]["content"]
        )
        assert decoded == raw

    def test_50_build_steps(self):
        b = TemplateBuilder("t").from_image("alpine")
        for i in range(50):
            b.run(f"echo step-{i}")
        assert len(b.to_dict()["build_steps"]) == 50

    def test_special_chars_in_env(self):
        envs = {
            "DB_URL": "postgres://user:p@ss=w0rd@host:5432/db",
            "PATH_EXTRA": "/usr/local/bin:/opt/bin",
        }
        d = TemplateBuilder("t").envs(envs).to_dict()
        assert d["environment"] == envs

    def test_multiline_run_command(self):
        cmd = "set -e\napt-get update\napt-get install -y python3"
        assert TemplateBuilder("t").run(cmd).to_dict()["build_steps"][0]["args"] == [cmd]

    def test_empty_string_copy_file(self):
        decoded = base64.b64decode(
            TemplateBuilder("t").copy_file("", "/f").to_dict()["build_steps"][0]["content"]
        )
        assert decoded == b""

    def test_build_step_type_enum_in_step(self):
        assert BuildStep(type=BuildStepType.PIP_INSTALL, args=["numpy"]).to_dict()["type"] == "pip_install"


# ===================================================================
# Backend Field Alignment
# ===================================================================


class TestBackendFieldAlignment:
    """SDK field names must match Go backend struct JSON tags."""

    def test_build_request_fields(self):
        d = (
            TemplateBuilder("align-test")
            .from_image("python:3.11")
            .vcpu(2).memory(512).disk(4096)
            .start_cmd("python app.py")
            .ready_cmd("true", timeout_secs=30)
            .envs({"KEY": "VAL"})
            .tags({"t": "v"})
            .run("echo ok")
            .template_id("custom-id")
            .to_dict()
        )
        expected_keys = {
            "name", "docker_image", "vcpu_count", "memory_mb", "disk_mb",
            "start_cmd", "ready_cmd", "ready_timeout_secs", "environment",
            "build_steps", "tags", "template_id",
        }
        assert set(d.keys()) == expected_keys

    def test_build_step_keys(self):
        d = BuildStep(type="copy_file", args=["/f"], content=b"x", options={"mode": "0644"}).to_dict()
        assert set(d.keys()) == {"type", "args", "content", "options"}

    def test_valid_step_types_match_backend(self):
        backend = {"run", "pip_install", "npm_install", "apt_install",
                    "bun_install", "copy_file", "git_clone", "mkdir"}
        assert {e.value for e in BuildStepType} == backend

    def test_status_values_superset(self):
        backend = {"pending", "running", "completed", "failed"}
        assert backend.issubset({e.value for e in TemplateBuildStatusEnum})


# ===================================================================
# Import Verification
# ===================================================================


class TestImports:
    """All public symbols importable from expected locations."""

    def test_types_templates(self):
        from gravixlayer.types.templates import (
            BuildStepType, BuildStep, TemplateBuildStatusEnum,
            TemplateBuildPhase, TemplateBuildResponse, TemplateBuildStatus,
            TemplateInfo, TemplateSnapshot, TemplateListResponse,
            TemplateDeleteResponse, BuildLogEntry, TemplateBuilder,
        )

    def test_resources_templates(self):
        from gravixlayer.resources.templates import (
            Templates, TemplateBuildError, TemplateBuildTimeoutError,
        )

    def test_top_level(self):
        from gravixlayer import (
            TemplateBuilder, Templates, TemplateBuildError,
            TemplateBuildTimeoutError, BuildStepType, TemplateBuildStatus,
            TemplateInfo,
        )

    def test_types_init(self):
        from gravixlayer.types import (
            BuildStepType, BuildStep, TemplateBuildStatusEnum,
            TemplateBuildPhase, TemplateBuildResponse, TemplateBuildStatus,
            TemplateInfo, TemplateSnapshot, TemplateListResponse,
            TemplateDeleteResponse, BuildLogEntry, TemplateBuilder,
        )


# ===================================================================
# Real-World Builder Payloads
# ===================================================================


class TestRealWorldBuilders:
    def test_python_ml_template_payload(self):
        d = (
            TemplateBuilder("python-ml-env", description="Python ML runtime")
            .from_image("python:3.11-slim")
            .vcpu(4)
            .memory(4096)
            .disk(16384)
            .envs({"PYTHONPATH": "/workspace", "PYTHONUNBUFFERED": "1"})
            .tags({"team": "ml", "env": "production"})
            .apt_install("git", "curl", "build-essential")
            .pip_install("numpy>=1.24", "pandas>=2.0", "scikit-learn")
            .mkdir("/workspace/models")
            .mkdir("/workspace/data")
            .copy_file("from setuptools import setup\nsetup(name='ml')\n", "/workspace/setup.py")
            .run("python -c 'import sys; print(sys.version)'")
            .start_cmd("uvicorn app:app --host 0.0.0.0 --port 8000")
            .ready_cmd(TemplateBuilder.wait_for_port(8000), timeout_secs=120)
            .to_dict()
        )
        assert d["name"] == "python-ml-env"
        assert d["docker_image"] == "python:3.11-slim"
        assert d["vcpu_count"] == 4
        assert d["memory_mb"] == 4096
        assert d["ready_timeout_secs"] == 120
        assert len(d["build_steps"]) == 6

    def test_node_express_template_payload(self):
        server_js = (
            "const express=require('express');\n"
            "const app=express();\n"
            "app.get('/health',(r,s)=>s.json({ok:true}));\n"
            "app.listen(3000);"
        )
        d = (
            TemplateBuilder("node-express-api", description="Node.js Express API")
            .from_image("node:20-slim")
            .vcpu(2)
            .memory(1024)
            .env("NODE_ENV", "production")
            .env("PORT", "3000")
            .tags({"runtime": "node", "framework": "express"})
            .apt_install("git", "curl")
            .npm_install("express", "cors", "helmet")
            .mkdir("/app")
            .copy_file(server_js, "/app/server.js")
            .copy_file('{"name":"api","main":"server.js"}', "/app/package.json")
            .run("cd /app && npm install --production")
            .start_cmd("node /app/server.js")
            .ready_cmd(TemplateBuilder.wait_for_url("http://localhost:3000/health"), timeout_secs=30)
            .to_dict()
        )
        assert d["docker_image"] == "node:20-slim"
        assert d["environment"]["NODE_ENV"] == "production"
        assert d["ready_timeout_secs"] == 30
        assert len(d["build_steps"]) == 6

    def test_dockerfile_template_payload(self):
        dockerfile = "FROM python:3.11-slim\nRUN pip install jupyter\nWORKDIR /workspace\n"
        d = (
            TemplateBuilder("jupyter-env")
            .dockerfile(dockerfile)
            .start_cmd("jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root")
            .ready_cmd(TemplateBuilder.wait_for_port(8888))
            .to_dict()
        )
        assert "dockerfile" in d
        assert "docker_image" not in d
