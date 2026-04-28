"""Tests for gravixlayer.types.agents — enums, dataclasses, and API parsers."""

from gravixlayer.types.agents import (
    AgentBuildStatus,
    AgentBuildPhase,
    AgentFramework,
    AgentProtocol,
    AgentSkill,
    AgentCapabilities,
    AgentCard,
    AgentBuildRequest,
    AgentBuildResponse,
    AgentBuildStatusResponse,
    AgentDeployRequest,
    AgentDeployResponse,
    AgentEndpoint,
    AgentDestroyResponse,
    _parse_build_response,
    _parse_build_status,
    _parse_deploy_response,
    _parse_agent_endpoint,
    _parse_destroy_response,
)


class TestAgentBuildStatusResponseProps:
    def test_terminal_completed(self):
        s = AgentBuildStatusResponse(
            build_id="b1",
            template_id="t1",
            status=AgentBuildStatus.COMPLETED.value,
            phase=AgentBuildPhase.COMPLETED.value,
            progress_percent=100,
        )
        assert s.is_terminal is True
        assert s.is_success is True

    def test_terminal_failed(self):
        s = AgentBuildStatusResponse(
            build_id="b1",
            template_id="t1",
            status=AgentBuildStatus.FAILED.value,
            phase="building",
            progress_percent=10,
            error="x",
        )
        assert s.is_terminal is True
        assert s.is_success is False

    def test_not_terminal_running(self):
        s = AgentBuildStatusResponse(
            build_id="b1",
            template_id="t1",
            status=AgentBuildStatus.RUNNING.value,
            phase="building",
            progress_percent=50,
        )
        assert s.is_terminal is False


class TestAgentBuildRequestToDict:
    def test_minimal_only_name(self):
        d = AgentBuildRequest(name="my-agent").to_dict()
        assert d == {"name": "my-agent"}

    def test_includes_optional_fields_when_set(self):
        d = AgentBuildRequest(
            name="n",
            description="d",
            framework="langgraph",
            ports=[8000],
            vcpu_count=2,
            memory_mb=512,
            disk_mb=1024,
            environment={"A": "1"},
            ready_timeout_secs=30,
            tags={"t": "v"},
        ).to_dict()
        assert d["framework"] == "langgraph"
        assert d["ports"] == [8000]
        assert d["vcpu_count"] == 2
        assert d["ready_timeout_secs"] == 30


class TestAgentDeployRequestToDict:
    def test_template_only(self):
        d = AgentDeployRequest(template_id="tid-1").to_dict()
        assert d == {"template_id": "tid-1"}

    def test_with_agent_card(self):
        card = AgentCard(
            name="c",
            description="d",
            version="1",
            skills=[AgentSkill(id="s1", name="Skill")],
        )
        d = AgentDeployRequest(template_id="t", agent_card=card).to_dict()
        assert d["template_id"] == "t"
        assert "agent_card" in d
        assert d["agent_card"]["name"] == "c"
        assert d["agent_card"]["skills"][0]["id"] == "s1"


class TestParsers:
    def test_parse_build_response(self):
        r = _parse_build_response(
            {
                "build_id": "b1",
                "template_id": "t1",
                "status": "started",
                "message": "ok",
            }
        )
        assert isinstance(r, AgentBuildResponse)
        assert r.build_id == "b1"
        assert r.template_id == "t1"

    def test_parse_build_status(self):
        r = _parse_build_status(
            {
                "build_id": "b1",
                "template_id": "t1",
                "status": "running",
                "phase": "building",
                "progress_percent": 42,
            }
        )
        assert r.progress_percent == 42

    def test_parse_deploy_response(self):
        r = _parse_deploy_response(
            {
                "agent_id": "a1",
                "runtime_id": "r1",
                "endpoint": "https://e/",
                "a2a_endpoint": "",
                "mcp_endpoint": "",
                "agent_card_url": "",
                "internal_endpoint": "",
                "status": "active",
                "dns_status": "active",
            }
        )
        assert r.agent_id == "a1"
        assert r.endpoint == "https://e/"

    def test_parse_agent_endpoint(self):
        r = _parse_agent_endpoint(
            {
                "agent_id": "a1",
                "endpoint": "https://pub/",
                "internal_endpoint": "http://int/",
                "protocols": {"http": "https://pub/"},
                "agent_card_url": "https://card",
                "health": "healthy",
                "dns_status": "active",
            }
        )
        assert r.protocols["http"] == "https://pub/"

    def test_parse_destroy_response(self):
        r = _parse_destroy_response({"agent_id": "a1", "status": "deleted"})
        assert r.agent_id == "a1"
        assert r.status == "deleted"


class TestAgentCapabilities:
    def test_to_dict_omits_false(self):
        assert AgentCapabilities().to_dict() == {}

    def test_to_dict_includes_true_flags(self):
        d = AgentCapabilities(streaming=True, push_notifications=True).to_dict()
        assert d["streaming"] is True
        assert d["push_notifications"] is True


class TestEnums:
    def test_agent_framework_values(self):
        assert AgentFramework.LANGGRAPH.value == "langgraph"
        assert AgentFramework.LANGCHAIN.value == "langchain"
        assert AgentFramework.GOOGLE_ADK.value == "google-adk"
        assert AgentFramework.OPENAI_AGENTS.value == "openai-agents"
        assert AgentFramework.STRANDS.value == "strands"
        assert AgentProtocol.A2A.value == "a2a"
