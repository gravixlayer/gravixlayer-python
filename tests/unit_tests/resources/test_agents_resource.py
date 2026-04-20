"""
Tests for agent helpers and Agents / AsyncAgents resources (mocked HTTP).

Covers: _load_dotenv, _create_source_archive, sync/async build, status, wait,
deploy-from-template, get, destroy, invoke.
"""

import io
import json
import tarfile

import httpx
import pytest

from tests.utils import TEST_API_KEY, TEST_BASE_URL, AGENTS_BASE

from gravixlayer import GravixLayer, AsyncGravixLayer
from gravixlayer.resources.agents import (
    Agents,
    AgentBuildError,
    AgentBuildTimeoutError,
    _create_source_archive,
    _load_dotenv,
)
from gravixlayer.types.agents import AgentBuildStatusResponse


def _sample_build_json():
    return {
        "build_id": "build-agent-1",
        "template_id": "tmpl-1",
        "status": "started",
        "message": "queued",
    }


def _sample_status_json(status="running", phase="building"):
    return {
        "build_id": "build-agent-1",
        "template_id": "tmpl-1",
        "status": status,
        "phase": phase,
        "progress_percent": 50 if status == "running" else 100,
    }


def _sample_deploy_json():
    return {
        "agent_id": "ag-1",
        "runtime_id": "rt-1",
        "endpoint": "https://agent.example.com",
        "a2a_endpoint": "",
        "mcp_endpoint": "",
        "agent_card_url": "",
        "internal_endpoint": "",
        "status": "active",
        "dns_status": "active",
    }


def _sample_endpoint_json():
    return {
        "agent_id": "ag-1",
        "endpoint": "https://agent.example.com",
        "internal_endpoint": "http://10.0.0.1",
        "protocols": {"http": "https://agent.example.com"},
        "agent_card_url": "",
        "health": "healthy",
        "dns_status": "active",
    }


# ===================================================================
# Helpers — dotenv and archive
# ===================================================================


class TestLoadDotenv:
    def test_missing_file_returns_empty(self, tmp_path):
        assert _load_dotenv(tmp_path) == {}

    def test_parses_key_value_and_comments(self, tmp_path):
        p = tmp_path / ".env"
        p.write_text(
            "# comment\n\nKEY=value\nQUOTED=\"hello world\"\n"
        )
        d = _load_dotenv(tmp_path)
        assert d["KEY"] == "value"
        assert d["QUOTED"] == "hello world"

    def test_skips_lines_without_equals(self, tmp_path):
        (tmp_path / ".env").write_text("noequals\nA=1\n")
        assert _load_dotenv(tmp_path) == {"A": "1"}


class TestCreateSourceArchive:
    def test_creates_non_empty_tar_gz(self, tmp_path):
        (tmp_path / "main.py").write_text("print(1)\n")
        raw = _create_source_archive(tmp_path)
        buf = io.BytesIO(raw)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            names = tar.getnames()
        assert any(n.endswith("main.py") for n in names)

    def test_raises_if_not_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        with pytest.raises(ValueError, match="directory"):
            _create_source_archive(f)

    def test_raises_if_missing(self):
        with pytest.raises(FileNotFoundError):
            _create_source_archive("/nonexistent/path/agent")


# ===================================================================
# Sync Agents — API
# ===================================================================


