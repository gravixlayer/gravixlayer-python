"""
Runtime API resource for synchronous client
"""

import os
from typing import List, Dict, Any, Optional

from .._resource_utils import (
    build_list_endpoint,
    normalize_runtime_api_payload,
    parse_paginated_items,
    parse_total_items,
)
from ..types.runtime import (
    Runtime,
    RuntimeList,
    RuntimeMetrics,
    RuntimeTimeoutResponse,
    RuntimeHostURL,
    SSHInfo,
    SSHStatus,
    CommandRunResponse,
    CodeRunResponse,
    CodeContext,
    CodeContextDeleteResponse,
    Template,
    TemplateList,
    RuntimeKillResponse,
    _validate_runtime_id,
    _METRICS_FIELDS,
    _RUNTIME_DEFAULTS,
)

from .runtime_git import RuntimeGitResource
from .runtime_files import RuntimeFileResource


class Runtimes:
    """Runtimes resource for synchronous client"""

    def __init__(self, client):
        self.client = client
        self._git_resource: Optional["RuntimeGitResource"] = None
        self._file_resource: Optional[RuntimeFileResource] = None

    @property
    def file(self) -> RuntimeFileResource:
        """Filesystem operations: ``read``, ``write``, ``delete``, ``list``, ``upload``, ``write_many``, …"""
        if self._file_resource is None:
            self._file_resource = RuntimeFileResource(self)
        return self._file_resource

    @property
    def git(self) -> "RuntimeGitResource":
        """Git operations: ``client.runtime.git.clone(...)``, ``.pull``, etc."""
        if self._git_resource is None:
            self._git_resource = RuntimeGitResource(self)
        return self._git_resource

    def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)"""
        return self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    @staticmethod
    def _apply_defaults(data: Dict[str, Any], template: Optional[str] = None) -> Dict[str, Any]:
        """Fill in missing runtime fields with safe defaults."""
        normalize_runtime_api_payload(data)
        for key, default in _RUNTIME_DEFAULTS.items():
            if key not in data or data[key] is None:
                data[key] = default
        if template and not data.get("template"):
            data["template"] = template
        return data

    # Runtime Lifecycle Methods

    def create(
        self,
        provider: Optional[str] = None,
        region: Optional[str] = None,
        template: Optional[str] = "python-3.14-base-small",
        timeout: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        internet_access: Optional[bool] = None,
        agent_id: Optional[str] = None,
    ) -> Runtime:
        """Create a new runtime instance.

        Args:
            provider: Cloud provider (falls back to client.cloud if not set)
            region: Cloud region (falls back to client.region if not set)
            template: Template name or ID to use
            timeout: Runtime timeout in seconds (default: None = no timeout)
            env_vars: Environment variables for the runtime. Pass ``{}`` to set an
                explicit empty map (distinct from omitting the field).
            metadata: Metadata tags for the runtime
            internet_access: Whether to allow internet access (default: None = server default)
            agent_id: Agent ID to associate with the runtime
        """
        resolved_provider = provider or self.client.cloud
        resolved_region = region or self.client.region
        if not resolved_provider:
            raise ValueError(
                "provider is required. Pass it to create() or set cloud on GravixLayer client."
            )
        if not resolved_region:
            raise ValueError(
                "region is required. Pass it to create() or set region on GravixLayer client."
            )

        data: Dict[str, Any] = {
            "provider": resolved_provider,
            "region": resolved_region,
            "template": template,
        }
        if timeout is not None:
            data["timeout"] = timeout
        if env_vars is not None:
            data["env_vars"] = env_vars
        if metadata is not None:
            data["metadata"] = metadata
        if internet_access is not None:
            data["internet_access"] = internet_access
        if agent_id is not None:
            data["agent_id"] = agent_id

        response = self._make_agents_request("POST", "runtime", data)
        result = self._apply_defaults(response.json(), template=template)
        rt = Runtime.from_api(result)
        rt._client = self.client
        return rt

    def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> RuntimeList:
        """List all runtimes"""
        endpoint = build_list_endpoint("runtime", limit=limit, offset=offset)
        response = self._make_agents_request("GET", endpoint)
        result = response.json()

        runtimes_list, total = parse_total_items(
            result,
            "runtimes",
            lambda s: Runtime.from_api(self._apply_defaults(s)),
        )
        for runtime_obj in runtimes_list:
            runtime_obj._client = self.client
        return RuntimeList(runtimes=runtimes_list, total=total)

    def get(self, runtime_id: str) -> Runtime:
        """Get detailed information about a specific runtime."""
        _validate_runtime_id(runtime_id)
        response = self._make_agents_request("GET", f"runtime/{runtime_id}")
        result = self._apply_defaults(response.json())
        rt = Runtime.from_api(result)
        rt._client = self.client
        return rt

    def kill(self, runtime_id: str) -> RuntimeKillResponse:
        """Terminate a running runtime immediately."""
        _validate_runtime_id(runtime_id)
        response = self._make_agents_request("DELETE", f"runtime/{runtime_id}")
        result = dict(response.json())
        body_rid = result.pop("runtime_id", None)
        return RuntimeKillResponse(runtime_id=body_rid or runtime_id, **result)

    def connect(self, runtime_id: str) -> Dict[str, Any]:
        """Connect to an existing runtime.

        Args:
            runtime_id: Target runtime ID.

        Returns:
            Dict with runtime_id, status, domain, and message.
        """
        _validate_runtime_id(runtime_id)
        response = self._make_agents_request("POST", f"runtime/{runtime_id}/connect")
        return response.json()

    # Runtime Configuration Methods

    def set_timeout(self, runtime_id: str, timeout: int) -> RuntimeTimeoutResponse:
        """Update the timeout for a running runtime."""
        _validate_runtime_id(runtime_id)
        data = {"timeout": timeout}
        response = self._make_agents_request("POST", f"runtime/{runtime_id}/timeout", data)
        result = response.json()
        return RuntimeTimeoutResponse(**result)

    def get_metrics(self, runtime_id: str) -> RuntimeMetrics:
        """Get current resource usage metrics for a runtime."""
        _validate_runtime_id(runtime_id)
        response = self._make_agents_request("GET", f"runtime/{runtime_id}/metrics")
        result = response.json()
        filtered = {k: v for k, v in result.items() if k in _METRICS_FIELDS}
        return RuntimeMetrics(**filtered)

    def get_host_url(self, runtime_id: str, port: int) -> RuntimeHostURL:
        """Get the public URL for accessing a specific port on the runtime."""
        _validate_runtime_id(runtime_id)
        response = self._make_agents_request("GET", f"runtime/{runtime_id}/host/{port}")
        result = response.json()
        return RuntimeHostURL(**result)

    # Command Execution Methods

    def run_cmd(
        self,
        runtime_id: str,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> CommandRunResponse:
        """Execute a shell command in the runtime.

        Returns a :class:`~gravixlayer.types.runtime.CommandRunResponse`. The
        :meth:`Runtime.run_cmd` helper wraps this in :class:`~gravixlayer.types.runtime.Execution`.

        Args:
            runtime_id: Target runtime ID.
            command: The command string to execute.
            args: Additional arguments.
            working_dir: Working directory.
            environment: Environment variables.
            timeout: Maximum execution time in **seconds** (converted to ms for the backend).
        """
        _validate_runtime_id(runtime_id)
        data: Dict[str, Any] = {"command": command}
        if args is not None:
            data["args"] = args
        if working_dir is not None:
            data["working_dir"] = working_dir
        if environment is not None:
            data["environment"] = environment
        if timeout is not None:
            # Backend expects milliseconds; SDK interface uses seconds
            data["timeout"] = timeout * 1000

        response = self._make_agents_request("POST", f"runtime/{runtime_id}/commands/run", data)
        result = response.json()
        return CommandRunResponse(**result)

    # Code Execution Methods

    def run_code(
        self,
        runtime_id: str,
        code: str,
        language: Optional[str] = "python",
        context_id: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> CodeRunResponse:
        """Execute code in the runtime using Jupyter kernel.

        Returns a :class:`~gravixlayer.types.runtime.CodeRunResponse` (not
        :class:`~gravixlayer.types.runtime.Execution`). Use
        ``Execution(client.runtime.run_code(...))`` if you want the unified
        wrapper used by :meth:`Runtime.run_code`.

        Args:
            runtime_id: Target runtime ID.
            code: Code to execute.
            language: Language (default: "python").
            context_id: Execution context ID for state persistence.
            environment: Environment variables.
            timeout: Maximum execution time in **seconds** (backend expects seconds for code execution).
        """
        _validate_runtime_id(runtime_id)
        data: Dict[str, Any] = {"code": code}
        if language is not None:
            data["language"] = language
        if context_id is not None:
            data["context_id"] = context_id
        if environment is not None:
            data["environment"] = environment
        if timeout is not None:
            data["timeout"] = timeout

        response = self._make_agents_request("POST", f"runtime/{runtime_id}/code/run", data)
        return CodeRunResponse.from_api(response.json())

    def create_context(
        self, runtime_id: str, language: Optional[str] = "python", cwd: Optional[str] = None
    ) -> CodeContext:
        """Create an isolated execution context (Jupyter kernel session) for persistent state."""
        _validate_runtime_id(runtime_id)
        data = {}
        if language:
            data["language"] = language
        if cwd:
            data["cwd"] = cwd

        response = self._make_agents_request("POST", f"runtime/{runtime_id}/code/contexts", data)
        result = response.json()

        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", language or "python"),
            "cwd": result.get("cwd") or cwd or "/workspace",
        }

        return CodeContext(**mapped_result)

    def get_context(self, runtime_id: str, context_id: str) -> CodeContext:
        """Get metadata for an execution context."""
        _validate_runtime_id(runtime_id)
        response = self._make_agents_request("GET", f"runtime/{runtime_id}/code/contexts/{context_id}")
        result = response.json()

        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", "python"),
            "cwd": result.get("cwd") or "/workspace",
        }

        return CodeContext(**mapped_result)

    def delete_context(self, runtime_id: str, context_id: str) -> CodeContextDeleteResponse:
        """Delete an execution context and release its kernel session."""
        _validate_runtime_id(runtime_id)
        response = self._make_agents_request("DELETE", f"runtime/{runtime_id}/code/contexts/{context_id}")
        result = response.json()
        return CodeContextDeleteResponse(**result)

    # SSH Methods

    def enable_ssh(self, runtime_id: str, regenerate_keys: bool = False) -> SSHInfo:
        """Enable SSH access on a runtime.

        Args:
            runtime_id: Target runtime ID.
            regenerate_keys: If True, regenerate SSH keys even if already enabled.

        Returns:
            SSHInfo with connection details.
        """
        _validate_runtime_id(runtime_id)
        endpoint = f"runtime/{runtime_id}/ssh/enable"
        if regenerate_keys:
            endpoint += "?regenerate_keys=true"
        response = self._make_agents_request("POST", endpoint)
        result = response.json()
        return SSHInfo(
            runtime_id=result.get("runtime_id", runtime_id),
            enabled=result.get("enabled", True),
            port=result.get("port", 0),
            username=result.get("username", ""),
            connect_cmd=result.get("connect_cmd", ""),
            private_key=result.get("private_key"),
            public_key=result.get("public_key"),
            ssh_config=result.get("ssh_config"),
            message=result.get("message"),
        )

    def disable_ssh(self, runtime_id: str) -> None:
        """Disable SSH access on a runtime."""
        _validate_runtime_id(runtime_id)
        self._make_agents_request("POST", f"runtime/{runtime_id}/ssh/disable")

    def ssh_status(self, runtime_id: str) -> SSHStatus:
        """Get current SSH status for a runtime."""
        _validate_runtime_id(runtime_id)
        response = self._make_agents_request("GET", f"runtime/{runtime_id}/ssh/status")
        result = response.json()
        return SSHStatus(
            runtime_id=result.get("runtime_id", runtime_id),
            enabled=result.get("enabled", False),
            port=result.get("port", 0),
            username=result.get("username", ""),
            daemon_running=result.get("daemon_running", False),
        )

    # State Management Methods

    def pause(self, runtime_id: str) -> None:
        """Pause a running runtime."""
        _validate_runtime_id(runtime_id)
        self._make_agents_request("POST", f"runtime/{runtime_id}/pause")

    def resume(self, runtime_id: str) -> None:
        """Resume a paused runtime."""
        _validate_runtime_id(runtime_id)
        self._make_agents_request("POST", f"runtime/{runtime_id}/resume")


class RuntimeTemplates:
    """Runtime Templates resource for synchronous client"""

    def __init__(self, client):
        self.client = client

    def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)"""
        return self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> TemplateList:
        """List available runtime templates"""
        endpoint = build_list_endpoint("template", limit=limit, offset=offset)
        response = self._make_agents_request("GET", endpoint)
        result = response.json()

        default_limit = 100 if limit is None else limit
        default_offset = 0 if offset is None else offset
        templates, page_limit, page_offset = parse_paginated_items(
            result,
            "templates",
            lambda template: Template(**template),
            default_limit=default_limit,
            default_offset=default_offset,
        )
        return TemplateList(templates=templates, limit=page_limit, offset=page_offset)


class RuntimeResource:
    """Main Runtime resource — the public API surface at ``client.runtime``.

    All runtime operations are available directly::

        client.runtime.create(template="python-3.14-base-small")
        client.runtime.run_code(runtime_id, "print('hi')")
        client.runtime.kill(runtime_id)
        client.runtime.file.write(runtime_id, path, content)

    Template listing is available via ``client.runtime.templates.list()``.
    """

    def __init__(self, client):
        self.client = client
        self._runtimes = Runtimes(client)
        self.templates = RuntimeTemplates(client)

    @property
    def file(self) -> RuntimeFileResource:
        """Nested filesystem API: ``client.runtime.file.read``, ``.write``, ``.delete``, …"""
        return self._runtimes.file

    @property
    def git(self) -> "RuntimeGitResource":
        """Git operations inside the runtime: ``client.runtime.git.clone``, …"""
        return self._runtimes.git

    def __getattr__(self, name: str):
        """Delegate any attribute not on this class to the underlying Runtimes instance."""
        attr = getattr(self._runtimes, name)
        self.__dict__[name] = attr
        return attr
