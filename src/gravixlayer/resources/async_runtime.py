"""
Runtime API resource for asynchronous client.
"""

import inspect
import json
from typing import List, Dict, Any, Optional

import httpx

from .. import telemetry
from .._resource_utils import (
    aiter_sse_payloads,
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
    SSHInfo,
    SSHStatus,
    CommandRunResponse,
    CodeRunResponse,
    CodeContext,
    CodeContextDeleteResponse,
    ExecutionError,
    ExecutionLogs,
    ExecutionResult,
    Template,
    TemplateList,
    RuntimeKillResponse,
    _validate_runtime_id,
    _validate_path,
    _METRICS_FIELDS,
    _RUNTIME_DEFAULTS,
)

from .runtime_git import AsyncRuntimeGitResource
from .runtime_files import AsyncRuntimeFileResource
from .runtime_pty import AsyncRuntimePtyResource
from .async_runtime_service import AsyncRuntimeServiceResource

# Timeout for restoring a runtime from a snapshot (3 minutes).
_SNAPSHOT_RESTORE_TIMEOUT = httpx.Timeout(180.0)


class AsyncRuntimes:
    """Runtimes resource for asynchronous client."""

    def __init__(self, client):
        self.client = client
        self._git_resource: Optional["AsyncRuntimeGitResource"] = None
        self._file_resource: Optional[AsyncRuntimeFileResource] = None
        self._pty_resource: Optional[AsyncRuntimePtyResource] = None
        self._service_resource: Optional[AsyncRuntimeServiceResource] = None

    @property
    def file(self) -> AsyncRuntimeFileResource:
        """Filesystem operations: ``read``, ``write``, ``delete``, ``list``, ``upload``, ``write_many``, …"""
        if self._file_resource is None:
            self._file_resource = AsyncRuntimeFileResource(self)
        return self._file_resource

    @property
    def pty(self) -> AsyncRuntimePtyResource:
        """Programmatic PTY sessions: ``create``, ``send_input``, ``stream``, ``kill``, …"""
        if self._pty_resource is None:
            self._pty_resource = AsyncRuntimePtyResource(self)
        return self._pty_resource

    @property
    def git(self) -> "AsyncRuntimeGitResource":
        """Git operations: ``await client.runtime.git.clone(...)``, etc."""
        if self._git_resource is None:
            self._git_resource = AsyncRuntimeGitResource(self)
        return self._git_resource

    @property
    def service(self) -> AsyncRuntimeServiceResource:
        """Web services on ``*.service.gravixlayer.ai``."""
        if self._service_resource is None:
            self._service_resource = AsyncRuntimeServiceResource(self)
        return self._service_resource

    async def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)."""
        return await self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    @staticmethod
    def _apply_defaults(data: Dict[str, Any], template: Optional[str] = None) -> Dict[str, Any]:
        """Fill in missing runtime fields with safe defaults."""
        normalize_runtime_api_payload(data)
        for key, default in _RUNTIME_DEFAULTS.items():
            if data.get(key) is None:
                data[key] = default
        if template and not data.get("template"):
            data["template"] = template
        return data

    # Runtime Lifecycle Methods

    async def create(
        self,
        cloud: Optional[str] = None,
        region: Optional[str] = None,
        template: Optional[str] = "base-small",
        timeout: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        internet_access: Optional[bool] = None,
        agent_id: Optional[str] = None,
        providers: Optional[List[str]] = None,
        network_policy_ids: Optional[List[str]] = None,
        provider: Optional[str] = None,
        snapshot: Optional[str] = None,
    ) -> Runtime:
        """Create a new runtime instance.

        Args:
            cloud: Cloud (aws/azure/gcp; falls back to client.cloud if not set)
            region: Cloud region (falls back to client.region if not set)
            template: Template name or ID to use. Ignored when ``snapshot`` is set
                unless a non-default template is also passed (then ValueError).
            timeout: Runtime timeout in seconds
            env_vars: Environment variables for the runtime
            metadata: Metadata tags for the runtime
            internet_access: Whether to allow internet access
            agent_id: Agent ID to associate with the runtime
            providers: Optional secret provider IDs to attach at creation
            network_policy_ids: Optional network policy IDs to attach at creation
                (the system default is always attached).
            provider: Deprecated alias for ``cloud``.
            snapshot: Snapshot name or UUID. Mutually exclusive with an explicit
                ``template`` other than the default ``base-small``.
        """
        if provider is not None and cloud is None:
            cloud = provider
        resolved_cloud = cloud or self.client.cloud
        resolved_region = region or self.client.region
        if not resolved_cloud:
            raise ValueError(
                "cloud is required. Pass it to create() or set cloud on AsyncGravixLayer client."
            )
        if not resolved_region:
            raise ValueError(
                "region is required. Pass it to create() or set region on AsyncGravixLayer client."
            )
        if snapshot and template not in (None, "base-small"):
            raise ValueError("template and snapshot are mutually exclusive")

        data: Dict[str, Any] = {
            "cloud": resolved_cloud,
            "region": resolved_region,
        }
        if snapshot:
            data["snapshot"] = snapshot
        else:
            data["template"] = template or "base-small"
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
        if providers is not None:
            data["providers"] = providers
        if network_policy_ids is not None:
            data["network_policy_ids"] = network_policy_ids

        with telemetry.runtime_span("create", "") as span:
            if snapshot:
                response = await self._make_agents_request(
                    "POST", "runtime", data, timeout=_SNAPSHOT_RESTORE_TIMEOUT
                )
            else:
                response = await self._make_agents_request("POST", "runtime", data)
            result = self._apply_defaults(response.json(), template=template)
            rt = Runtime.from_api(result)
            rt._client = self.client
            if span is not None:
                rid = getattr(rt, "runtime_id", None) or ""
                if rid:
                    span.set_attribute(telemetry.ATTR_RUNTIME_ID, rid)
                telemetry.record_outputs(
                    span,
                    {
                        "runtime_id": rid,
                        "status": getattr(rt, "status", None),
                        "template": getattr(rt, "template", template),
                    },
                )
            return rt

    async def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> RuntimeList:
        """List all runtimes."""
        endpoint = build_list_endpoint("runtime", limit=limit, offset=offset)
        response = await self._make_agents_request("GET", endpoint)
        result = response.json()

        runtimes_list, total = parse_total_items(
            result,
            "runtimes",
            lambda s: Runtime.from_api(self._apply_defaults(s)),
        )
        for runtime_obj in runtimes_list:
            runtime_obj._client = self.client
        return RuntimeList(runtimes=runtimes_list, total=total)

    async def get(self, runtime_id: str) -> Runtime:
        """Get detailed information about a specific runtime."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("GET", f"runtime/{runtime_id}")
        result = self._apply_defaults(response.json())
        rt = Runtime.from_api(result)
        rt._client = self.client
        return rt

    async def kill(self, runtime_id: str) -> RuntimeKillResponse:
        """Terminate a running runtime immediately."""
        _validate_runtime_id(runtime_id)
        with telemetry.runtime_span("kill", runtime_id) as span:
            response = await self._make_agents_request("DELETE", f"runtime/{runtime_id}")
            result = response.json()
            body_rid = result.get("runtime_id")
            message = result.get("message")
            killed = RuntimeKillResponse(
                message="" if message is None else str(message),
                runtime_id=runtime_id if body_rid is None else body_rid,
            )
            if span is not None:
                telemetry.record_outputs(
                    span,
                    {
                        "runtime_id": getattr(killed, "runtime_id", None) or runtime_id,
                        "message": getattr(killed, "message", None),
                    },
                )
            return killed

    async def connect(self, runtime_id: str) -> Dict[str, Any]:
        """Connect to an existing runtime.

        Args:
            runtime_id: Target runtime ID.

        Returns:
            Dict with runtime_id, status, domain, and message.
        """
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("POST", f"runtime/{runtime_id}/connect")
        return response.json()

    # Runtime Configuration Methods

    async def set_timeout(self, runtime_id: str, timeout: int) -> RuntimeTimeoutResponse:
        """Update the timeout for a running runtime."""
        _validate_runtime_id(runtime_id)
        data = {"timeout": timeout}
        response = await self._make_agents_request("POST", f"runtime/{runtime_id}/timeout", data)
        result = response.json()
        return RuntimeTimeoutResponse(**result)

    async def get_metrics(self, runtime_id: str) -> RuntimeMetrics:
        """Get current resource usage metrics for a runtime."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("GET", f"runtime/{runtime_id}/metrics")
        result = response.json()
        return RuntimeMetrics(**{k: result[k] for k in _METRICS_FIELDS if k in result})

    # Command Execution Methods

    async def run_cmd(
        self,
        runtime_id: str,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> CommandRunResponse:
        """Execute a shell command in the runtime.

        Args:
            runtime_id: Target runtime ID.
            command: The command string to execute.
            args: Additional arguments.
            working_dir: Working directory.
            environment: Environment variables.
            timeout: Maximum execution time in **seconds** (converted to ms for the API).
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
            data["timeout"] = timeout * 1000

        with telemetry.runtime_span("command.run", runtime_id) as span:
            response = await self._make_agents_request("POST", f"runtime/{runtime_id}/commands/run", data)
            result = CommandRunResponse.from_api(response.json())
            if span is not None:
                span.set_attribute("process.exit_code", int(getattr(result, "exit_code", 0) or 0))
                telemetry.record_outputs(
                    span,
                    {
                        "exit_code": getattr(result, "exit_code", None),
                        "success": getattr(result, "success", True),
                        "stdout_preview": (getattr(result, "stdout", "") or "")[:500],
                        "stderr_preview": (getattr(result, "stderr", "") or "")[:500],
                    },
                )
                if not getattr(result, "success", True):
                    telemetry.mark_span_error(span, f"exit_code={result.exit_code}")
            return result

    # Code Execution Methods

    async def run_code(
        self,
        runtime_id: str,
        code: str,
        language: Optional[str] = "python",
        context_id: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        on_stdout: Optional[Any] = None,
        on_stderr: Optional[Any] = None,
        on_result: Optional[Any] = None,
        on_error: Optional[Any] = None,
    ) -> CodeRunResponse:
        """Execute code in the runtime using Jupyter kernel.

        Passing any of the ``on_*`` callbacks switches to streaming mode, where output
        is delivered incrementally as the code runs instead of only at completion. The
        callbacks may be plain functions or coroutine functions. The return value has
        the same shape in both modes.

        Args:
            runtime_id: Target runtime ID.
            code: Code to execute.
            language: Language (default: "python").
            context_id: Execution context ID for state persistence.
            environment: Environment variables.
            timeout: Maximum execution time in **seconds** (API expects seconds for code execution).
            on_stdout: Optional callable invoked with each incremental stdout chunk (``str``).
            on_stderr: Optional callable invoked with each incremental stderr chunk (``str``).
            on_result: Optional callable invoked with each ``ExecutionResult``.
            on_error: Optional callable invoked with the ``ExecutionError`` on failure.
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

        streaming = (
            on_stdout is not None
            or on_stderr is not None
            or on_result is not None
            or on_error is not None
        )
        with telemetry.runtime_span("code.run", runtime_id) as span:
            if streaming:
                result = await self._run_code_streaming(
                    runtime_id, data, on_stdout, on_stderr, on_result, on_error,
                )
            else:
                response = await self._make_agents_request("POST", f"runtime/{runtime_id}/code/run", data)
                result = CodeRunResponse.from_api(response.json())
            if span is not None:
                text = getattr(result, "text", None) or getattr(result, "stdout", "") or ""
                telemetry.record_outputs(
                    span,
                    {
                        "text_preview": (text[:500] + "...") if len(text) > 500 else text,
                        "error": getattr(result, "error", None),
                    },
                )
                if getattr(result, "error", None):
                    telemetry.mark_span_error(span, str(result.error))
            return result

    async def _run_code_streaming(
        self,
        runtime_id: str,
        data: Dict[str, Any],
        on_stdout: Optional[Any],
        on_stderr: Optional[Any],
        on_result: Optional[Any],
        on_error: Optional[Any],
    ) -> CodeRunResponse:
        """Stream a run_code response as Server-Sent Events.

        Accumulates the same fields the unary endpoint returns while invoking the
        caller's callbacks for each incremental event.
        """
        async def dispatch(callback: Optional[Any], value: Any) -> None:
            if callback is None:
                return
            maybe = callback(value)
            if inspect.isawaitable(maybe):
                await maybe

        endpoint = f"runtime/{runtime_id}/code/run?stream=true"
        response = await self._make_agents_request("POST", endpoint, data, stream=True)

        logs = ExecutionLogs()
        results: List[ExecutionResult] = []
        error: Optional[ExecutionError] = None

        try:
            async for payload in aiter_sse_payloads(response.aiter_lines()):
                try:
                    evt = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                evt_type = evt.get("type")
                if evt_type == "stdout":
                    chunk = evt.get("text", "")
                    logs.stdout.append(chunk)
                    await dispatch(on_stdout, chunk)
                elif evt_type == "stderr":
                    chunk = evt.get("text", "")
                    logs.stderr.append(chunk)
                    await dispatch(on_stderr, chunk)
                elif evt_type == "result":
                    raw = evt.get("result") or {}
                    item = ExecutionResult(
                        text=raw.get("text", ""),
                        html=raw.get("html", ""),
                        json=raw.get("json"),
                        png=raw.get("png", ""),
                        jpeg=raw.get("jpeg", ""),
                        svg=raw.get("svg", ""),
                        markdown=raw.get("markdown", ""),
                        chart=raw.get("chart"),
                    )
                    results.append(item)
                    await dispatch(on_result, item)
                elif evt_type == "error":
                    raw = evt.get("error") or {}
                    if isinstance(raw, dict):
                        error = ExecutionError(
                            name=raw.get("name", ""),
                            value=raw.get("value", ""),
                            traceback=raw.get("traceback", ""),
                        )
                    else:
                        error = ExecutionError(value=str(evt.get("message") or raw))
                    await dispatch(on_error, error)
                elif evt_type == "end":
                    break
        finally:
            await response.aclose()

        return CodeRunResponse(results=results, logs=logs, error=error)

    async def create_context(
        self, runtime_id: str, language: Optional[str] = "python", cwd: Optional[str] = None
    ) -> CodeContext:
        """Create an isolated execution context (Jupyter kernel session) for persistent state."""
        _validate_runtime_id(runtime_id)
        data: Dict[str, Any] = {}
        if language:
            data["language"] = language
        if cwd:
            data["cwd"] = cwd

        response = await self._make_agents_request("POST", f"runtime/{runtime_id}/code/contexts", data)
        result = response.json()

        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", language or "python"),
            "cwd": result.get("cwd") or cwd or "/workspace",
        }

        return CodeContext(**mapped_result)

    async def get_context(self, runtime_id: str, context_id: str) -> CodeContext:
        """Get metadata for an execution context."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("GET", f"runtime/{runtime_id}/code/contexts/{context_id}")
        result = response.json()

        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", "python"),
            "cwd": result.get("cwd") or "/workspace",
        }

        return CodeContext(**mapped_result)

    async def delete_context(self, runtime_id: str, context_id: str) -> CodeContextDeleteResponse:
        """Delete an execution context and release its kernel session."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("DELETE", f"runtime/{runtime_id}/code/contexts/{context_id}")
        result = response.json()
        return CodeContextDeleteResponse(**result)

    # SSH Methods

    async def enable_ssh(self, runtime_id: str, regenerate_keys: bool = False) -> SSHInfo:
        """Enable SSH access on a runtime."""
        _validate_runtime_id(runtime_id)
        endpoint = f"runtime/{runtime_id}/ssh/enable"
        if regenerate_keys:
            endpoint += "?regenerate_keys=true"
        response = await self._make_agents_request("POST", endpoint)
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

    async def disable_ssh(self, runtime_id: str) -> None:
        """Disable SSH access on a runtime."""
        _validate_runtime_id(runtime_id)
        await self._make_agents_request("POST", f"runtime/{runtime_id}/ssh/disable")

    async def ssh_status(self, runtime_id: str) -> SSHStatus:
        """Get current SSH status for a runtime."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("GET", f"runtime/{runtime_id}/ssh/status")
        result = response.json()
        return SSHStatus(
            runtime_id=result.get("runtime_id", runtime_id),
            enabled=result.get("enabled", False),
            port=result.get("port", 0),
            username=result.get("username", ""),
            daemon_running=result.get("daemon_running", False),
        )

    # State Management Methods

    async def pause(self, runtime_id: str) -> None:
        """Pause a running runtime."""
        _validate_runtime_id(runtime_id)
        await self._make_agents_request("POST", f"runtime/{runtime_id}/pause")

    async def resume(self, runtime_id: str) -> None:
        """Resume a paused runtime."""
        _validate_runtime_id(runtime_id)
        await self._make_agents_request("POST", f"runtime/{runtime_id}/resume")


