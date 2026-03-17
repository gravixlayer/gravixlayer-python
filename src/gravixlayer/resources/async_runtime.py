"""
Runtime API resource for asynchronous client.
"""

import dataclasses
import os
from typing import List, Dict, Any, Optional, BinaryIO, Union
from urllib.parse import urlencode

from ..types.runtime import (
    Runtime,
    RuntimeList,
    RuntimeMetrics,
    RuntimeTimeoutResponse,
    RuntimeHostURL,
    SSHInfo,
    SSHStatus,
    FileReadResponse,
    FileWriteResponse,
    FileListResponse,
    FileInfo,
    FileDeleteResponse,
    DirectoryCreateResponse,
    FileUploadResponse,
    WriteEntry,
    WriteResult,
    WriteFilesResponse,
    CommandRunResponse,
    CodeRunResponse,
    CodeContext,
    CodeContextDeleteResponse,
    Template,
    TemplateList,
    RuntimeKillResponse,
    _validate_runtime_id,
    _validate_path,
)

# Field names known to the RuntimeMetrics dataclass — cached once at import time
_METRICS_FIELDS: frozenset = frozenset(f.name for f in dataclasses.fields(RuntimeMetrics))

# Default values for runtime response fields the API may omit
_RUNTIME_DEFAULTS: Dict[str, Any] = {
    "metadata": {},
    "template": None,
    "template_id": None,
    "started_at": None,
    "timeout_at": None,
    "cpu_count": None,
    "memory_mb": None,
    "ended_at": None,
}


