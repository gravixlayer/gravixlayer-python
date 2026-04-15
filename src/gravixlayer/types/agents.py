"""
Type definitions for Agent Deployment API.

Provides dataclasses for agent builds, deployments, endpoints, and invocations.
Aligned with the backend agent endpoint API contract (Go handlers).
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentBuildStatus(str, Enum):
    """Build lifecycle status values."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentBuildPhase(str, Enum):
    """Build phases reported by the backend."""
    INITIALIZING = "initializing"
    PREPARING = "preparing"
    BUILDING = "building"
    FINALIZING = "finalizing"
    COMPLETED = "completed"


class AgentDeployStatus(str, Enum):
    """Agent deployment status values."""
    STARTING = "starting"
    ACTIVE = "active"
    DELETING = "deleting"
    DELETED = "deleted"


class AgentDNSStatus(str, Enum):
    """DNS propagation status."""
    PENDING = "pending"
    PROPAGATING = "propagating"
    ACTIVE = "active"
    FAILED = "failed"


class AgentHealthStatus(str, Enum):
    """Agent health status values."""
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AgentFramework(str, Enum):
    """Supported agent frameworks."""
    LANGGRAPH = "langgraph"
    CREWAI = "crewai"
    GOOGLE_ADK = "google-adk"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    A2A = "a2a"
    PYTHON = "python"


# ---------------------------------------------------------------------------
# Agent Card types (A2A v1.0 protocol)
# ---------------------------------------------------------------------------

@dataclass
class AgentSkill:
    """A skill advertised by an agent in its A2A Agent Card."""
    id: str
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"id": self.id, "name": self.name}
        if self.description:
            result["description"] = self.description
        if self.tags:
            result["tags"] = self.tags
        if self.examples:
            result["examples"] = self.examples
        return result


@dataclass
class AgentCapabilities:
    """Agent capabilities declaration (A2A spec)."""
    streaming: bool = False
    push_notifications: bool = False
    state_transition_history: bool = False

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if self.streaming:
            result["streaming"] = self.streaming
        if self.push_notifications:
            result["push_notifications"] = self.push_notifications
        if self.state_transition_history:
            result["state_transition_history"] = self.state_transition_history
        return result


@dataclass
class AgentCard:
    """A2A Agent Card describing agent capabilities."""
    name: str
    description: str
    version: str = ""
    skills: List[AgentSkill] = field(default_factory=list)
    capabilities: Optional[AgentCapabilities] = None
    default_input_modes: List[str] = field(default_factory=list)
    default_output_modes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"name": self.name, "description": self.description}
        if self.version:
            result["version"] = self.version
        if self.skills:
            result["skills"] = [s.to_dict() for s in self.skills]
        caps = self.capabilities or AgentCapabilities()
        result["capabilities"] = caps.to_dict()
        if self.default_input_modes:
            result["default_input_modes"] = self.default_input_modes
        if self.default_output_modes:
            result["default_output_modes"] = self.default_output_modes
        return result


# ---------------------------------------------------------------------------
# Build request/response types
# ---------------------------------------------------------------------------

@dataclass
class AgentBuildRequest:
    """Parameters for POST /v1/agents/template/build-agent (multipart).

    Used by ``Agents.build()`` to upload agent project source.
    """
    name: str
    description: str = ""
    entrypoint: str = ""
    python_version: str = ""
    framework: str = ""
    ports: List[int] = field(default_factory=list)
    vcpu_count: int = 0
    memory_mb: int = 0
    disk_mb: int = 0
    environment: Dict[str, str] = field(default_factory=dict)
    start_cmd: str = ""
    ready_cmd: str = ""
    ready_timeout_secs: int = 0
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"name": self.name}
        if self.description:
            result["description"] = self.description
        if self.entrypoint:
            result["entrypoint"] = self.entrypoint
        if self.python_version:
            result["python_version"] = self.python_version
        if self.framework:
            result["framework"] = self.framework
        if self.ports:
            result["ports"] = self.ports
        if self.vcpu_count:
            result["vcpu_count"] = self.vcpu_count
        if self.memory_mb:
            result["memory_mb"] = self.memory_mb
        if self.disk_mb:
            result["disk_mb"] = self.disk_mb
        if self.environment:
            result["environment"] = self.environment
        if self.start_cmd:
            result["start_cmd"] = self.start_cmd
        if self.ready_cmd:
            result["ready_cmd"] = self.ready_cmd
        if self.ready_timeout_secs:
            result["ready_timeout_secs"] = self.ready_timeout_secs
        if self.tags:
            result["tags"] = self.tags
        return result