class TestSyncAgentsAPI:
    @pytest.fixture()
    def client(self, mock_api):
        c = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        yield c
        c.close()

    def test_client_has_agents(self, client):
        assert isinstance(client.agents, Agents)

    def test_build_from_source(self, client, mock_api, tmp_path):
        (tmp_path / "app.py").write_text("# app\n")
        mock_api.post(f"{AGENTS_BASE}/template/build-agent").mock(
            return_value=httpx.Response(202, json=_sample_build_json())
        )
        resp = client.agents.build(tmp_path, name="my-agent", framework="langgraph")
        assert resp.build_id == "build-agent-1"
        req = mock_api.calls[-1].request
        assert req.method == "POST"
        assert "multipart/form-data" in req.headers.get("content-type", "")

    def test_get_build_status(self, client, mock_api):
        mock_api.get(f"{AGENTS_BASE}/template/builds/build-agent-1/status").mock(
            return_value=httpx.Response(200, json=_sample_status_json())
        )
        st = client.agents.get_build_status("build-agent-1")
        assert st.status == "running"
        assert st.phase == "building"

    def test_wait_for_build_success(self, client, mock_api):
        mock_api.get(f"{AGENTS_BASE}/template/builds/b1/status").mock(
            return_value=httpx.Response(
                200,
                json=_sample_status_json(status="completed", phase="completed"),
            )
        )
        final = client.agents.wait_for_build("b1", poll_interval_secs=0.01, timeout_secs=5)
        assert final.is_success is True

    def test_wait_for_build_failure_raises(self, client, mock_api):
        mock_api.get(f"{AGENTS_BASE}/template/builds/b1/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    **_sample_status_json(status="failed", phase="building"),
                    "error": "compile error",
                },
            )
        )
        with pytest.raises(AgentBuildError, match="compile error"):
            client.agents.wait_for_build("b1", poll_interval_secs=0.01, timeout_secs=5)

    def test_wait_for_build_timeout(self, client, mock_api):
        mock_api.get(f"{AGENTS_BASE}/template/builds/b1/status").mock(
            return_value=httpx.Response(200, json=_sample_status_json())
        )
        with pytest.raises(AgentBuildTimeoutError) as ei:
            client.agents.wait_for_build("b1", poll_interval_secs=0.01, timeout_secs=0)
        assert ei.value.timeout_secs == 0

    def test_deploy_from_template_id(self, client, mock_api):
        mock_api.post(f"{AGENTS_BASE}/deploy").mock(
            return_value=httpx.Response(201, json=_sample_deploy_json())
        )
        dep = client.agents.deploy(template_id="tmpl-xyz")
        assert dep.agent_id == "ag-1"
        assert "agent.example.com" in dep.endpoint
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["template_id"] == "tmpl-xyz"

    def test_deploy_validation_errors(self, client):
        with pytest.raises(ValueError, match="Either"):
            client.agents.deploy()
        with pytest.raises(ValueError, match="not both"):
            client.agents.deploy(source=".", template_id="x", name="n")

    def test_get_endpoint(self, client, mock_api):
        mock_api.get(f"{AGENTS_BASE}/ag-1/endpoint").mock(
            return_value=httpx.Response(200, json=_sample_endpoint_json())
        )
        info = client.agents.get("ag-1")
        assert info.agent_id == "ag-1"
        assert info.endpoint.startswith("https://")

    def test_destroy(self, client, mock_api):
        mock_api.delete(f"{AGENTS_BASE}/ag-1").mock(
            return_value=httpx.Response(200, json={"agent_id": "ag-1", "status": "deleted"})
        )
        r = client.agents.destroy("ag-1")
        assert r.agent_id == "ag-1"

    def test_invoke(self, client, mock_api):
        mock_api.get(f"{AGENTS_BASE}/ag-1/endpoint").mock(
            return_value=httpx.Response(200, json=_sample_endpoint_json())
        )
        mock_api.post("https://agent.example.com/invoke").mock(
            return_value=httpx.Response(200, json={"ok": True, "out": "hi"})
        )
        out = client.agents.invoke("ag-1", input={"prompt": "hello"})
        assert out["ok"] is True


# ===================================================================
# Async Agents — API
# ===================================================================


class TestAsyncAgentsAPI:
    @pytest.mark.asyncio
    async def test_build_and_status(self, mock_api, tmp_path):
        (tmp_path / "main.py").write_text("x")
        mock_api.post(f"{AGENTS_BASE}/template/build-agent").mock(
            return_value=httpx.Response(202, json=_sample_build_json())
        )
        mock_api.get(f"{AGENTS_BASE}/template/builds/build-agent-1/status").mock(
            return_value=httpx.Response(200, json=_sample_status_json())
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            br = await client.agents.build(tmp_path, name="n")
            assert br.build_id == "build-agent-1"
            st = await client.agents.get_build_status(br.build_id)
            assert st.build_id == "build-agent-1"

    @pytest.mark.asyncio
    async def test_deploy_template_and_invoke(self, mock_api):
        mock_api.post(f"{AGENTS_BASE}/deploy").mock(
            return_value=httpx.Response(201, json=_sample_deploy_json())
        )
        mock_api.get(f"{AGENTS_BASE}/ag-1/endpoint").mock(
            return_value=httpx.Response(200, json=_sample_endpoint_json())
        )
        mock_api.post("https://agent.example.com/invoke").mock(
            return_value=httpx.Response(200, json={"async": True})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            dep = await client.agents.deploy(template_id="tmpl-xyz")
            assert dep.agent_id == "ag-1"
            out = await client.agents.invoke(dep.agent_id, input={})
            assert out["async"] is True


# ===================================================================
# Exception types
# ===================================================================


class TestAgentExceptionTypes:
    def test_build_error_attrs(self):
        st = AgentBuildStatusResponse(
            build_id="b",
            template_id="t",
            status="failed",
            phase="x",
            progress_percent=0,
            error="e",
        )
        err = AgentBuildError("b1", "oops", status=st)
        assert err.build_id == "b1"
        assert err.status is st

    def test_timeout_error(self):
        err = AgentBuildTimeoutError("b2", 120)
        assert err.timeout_secs == 120
        assert "120" in str(err)
