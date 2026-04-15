"""
Agent Deployment resource for synchronous client.

Provides methods for building agent templates from source, deploying agents,
invoking deployed agents, and managing agent lifecycle.

API endpoints:
    POST   /v1/agents/template/build-agent   (multipart: archive + metadata)
    GET    /v1/agents/template/builds/:build_id/status
    POST   /v1/agents/deploy
    GET    /v1/agents/:agent_id/endpoint
    DELETE /v1/agents/:agent_id
"""

import io
import json
import os
import tarfile
import time
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Union

from ..types.agents import (
    AgentBuildRequest,
    AgentBuildResponse,
    AgentBuildStatusResponse,
    AgentBuildStatus,
    AgentDeployRequest,
    AgentDeployResponse,
    AgentEndpoint,
    AgentDestroyResponse,
    AgentCard,
    _parse_build_response,
    _parse_build_status,
    _parse_deploy_response,
    _parse_agent_endpoint,
    _parse_destroy_response,
)

logger = logging.getLogger(__name__)

# Default patterns to exclude when archiving agent project source.
_ARCHIVE_EXCLUDE_PATTERNS = frozenset({
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    "*.egg-info",
    ".DS_Store",
})


class AgentBuildError(Exception):
    """Raised when an agent template build fails."""

    def __init__(
        self,
        build_id: str,
        message: str,
        status: Optional[AgentBuildStatusResponse] = None,
    ):
        self.build_id = build_id
        self.status = status
        super().__init__(f"Agent build {build_id} failed: {message}")


class AgentBuildTimeoutError(AgentBuildError):
    """Raised when an agent template build exceeds the timeout."""

    def __init__(
        self,
        build_id: str,
        timeout_secs: int,
        status: Optional[AgentBuildStatusResponse] = None,
    ):
        self.timeout_secs = timeout_secs
        super().__init__(
            build_id,
            f"Build did not complete within {timeout_secs}s",
            status=status,
        )


def _create_source_archive(source: Union[str, Path]) -> bytes:
    """Create a tar.gz archive from a local directory.

    Args:
        source: Path to the agent project directory.

    Returns:
        Bytes of the tar.gz archive.

    Raises:
        FileNotFoundError: If the source directory does not exist.
        ValueError: If the source is not a directory.
    """
    source_path = Path(source).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source directory not found: {source_path}")
    if not source_path.is_dir():
        raise ValueError(f"Source must be a directory: {source_path}")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for entry in sorted(source_path.rglob("*")):
            rel = entry.relative_to(source_path)
            # Skip excluded patterns
            if any(part in _ARCHIVE_EXCLUDE_PATTERNS for part in rel.parts):
                continue
            if any(entry.name.endswith(p.lstrip("*")) for p in _ARCHIVE_EXCLUDE_PATTERNS if p.startswith("*")):
                continue
            arcname = str(rel)
            tar.add(str(entry), arcname=arcname, recursive=False)

    return buf.getvalue()