@dataclass
class AgentBuildResponse:
    """Response from POST /v1/agents/template/build-agent (202 Accepted)."""
    build_id: str
    template_id: str
    status: str
    message: str


@dataclass
class AgentBuildStatusResponse:
    """Response from GET /v1/agents/template/builds/:build_id/status."""
    build_id: str
    template_id: str
    status: str
    phase: str
    progress_percent: int
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            AgentBuildStatus.COMPLETED.value,
            AgentBuildStatus.FAILED.value,
        )

    @property
    def is_success(self) -> bool:
        return self.status == AgentBuildStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# Deploy request/response types
# ---------------------------------------------------------------------------

@dataclass
class AgentDeployRequest:
    """Parameters for POST /v1/agents/deploy."""
    template_id: str
    framework: str = ""
    entry_point: str = ""
    http_port: int = 0
    a2a_port: int = 0
    mcp_port: int = 0
    protocols: List[str] = field(default_factory=list)
    is_public: bool = False
    environment: Dict[str, str] = field(default_factory=dict)
    timeout: int = 0
    agent_card: Optional[AgentCard] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"template_id": self.template_id}
        if self.framework:
            result["framework"] = self.framework
        if self.entry_point:
            result["entry_point"] = self.entry_point
        if self.http_port:
            result["http_port"] = self.http_port
        if self.a2a_port:
            result["a2a_port"] = self.a2a_port
        if self.mcp_port:
            result["mcp_port"] = self.mcp_port
        if self.protocols:
            result["protocols"] = self.protocols
        if self.is_public:
            result["is_public"] = self.is_public
        if self.environment:
            result["environment"] = self.environment
        if self.timeout:
            result["timeout"] = self.timeout
        if self.agent_card is not None:
            result["agent_card"] = self.agent_card.to_dict()
        return result


@dataclass
class AgentDeployResponse:
    """Response from POST /v1/agents/deploy (201 Created)."""
    agent_id: str
    runtime_id: str
    endpoint: str
    a2a_endpoint: str
    mcp_endpoint: str
    agent_card_url: str
    internal_endpoint: str
    status: str
    dns_status: str


@dataclass
class AgentEndpoint:
    """Response from GET /v1/agents/:agent_id/endpoint."""
    agent_id: str
    endpoint: str
    internal_endpoint: str
    protocols: Dict[str, str]
    agent_card_url: str
    health: str
    dns_status: str


@dataclass
class AgentDestroyResponse:
    """Response from DELETE /v1/agents/:agent_id."""
    agent_id: str
    status: str


# ---------------------------------------------------------------------------
# API response parsers
# ---------------------------------------------------------------------------

def _parse_build_response(data: Dict[str, Any]) -> AgentBuildResponse:
    return AgentBuildResponse(
        build_id=data["build_id"],
        template_id=data["template_id"],
        status=data.get("status", ""),
        message=data.get("message", ""),
    )


def _parse_build_status(data: Dict[str, Any]) -> AgentBuildStatusResponse:
    return AgentBuildStatusResponse(
        build_id=data["build_id"],
        template_id=data["template_id"],
        status=data.get("status", ""),
        phase=data.get("phase", ""),
        progress_percent=data.get("progress_percent", 0),
        error=data.get("error"),
        started_at=data.get("started_at"),
        completed_at=data.get("completed_at"),
    )


def _parse_deploy_response(data: Dict[str, Any]) -> AgentDeployResponse:
    return AgentDeployResponse(
        agent_id=data["agent_id"],
        runtime_id=data.get("runtime_id", ""),
        endpoint=data.get("endpoint", ""),
        a2a_endpoint=data.get("a2a_endpoint", ""),
        mcp_endpoint=data.get("mcp_endpoint", ""),
        agent_card_url=data.get("agent_card_url", ""),
        internal_endpoint=data.get("internal_endpoint", ""),
        status=data.get("status", ""),
        dns_status=data.get("dns_status", ""),
    )


def _parse_agent_endpoint(data: Dict[str, Any]) -> AgentEndpoint:
    return AgentEndpoint(
        agent_id=data["agent_id"],
        endpoint=data.get("endpoint", ""),
        internal_endpoint=data.get("internal_endpoint", ""),
        protocols=data.get("protocols", {}),
        agent_card_url=data.get("agent_card_url", ""),
        health=data.get("health", ""),
        dns_status=data.get("dns_status", ""),
    )


def _parse_destroy_response(data: Dict[str, Any]) -> AgentDestroyResponse:
    return AgentDestroyResponse(
        agent_id=data.get("agent_id", ""),
        status=data.get("status", ""),
    )