class AsyncRuntimes:
    """Runtimes resource for asynchronous client."""

    def __init__(self, client):
        self.client = client

    async def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)."""
        return await self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    @staticmethod
    def _apply_defaults(data: Dict[str, Any], template: Optional[str] = None) -> Dict[str, Any]:
        """Fill in missing runtime fields with safe defaults."""
        for key, default in _RUNTIME_DEFAULTS.items():
            if key not in data or data[key] is None:
                data[key] = default
        if template and not data.get("template"):
            data["template"] = template
        return data

    # Runtime Lifecycle Methods

    async def create(
        self,
        provider: Optional[str] = None,
        region: Optional[str] = None,
        template: Optional[str] = "python-base-v1",
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
            timeout: Runtime timeout in seconds
            env_vars: Environment variables for the runtime
            metadata: Metadata tags for the runtime
            internet_access: Whether to allow internet access
            agent_id: Agent ID to associate with the runtime
        """
        resolved_provider = provider or getattr(self.client, "cloud", None)
        resolved_region = region or getattr(self.client, "region", None)
        if not resolved_provider:
            raise ValueError(
                "provider is required. Pass it to create() or set cloud on AsyncGravixLayer client."
            )
        if not resolved_region:
            raise ValueError(
                "region is required. Pass it to create() or set region on AsyncGravixLayer client."
            )

        data: Dict[str, Any] = {
            "provider": resolved_provider,
            "region": resolved_region,
            "template": template,
        }
        if timeout is not None:
            data["timeout"] = timeout
        if env_vars:
            data["env_vars"] = env_vars
        if metadata:
            data["metadata"] = metadata
        if internet_access is not None:
            data["internet_access"] = internet_access
        if agent_id is not None:
            data["agent_id"] = agent_id

        response = await self._make_agents_request("POST", "runtimes", data)
        result = self._apply_defaults(response.json(), template=template)
        rt = Runtime.from_api(result)
        rt._client = self.client
        return rt

    async def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> RuntimeList:
        """List all runtimes."""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        endpoint = f"runtimes?{urlencode(params)}" if params else "runtimes"
        response = await self._make_agents_request("GET", endpoint)
        result = response.json()

        runtimes_list = []
        for s in result["runtimes"]:
            sb = Runtime.from_api(self._apply_defaults(s))
            sb._client = self.client
            runtimes_list.append(sb)
        return RuntimeList(runtimes=runtimes_list, total=result["total"])

    async def get(self, runtime_id: str) -> Runtime:
        """Get detailed information about a specific runtime."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("GET", f"runtimes/{runtime_id}")
        result = self._apply_defaults(response.json())
        rt = Runtime.from_api(result)
        rt._client = self.client
        return rt

    async def kill(self, runtime_id: str) -> RuntimeKillResponse:
        """Terminate a running runtime immediately."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("DELETE", f"runtimes/{runtime_id}")
        result = response.json()
        return RuntimeKillResponse(**result)

    async def connect(self, runtime_id: str) -> Dict[str, Any]:
        """Connect to an existing runtime.

        Args:
            runtime_id: Target runtime ID.

        Returns:
            Dict with runtime_id, status, domain, and message.
        """
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/connect")
        return response.json()

    # Runtime Configuration Methods

    async def set_timeout(self, runtime_id: str, timeout: int) -> RuntimeTimeoutResponse:
        """Update the timeout for a running runtime."""
        _validate_runtime_id(runtime_id)
        data = {"timeout": timeout}
        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/timeout", data)
        result = response.json()
        return RuntimeTimeoutResponse(**result)

    async def get_metrics(self, runtime_id: str) -> RuntimeMetrics:
        """Get current resource usage metrics for a runtime."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("GET", f"runtimes/{runtime_id}/metrics")
        result = response.json()
        filtered = {k: v for k, v in result.items() if k in _METRICS_FIELDS}
        return RuntimeMetrics(**filtered)

    async def get_host_url(self, runtime_id: str, port: int) -> RuntimeHostURL:
        """Get the public URL for accessing a specific port on the runtime."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("GET", f"runtimes/{runtime_id}/host/{port}")
        result = response.json()
        return RuntimeHostURL(**result)

    # File Operations Methods

    async def read_file(self, runtime_id: str, path: str) -> FileReadResponse:
        """Read the contents of a file from the runtime filesystem."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        data = {"path": path}
        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/files/read", data)
        result = response.json()
        return FileReadResponse(**result)

    async def write_file(self, runtime_id: str, path: str, content: str) -> FileWriteResponse:
        """Write content to a file in the runtime filesystem."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        data = {"path": path, "content": content}
        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/files/write", data)
        result = response.json()
        return FileWriteResponse(**result)

    async def list_files(self, runtime_id: str, path: str) -> FileListResponse:
        """List files and directories in a specified path."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        data = {"path": path}
        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/files/list", data)
        result = response.json()

        files = []
        for file_info in result["files"]:
            mapped_info = {
                "name": file_info.get("name", ""),
                "size": file_info.get("size", 0),
                "is_dir": file_info.get("is_dir", False),
                "modified_at": file_info.get("modified_at") or file_info.get("mod_time", ""),
                "mode": file_info.get("mode"),
            }
            files.append(FileInfo(**mapped_info))

        return FileListResponse(files=files)

    async def delete_file(self, runtime_id: str, path: str) -> FileDeleteResponse:
        """Delete a file or directory from the runtime filesystem."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        data = {"path": path}
        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/files/delete", data)
        result = response.json()
        return FileDeleteResponse(**result)

    async def make_directory(self, runtime_id: str, path: str) -> DirectoryCreateResponse:
        """Create a new directory in the runtime filesystem."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        data = {"path": path}
        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/files/mkdir", data)
        result = response.json()
        return DirectoryCreateResponse(**result)

    async def upload_file(self, runtime_id: str, file: BinaryIO, path: Optional[str] = None) -> FileUploadResponse:
        """Upload a file to the runtime filesystem using multipart form data."""
        _validate_runtime_id(runtime_id)
        data = {}
        if path:
            data["path"] = path

        files = {"file": file}
        response = await self._make_agents_request(
            "POST", f"runtimes/{runtime_id}/upload", data=data, files=files
        )
        result = response.json()
        return FileUploadResponse(**result)

    async def download_file(self, runtime_id: str, path: str) -> bytes:
        """Download a file from the runtime filesystem."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        endpoint = f"runtimes/{runtime_id}/download?{urlencode({'path': path})}"
        response = await self._make_agents_request("GET", endpoint)
        return response.content

    # Multipart File Write Methods

    @staticmethod
    def _coerce_to_bytes(data: Union[str, bytes, BinaryIO]) -> bytes:
        """Convert str, bytes, or file-like object to bytes."""
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, bytes):
            return data
        if hasattr(data, "read"):
            return data.read()
        raise TypeError(f"Expected str, bytes, or file-like object, got {type(data).__name__}")

    async def write(
        self,
        runtime_id: str,
        path: str,
        data: Union[str, bytes, BinaryIO],
        user: Optional[str] = None,
        mode: Optional[int] = None,
    ) -> WriteResult:
        """Write a single file to the runtime using multipart upload.

        Args:
            runtime_id: ID of the target runtime
            path: Destination path inside the runtime
            data: File content as str, bytes, or file-like object
            user: Optional owner username for the file
            mode: Optional file permissions as octal int (e.g. 0o755)

        Returns:
            WriteResult with path, name, and type info
        """
        _validate_runtime_id(runtime_id)
        content = self._coerce_to_bytes(data)
        filename = os.path.basename(path)

        params: Dict[str, str] = {"path": path}
        if user:
            params["username"] = user
        if mode is not None:
            params["mode"] = oct(mode)

        endpoint = f"runtimes/{runtime_id}/files?{urlencode(params)}"
        files = {"file": (filename, content, "application/octet-stream")}
        response = await self._make_agents_request("POST", endpoint, files=files)
        result = response.json()

        if isinstance(result, list) and len(result) > 0:
            entry = result[0]
            return WriteResult(
                path=entry.get("path", path),
                name=entry.get("name", filename),
                type=entry.get("type", "file"),
                size=len(content),
            )
        return WriteResult(path=path, name=filename, type="file", size=len(content))

    async def write_files(
        self,
        runtime_id: str,
        entries: List[WriteEntry],
        user: Optional[str] = None,
    ) -> WriteFilesResponse:
        """Write multiple files to the runtime in a single multipart upload.

        Args:
            runtime_id: ID of the target runtime
            entries: List of WriteEntry objects with path, data, and optional mode
            user: Optional default owner username for all files

        Returns:
            WriteFilesResponse with per-file results and partial_failure flag
        """
        _validate_runtime_id(runtime_id)
        if not entries:
            return WriteFilesResponse(files=[], partial_failure=False)

        multipart_files = []
        for entry in entries:
            content = self._coerce_to_bytes(entry.data)
            multipart_files.append(("file", (entry.path, content, "application/octet-stream")))

        params: Dict[str, str] = {}
        if user:
            params["username"] = user
        query = f"?{urlencode(params)}" if params else ""

        endpoint = f"runtimes/{runtime_id}/files{query}"
        response = await self._make_agents_request("POST", endpoint, files=multipart_files)
        result = response.json()
        partial_failure = response.status_code == 207

        file_results = []
        if isinstance(result, list):
            for entry_result in result:
                file_results.append(WriteResult(
                    path=entry_result.get("path", ""),
                    name=entry_result.get("name", ""),
                    type=entry_result.get("type", "file"),
                    error=entry_result.get("error"),
                ))
        elif isinstance(result, dict) and "files" in result:
            for entry_result in result["files"]:
                file_results.append(WriteResult(
                    path=entry_result.get("path", ""),
                    name=entry_result.get("name", ""),
                    type=entry_result.get("type", "file"),
                    error=entry_result.get("error"),
                ))

        return WriteFilesResponse(files=file_results, partial_failure=partial_failure)

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
            data["timeout"] = timeout * 1000

        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/commands/run", data)
        result = response.json()
        return CommandRunResponse(**result)

    # Code Execution Methods

    async def run_code(
        self,
        runtime_id: str,
        code: str,
        language: Optional[str] = "python",
        context_id: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> CodeRunResponse:
        """Execute code in the runtime using Jupyter kernel.

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

        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/code/run", data)
        return CodeRunResponse.from_api(response.json())

    async def create_code_context(
        self, runtime_id: str, language: Optional[str] = "python", cwd: Optional[str] = None
    ) -> CodeContext:
        """Create an isolated code execution context."""
        _validate_runtime_id(runtime_id)
        data: Dict[str, Any] = {}
        if language:
            data["language"] = language
        if cwd:
            data["cwd"] = cwd

        response = await self._make_agents_request("POST", f"runtimes/{runtime_id}/code/contexts", data)
        result = response.json()

        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", language or "python"),
            "cwd": result.get("cwd", cwd or "/home/user"),
        }

        return CodeContext(**mapped_result)

    async def get_code_context(self, runtime_id: str, context_id: str) -> CodeContext:
        """Get information about a code execution context."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("GET", f"runtimes/{runtime_id}/code/contexts/{context_id}")
        result = response.json()

        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", "python"),
            "cwd": result.get("cwd", "/home/user"),
        }

        return CodeContext(**mapped_result)

    async def delete_code_context(self, runtime_id: str, context_id: str) -> CodeContextDeleteResponse:
        """Delete a code execution context."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("DELETE", f"runtimes/{runtime_id}/code/contexts/{context_id}")
        result = response.json()
        return CodeContextDeleteResponse(**result)

    # SSH Methods

    async def enable_ssh(self, runtime_id: str, regenerate_keys: bool = False) -> SSHInfo:
        """Enable SSH access on a runtime."""
        _validate_runtime_id(runtime_id)
        endpoint = f"runtimes/{runtime_id}/ssh/enable"
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
            key_fingerprint=result.get("key_fingerprint"),
            private_key=result.get("private_key"),
            public_key=result.get("public_key"),
            ssh_config=result.get("ssh_config"),
            message=result.get("message"),
        )

    async def disable_ssh(self, runtime_id: str) -> None:
        """Disable SSH access on a runtime."""
        _validate_runtime_id(runtime_id)
        await self._make_agents_request("POST", f"runtimes/{runtime_id}/ssh/disable")

    async def ssh_status(self, runtime_id: str) -> SSHStatus:
        """Get current SSH status for a runtime."""
        _validate_runtime_id(runtime_id)
        response = await self._make_agents_request("GET", f"runtimes/{runtime_id}/ssh/status")
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
        await self._make_agents_request("POST", f"runtimes/{runtime_id}/pause")

    async def resume(self, runtime_id: str) -> None:
        """Resume a paused runtime."""
        _validate_runtime_id(runtime_id)
        await self._make_agents_request("POST", f"runtimes/{runtime_id}/resume")


class AsyncRuntimeTemplates:
    """Runtime Templates resource for asynchronous client"""

    def __init__(self, client):
        self.client = client

    async def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)"""
        return await self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    async def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> TemplateList:
        """List available runtime templates."""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        endpoint = "templates"
        if params:
            endpoint = f"templates?{urlencode(params)}"

        response = await self._make_agents_request("GET", endpoint)
        result = response.json()

        templates = [Template(**template) for template in result["templates"]]
        return TemplateList(templates=templates, limit=result["limit"], offset=result["offset"])


class AsyncRuntimeResource:
    """Main Runtime resource — the public API surface at ``client.runtime``.

    All runtime operations are available directly::

        await client.runtime.create(template="python-base-v1")
        await client.runtime.run_code(runtime_id, "print('hi')")
        await client.runtime.kill(runtime_id)

    Template listing is available via ``await client.runtime.templates.list()``.
    """

    def __init__(self, client):
        self.client = client
        self._runtimes = AsyncRuntimes(client)
        self.templates = AsyncRuntimeTemplates(client)

    def __getattr__(self, name: str):
        """Delegate any attribute not on this class to the underlying AsyncRuntimes instance."""
        return getattr(self._runtimes, name)