class Agents:
    """Agent Deployment resource.

    Provides build-from-source, deploy, invoke, stream, and lifecycle
    management for deployed agents.

    Example:
        >>> from gravixlayer import GravixLayer
        >>> client = GravixLayer(api_key="...")
        >>>
        >>> # Deploy from source (unified build + deploy)
        >>> deployment = client.agents.deploy(
        ...     source="./my_agent/", name="my-agent", framework="langgraph",
        ... )
        >>> print(deployment.endpoint)
        >>>
        >>> # Deploy from pre-built template
        >>> deployment = client.agents.deploy(template_id="uuid-here")
        >>>
        >>> # Standalone build only
        >>> build = client.agents.build("./my_agent/", name="my-agent")
        >>> status = client.agents.wait_for_build(build.build_id)
        >>>
        >>> # Invoke deployed agent
        >>> response = client.agents.invoke(deployment.agent_id, input={"prompt": "Hello"})
    """

    def __init__(self, client):
        self.client = client

    # -- Internal helpers ---------------------------------------------------

    def _make_agents_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Issue a request against the agents API (/v1/agents/...)."""
        return self.client._make_request(
            method, endpoint, data, _service="v1/agents", **kwargs
        )

    # -- Build operations ---------------------------------------------------

    def build(
        self,
        source: Union[str, Path],
        *,
        name: str,
        description: str = "",
        entrypoint: str = "",
        python_version: str = "",
        framework: str = "",
        ports: Optional[list] = None,
        vcpu_count: int = 0,
        memory_mb: int = 0,
        disk_mb: int = 0,
        environment: Optional[Dict[str, str]] = None,
        start_cmd: str = "",
        ready_cmd: str = "",
        ready_timeout_secs: int = 0,
        tags: Optional[Dict[str, str]] = None,
    ) -> AgentBuildResponse:
        """Start an agent template build from local project source.

        Uploads the source directory as a tar.gz archive along with build
        metadata to ``POST /v1/agents/template/build-agent``.

        Args:
            source: Path to the agent project directory.
            name: Name for the template (required).
            description: Optional template description.
            entrypoint: Application entrypoint (e.g. ``"main:app"``).
            python_version: Python version (e.g. ``"3.13"``).
            framework: Agent framework (langgraph, crewai, google-adk, etc.).
            ports: Ports the agent listens on (default ``[8000]``).
            vcpu_count: Number of vCPUs (default determined by backend).
            memory_mb: Memory in MB (default determined by backend).
            disk_mb: Disk size in MB (default determined by backend).
            environment: Environment variables for the agent.
            start_cmd: Custom start command.
            ready_cmd: Readiness check command.
            ready_timeout_secs: Readiness timeout in seconds.
            tags: Metadata tags.

        Returns:
            AgentBuildResponse with build_id for status polling.
        """
        archive_bytes = _create_source_archive(source)

        metadata = AgentBuildRequest(
            name=name,
            description=description,
            entrypoint=entrypoint,
            python_version=python_version,
            framework=framework,
            ports=ports or [],
            vcpu_count=vcpu_count,
            memory_mb=memory_mb,
            disk_mb=disk_mb,
            environment=environment or {},
            start_cmd=start_cmd,
            ready_cmd=ready_cmd,
            ready_timeout_secs=ready_timeout_secs,
            tags=tags or {},
        )

        files = [
            ("archive", ("project.tar.gz", archive_bytes, "application/gzip")),
        ]
        form_data = {"metadata": json.dumps(metadata.to_dict())}

        response = self._make_agents_request(
            "POST",
            "template/build-agent",
            data=form_data,
            files=files,
        )
        return _parse_build_response(response.json())

    def get_build_status(self, build_id: str) -> AgentBuildStatusResponse:
        """Poll the status of a running agent template build.

        Args:
            build_id: The build ID returned by ``build()``.

        Returns:
            AgentBuildStatusResponse with current phase and progress.
        """
        response = self._make_agents_request(
            "GET", f"template/builds/{build_id}/status"
        )
        return _parse_build_status(response.json())

    def wait_for_build(
        self,
        build_id: str,
        *,
        poll_interval_secs: float = 5.0,
        timeout_secs: int = 600,
        on_status: Optional[Any] = None,
    ) -> AgentBuildStatusResponse:
        """Block until an agent template build completes or fails.

        Args:
            build_id: The build ID to monitor.
            poll_interval_secs: Seconds between status polls (default 5).
            timeout_secs: Maximum seconds to wait (default 600).
            on_status: Optional callback invoked on each poll with an
                       AgentBuildStatusResponse.

        Returns:
            Final AgentBuildStatusResponse when build reaches terminal state.

        Raises:
            AgentBuildError: If the build fails.
            AgentBuildTimeoutError: If the build exceeds timeout.
        """
        logger.info("Waiting for agent build: build_id=%s", build_id)

        deadline = time.monotonic() + timeout_secs
        last_phase = ""

        while True:
            if time.monotonic() > deadline:
                try:
                    final = self.get_build_status(build_id)
                except Exception:
                    final = None
                raise AgentBuildTimeoutError(
                    build_id, timeout_secs, status=final
                )

            time.sleep(poll_interval_secs)
            status = self.get_build_status(build_id)

            if on_status is not None:
                on_status(status)

            if status.phase != last_phase:
                last_phase = status.phase
                logger.info(
                    "Build %s: phase=%s progress=%d%%",
                    build_id,
                    status.phase,
                    status.progress_percent,
                )

            if status.is_terminal:
                if status.is_success:
                    logger.info("Build %s completed successfully", build_id)
                    return status

                error_msg = status.error or "Unknown build failure"
                logger.error("Build %s failed: %s", build_id, error_msg)
                raise AgentBuildError(build_id, error_msg, status=status)

    # -- Deploy operations --------------------------------------------------

    def deploy(
        self,
        source: Optional[Union[str, Path]] = None,
        *,
        template_id: Optional[str] = None,
        name: str = "",
        description: str = "",
        entrypoint: str = "",
        python_version: str = "",
        framework: str = "",
        ports: Optional[list] = None,
        vcpu_count: int = 0,
        memory_mb: int = 0,
        disk_mb: int = 0,
        environment: Optional[Dict[str, str]] = None,
        start_cmd: str = "",
        ready_cmd: str = "",
        ready_timeout_secs: int = 0,
        tags: Optional[Dict[str, str]] = None,
        entry_point: str = "",
        http_port: int = 0,
        a2a_port: int = 0,
        mcp_port: int = 0,
        protocols: Optional[list] = None,
        is_public: bool = False,
        deploy_environment: Optional[Dict[str, str]] = None,
        timeout: int = 0,
        agent_card: Optional[AgentCard] = None,
        build_poll_interval_secs: float = 5.0,
        build_timeout_secs: int = 600,
        on_build_status: Optional[Any] = None,
    ) -> AgentDeployResponse:
        """Deploy an agent from source or from a pre-built template.

        **From source** (unified build + deploy):
            Pass ``source`` (path to project directory) and ``name``.
            Builds a template, waits for completion, then deploys.

        **From template**:
            Pass ``template_id`` only. Deploys from an existing template.

        Exactly one of ``source`` or ``template_id`` must be provided.

        Args:
            source: Path to agent project directory (triggers build + deploy).
            template_id: UUID of a pre-built template (deploy only).
            name: Template name (required when ``source`` is provided).
            description: Template description (build only).
            entrypoint: Application entrypoint for build (e.g. ``"main:app"``).
            python_version: Python version for build (e.g. ``"3.13"``).
            framework: Agent framework (langgraph, crewai, google-adk, etc.).
            ports: Ports the agent listens on (build only, default ``[8000]``).
            vcpu_count: Number of vCPUs (build only).
            memory_mb: Memory in MB (build only).
            disk_mb: Disk size in MB (build only).
            environment: Build-time environment variables.
            start_cmd: Custom start command (build only).
            ready_cmd: Readiness check command (build only).
            ready_timeout_secs: Readiness timeout (build only).
            tags: Metadata tags (build only).
            entry_point: Application entrypoint for deploy.
            http_port: HTTP port (default assigned by backend).
            a2a_port: A2A protocol port.
            mcp_port: MCP protocol port.
            protocols: Protocols to enable (default ``["http"]``).
            is_public: Whether the endpoint is publicly accessible.
            deploy_environment: Runtime environment variables for deploy.
            timeout: Agent runtime timeout in seconds.
            agent_card: A2A Agent Card configuration.
            build_poll_interval_secs: Build status poll interval (source only).
            build_timeout_secs: Max time to wait for build (source only).
            on_build_status: Callback for build status updates (source only).

        Returns:
            AgentDeployResponse with agent_id, endpoint URL, and status.

        Raises:
            ValueError: If neither or both of ``source`` and ``template_id``
                are provided, or if ``name`` is missing when ``source`` is set.
            AgentBuildError: If the build fails (source path only).
            AgentBuildTimeoutError: If the build exceeds timeout (source only).
        """
        if source is not None and template_id is not None:
            raise ValueError("Provide either 'source' or 'template_id', not both")
        if source is None and template_id is None:
            raise ValueError("Either 'source' (build + deploy) or 'template_id' (deploy only) is required")

        if source is not None:
            if not name:
                raise ValueError("'name' is required when deploying from source")

            build_response = self.build(
                source,
                name=name,
                description=description,
                entrypoint=entrypoint,
                python_version=python_version,
                framework=framework,
                ports=ports,
                vcpu_count=vcpu_count,
                memory_mb=memory_mb,
                disk_mb=disk_mb,
                environment=environment,
                start_cmd=start_cmd,
                ready_cmd=ready_cmd,
                ready_timeout_secs=ready_timeout_secs,
                tags=tags,
            )

            build_status = self.wait_for_build(
                build_response.build_id,
                poll_interval_secs=build_poll_interval_secs,
                timeout_secs=build_timeout_secs,
                on_status=on_build_status,
            )

            template_id = build_status.template_id
            if not entry_point and entrypoint:
                entry_point = entrypoint

        request = AgentDeployRequest(
            template_id=template_id,
            framework=framework,
            entry_point=entry_point,
            http_port=http_port,
            a2a_port=a2a_port,
            mcp_port=mcp_port,
            protocols=protocols or [],
            is_public=is_public,
            environment=deploy_environment or environment or {},
            timeout=timeout,
            agent_card=agent_card,
        )

        response = self._make_agents_request("POST", "deploy", request.to_dict())
        return _parse_deploy_response(response.json())

    # -- Agent endpoint operations ------------------------------------------

    def get(self, agent_id: str) -> AgentEndpoint:
        """Get agent endpoint information.

        Args:
            agent_id: The agent ID (e.g. ``"ag-abc123..."``).

        Returns:
            AgentEndpoint with health, DNS status, and protocol URLs.
        """
        response = self._make_agents_request("GET", f"{agent_id}/endpoint")
        return _parse_agent_endpoint(response.json())

    def destroy(self, agent_id: str) -> AgentDestroyResponse:
        """Destroy a deployed agent.

        Terminates the runtime, removes DNS records, and deletes the
        agent endpoint.

        Args:
            agent_id: The agent ID to destroy.

        Returns:
            AgentDestroyResponse confirming destruction.
        """
        response = self._make_agents_request("DELETE", agent_id)
        return _parse_destroy_response(response.json())

    # -- Invocation operations ----------------------------------------------

    def invoke(
        self,
        agent_id: str,
        *,
        input: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Invoke a deployed agent synchronously.

        Sends a request to the agent's public HTTPS endpoint.

        Args:
            agent_id: The agent ID to invoke.
            input: Input payload for the agent.
            session_id: Optional session/thread ID for stateful conversations.
            metadata: Optional metadata to pass to the agent.

        Returns:
            Agent response as a dictionary.
        """
        endpoint_info = self.get(agent_id)
        agent_url = endpoint_info.endpoint.rstrip("/")

        payload: Dict[str, Any] = {}
        if input is not None:
            payload["input"] = input
        if session_id is not None:
            payload["session_id"] = session_id
        if metadata is not None:
            payload["metadata"] = metadata

        response = self.client._make_request(
            "POST",
            f"{agent_url}/invoke",
            payload,
            _service="",
        )
        return response.json()

    def stream(
        self,
        agent_id: str,
        *,
        input: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Invoke a deployed agent with streaming response.

        Returns an iterator of server-sent events from the agent.

        Args:
            agent_id: The agent ID to invoke.
            input: Input payload for the agent.
            session_id: Optional session/thread ID.
            metadata: Optional metadata.

        Yields:
            Parsed SSE event dictionaries from the agent.
        """
        endpoint_info = self.get(agent_id)
        agent_url = endpoint_info.endpoint.rstrip("/")

        payload: Dict[str, Any] = {}
        if input is not None:
            payload["input"] = input
        if session_id is not None:
            payload["session_id"] = session_id
        if metadata is not None:
            payload["metadata"] = metadata

        response = self.client._make_request(
            "POST",
            f"{agent_url}/stream",
            payload,
            _service="",
            stream=True,
        )

        try:
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        yield {"raw": data}
        finally:
            response.close()