class AsyncRuntimeTemplates:
    """Runtime Templates resource for asynchronous client"""

    def __init__(self, client):
        self.client = client

    async def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)"""
        return await self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    async def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> TemplateList:
        """List available sandbox/runtime templates (excludes agent templates)."""
        endpoint = build_list_endpoint(
            "template",
            limit=limit,
            offset=offset,
            extra_params={"kind": "sandbox"},
        )

        response = await self._make_agents_request("GET", endpoint)
        result = response.json()

        default_limit = 100 if limit is None else limit
        default_offset = 0 if offset is None else offset
        templates, page_limit, page_offset = parse_paginated_items(
            result,
            "templates",
            lambda template: Template.from_api(template),
            default_limit=default_limit,
            default_offset=default_offset,
        )
        return TemplateList(templates=templates, limit=page_limit, offset=page_offset)


class AsyncRuntimeResource:
    """Main Runtime resource — the public API surface at ``client.runtime``.

    All runtime operations are available directly::

        await client.runtime.create()  # defaults to template="base-small"
        await client.runtime.run_code(runtime_id, "print('hi')")
        await client.runtime.kill(runtime_id)
        await client.runtime.file.write(runtime_id, path, content)

    Template listing is available via ``await client.runtime.templates.list()``.
    """

    def __init__(self, client):
        self.client = client
        self._runtimes = AsyncRuntimes(client)
        self.templates = AsyncRuntimeTemplates(client)

    @property
    def file(self) -> AsyncRuntimeFileResource:
        """Nested filesystem API: ``await client.runtime.file.read``, …"""
        return self._runtimes.file

    @property
    def git(self) -> "AsyncRuntimeGitResource":
        """Git operations inside the runtime."""
        return self._runtimes.git

    @property
    def service(self) -> AsyncRuntimeServiceResource:
        """Web services on ``*.service.gravixlayer.ai``."""
        return self._runtimes.service

    def __getattr__(self, name: str):
        """Delegate any attribute not on this class to the underlying AsyncRuntimes instance."""
        attr = getattr(self._runtimes, name)
        self.__dict__[name] = attr
        return attr
