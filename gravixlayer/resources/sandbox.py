"""
Sandbox API resource for synchronous client
"""

import dataclasses
import os
from typing import List, Dict, Any, Optional, BinaryIO, Union
from urllib.parse import urlencode

from ..types.sandbox import (
    Sandbox,
    SandboxList,
    SandboxMetrics,
    SandboxTimeout,
    SandboxTimeoutResponse,
    SandboxHostURL,
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
    SandboxKillResponse,
    _validate_sandbox_id,
    _validate_path,
)

# Field names known to the SandboxMetrics dataclass — cached once at import time
_METRICS_FIELDS: frozenset = frozenset(f.name for f in dataclasses.fields(SandboxMetrics))

# Default values for sandbox response fields the API may omit
_SANDBOX_DEFAULTS: Dict[str, Any] = {
    "metadata": {},
    "template": None,
    "template_id": None,
    "started_at": None,
    "timeout_at": None,
    "cpu_count": None,
    "memory_mb": None,
    "ended_at": None,
}


class Sandboxes:
    """Sandboxes resource for synchronous client"""

    def __init__(self, client):
        self.client = client

    def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)"""
        return self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    @staticmethod
    def _apply_defaults(data: Dict[str, Any], template: Optional[str] = None) -> Dict[str, Any]:
        """Fill in missing sandbox fields with safe defaults."""
        for key, default in _SANDBOX_DEFAULTS.items():
            if key not in data or data[key] is None:
                data[key] = default
        if template and not data.get("template"):
            data["template"] = template
        return data

    # Sandbox Lifecycle Methods

    def create(
        self,
        provider: Optional[str] = None,
        region: Optional[str] = None,
        template: Optional[str] = "python-base-v1",
        timeout: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        internet_access: Optional[bool] = None,
        agent_id: Optional[str] = None,
    ) -> Sandbox:
        """Create a new sandbox instance.

        Args:
            provider: Cloud provider (falls back to client.cloud if not set)
            region: Cloud region (falls back to client.region if not set)
            template: Template name or ID to use
            timeout: Sandbox timeout in seconds (default: None = no timeout)
            env_vars: Environment variables for the sandbox
            metadata: Metadata tags for the sandbox
            internet_access: Whether to allow internet access (default: None = server default)
            agent_id: Agent ID to associate with the sandbox
        """
        resolved_provider = provider or getattr(self.client, "cloud", None)
        resolved_region = region or getattr(self.client, "region", None)
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
        if env_vars:
            data["env_vars"] = env_vars
        if metadata:
            data["metadata"] = metadata
        if internet_access is not None:
            data["internet_access"] = internet_access
        if agent_id is not None:
            data["agent_id"] = agent_id

        response = self._make_agents_request("POST", "sandboxes", data)
        result = self._apply_defaults(response.json(), template=template)
        sandbox = Sandbox.from_api(result)
        sandbox._client = self.client
        return sandbox

    def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> SandboxList:
        """List all sandboxes"""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        endpoint = f"sandboxes?{urlencode(params)}" if params else "sandboxes"
        response = self._make_agents_request("GET", endpoint)
        result = response.json()

        sandboxes = []
        for s in result["sandboxes"]:
            sb = Sandbox.from_api(self._apply_defaults(s))
            sb._client = self.client
            sandboxes.append(sb)
        return SandboxList(sandboxes=sandboxes, total=result["total"])

    def get(self, sandbox_id: str) -> Sandbox:
        """Get detailed information about a specific sandbox."""
        _validate_sandbox_id(sandbox_id)
        response = self._make_agents_request("GET", f"sandboxes/{sandbox_id}")
        result = self._apply_defaults(response.json())
        sandbox = Sandbox.from_api(result)
        sandbox._client = self.client
        return sandbox

    def kill(self, sandbox_id: str) -> SandboxKillResponse:
        """Terminate a running sandbox immediately."""
        _validate_sandbox_id(sandbox_id)
        response = self._make_agents_request("DELETE", f"sandboxes/{sandbox_id}")
        result = response.json()
        return SandboxKillResponse(**result)

    def connect(self, sandbox_id: str) -> Dict[str, Any]:
        """Connect to an existing sandbox.

        Args:
            sandbox_id: Target sandbox ID.

        Returns:
            Dict with sandbox_id, status, domain, and message.
        """
        _validate_sandbox_id(sandbox_id)
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/connect")
        return response.json()

    # Sandbox Configuration Methods

    def set_timeout(self, sandbox_id: str, timeout: int) -> SandboxTimeoutResponse:
        """Update the timeout for a running sandbox."""
        _validate_sandbox_id(sandbox_id)
        data = {"timeout": timeout}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/timeout", data)
        result = response.json()
        return SandboxTimeoutResponse(**result)

    def get_metrics(self, sandbox_id: str) -> SandboxMetrics:
        """Get current resource usage metrics for a sandbox."""
        _validate_sandbox_id(sandbox_id)
        response = self._make_agents_request("GET", f"sandboxes/{sandbox_id}/metrics")
        result = response.json()
        filtered = {k: v for k, v in result.items() if k in _METRICS_FIELDS}
        return SandboxMetrics(**filtered)

    def get_host_url(self, sandbox_id: str, port: int) -> SandboxHostURL:
        """Get the public URL for accessing a specific port on the sandbox."""
        _validate_sandbox_id(sandbox_id)
        response = self._make_agents_request("GET", f"sandboxes/{sandbox_id}/host/{port}")
        result = response.json()
        return SandboxHostURL(**result)

    # File Operations Methods

    def read_file(self, sandbox_id: str, path: str) -> FileReadResponse:
        """Read the contents of a file from the sandbox filesystem."""
        _validate_sandbox_id(sandbox_id)
        _validate_path(path)
        data = {"path": path}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/read", data)
        result = response.json()
        return FileReadResponse(**result)

    def write_file(self, sandbox_id: str, path: str, content: str) -> FileWriteResponse:
        """Write content to a file in the sandbox filesystem."""
        _validate_sandbox_id(sandbox_id)
        _validate_path(path)
        data = {"path": path, "content": content}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/write", data)
        result = response.json()
        return FileWriteResponse(**result)

    def list_files(self, sandbox_id: str, path: str) -> FileListResponse:
        """List files and directories in a specified path."""
        _validate_sandbox_id(sandbox_id)
        _validate_path(path)
        data = {"path": path}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/list", data)
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

    def delete_file(self, sandbox_id: str, path: str) -> FileDeleteResponse:
        """Delete a file or directory from the sandbox filesystem."""
        _validate_sandbox_id(sandbox_id)
        _validate_path(path)
        data = {"path": path}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/delete", data)
        result = response.json()
        return FileDeleteResponse(**result)

    def make_directory(self, sandbox_id: str, path: str) -> DirectoryCreateResponse:
        """Create a new directory in the sandbox filesystem."""
        _validate_sandbox_id(sandbox_id)
        _validate_path(path)
        data = {"path": path}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/mkdir", data)
        result = response.json()
        return DirectoryCreateResponse(**result)

    def upload_file(self, sandbox_id: str, file: BinaryIO, path: Optional[str] = None) -> FileUploadResponse:
        """Upload a file to the sandbox filesystem using multipart form data."""
        _validate_sandbox_id(sandbox_id)
        files = {"file": file}
        data = {}
        if path:
            data["path"] = path

        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/upload", data=data, files=files)
        result = response.json()
        return FileUploadResponse(**result)

    def download_file(self, sandbox_id: str, path: str) -> bytes:
        """Download a file from the sandbox filesystem."""
        _validate_sandbox_id(sandbox_id)
        _validate_path(path)
        endpoint = f"sandboxes/{sandbox_id}/download?{urlencode({'path': path})}"
        response = self._make_agents_request("GET", endpoint)
        return response.content

    # Multipart File Write Methods

    @staticmethod
    def _coerce_to_bytes(data: Union[str, bytes, BinaryIO]) -> bytes:
        """Convert str, bytes, or file-like object to bytes"""
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, bytes):
            return data
        if hasattr(data, "read"):
            return data.read()
        raise TypeError(f"Expected str, bytes, or file-like object, got {type(data).__name__}")

    def write(
        self,
        sandbox_id: str,
        path: str,
        data: Union[str, bytes, BinaryIO],
        user: Optional[str] = None,
        mode: Optional[int] = None,
    ) -> WriteResult:
        """Write a single file to the sandbox using multipart upload.

        Sends raw bytes via multipart/form-data - no base64 encoding.

        Args:
            sandbox_id: ID of the target sandbox
            path: Destination path inside the sandbox (absolute or relative to /home/user/)
            data: File content as str, bytes, or file-like object
            user: Optional owner username for the file
            mode: Optional file permissions as octal int (e.g. 0o755)

        Returns:
            WriteResult with path, name, and type info

        Example:
            >>> sandboxes.write(sid, "/home/user/hello.py", "print('hello')")
            >>> sandboxes.write(sid, "data.bin", b"\\x00\\x01\\x02")
            >>> with open("local.txt", "rb") as f:
            ...     sandboxes.write(sid, "/tmp/remote.txt", f)
        """
        content = self._coerce_to_bytes(data)
        filename = os.path.basename(path)

        # Build query params with proper URL encoding
        params: Dict[str, str] = {"path": path}
        if user:
            params["username"] = user
        if mode is not None:
            params["mode"] = oct(mode)

        endpoint = f"sandboxes/{sandbox_id}/files?{urlencode(params)}"
        files = {"file": (filename, content, "application/octet-stream")}
        response = self._make_agents_request("POST", endpoint, files=files)
        result = response.json()

        # Response is an array of file results
        if isinstance(result, list) and len(result) > 0:
            entry = result[0]
            return WriteResult(
                path=entry.get("path", path),
                name=entry.get("name", filename),
                type=entry.get("type", "file"),
                size=len(content),
            )
        return WriteResult(path=path, name=filename, type="file", size=len(content))

    def write_files(
        self,
        sandbox_id: str,
        entries: List[WriteEntry],
        user: Optional[str] = None,
    ) -> WriteFilesResponse:
        """Write multiple files to the sandbox in a single multipart upload.

        Sends all files as separate parts in one HTTP POST - no base64.

        Args:
            sandbox_id: ID of the target sandbox
            entries: List of WriteEntry objects with path, data, and optional mode
            user: Optional default owner username for all files

        Returns:
            WriteFilesResponse with per-file results and partial_failure flag

        Example:
            >>> from gravixlayer.types.sandbox import WriteEntry
            >>> sandboxes.write_files(sid, [
            ...     WriteEntry(path="/home/user/main.py", data="print('hello')"),
            ...     WriteEntry(path="/home/user/config.json", data=b'{"key": "val"}'),
            ...     WriteEntry(path="/tmp/script.sh", data="#!/bin/bash\\necho hi", mode=0o755),
            ... ])
        """
        if not entries:
            return WriteFilesResponse(files=[], partial_failure=False)

        # Build multipart parts: each file is a ("file", (filename, content, mime)) tuple
        multipart_files = []
        for entry in entries:
            content = self._coerce_to_bytes(entry.data)
            # Use full path as filename so the server preserves the destination
            multipart_files.append(("file", (entry.path, content, "application/octet-stream")))

        # Build query params with proper URL encoding
        params: Dict[str, str] = {}
        if user:
            params["username"] = user
        query = f"?{urlencode(params)}" if params else ""

        endpoint = f"sandboxes/{sandbox_id}/files{query}"
        response = self._make_agents_request("POST", endpoint, files=multipart_files)
        result = response.json()
        partial_failure = response.status_code == 207

        # Parse results
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

    def run_cmd(
        self,
        sandbox_id: str,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> CommandRunResponse:
        """Execute a shell command in the sandbox.

        Args:
            sandbox_id: Target sandbox ID.
            command: The command string to execute.
            args: Additional arguments.
            working_dir: Working directory.
            environment: Environment variables.
            timeout: Maximum execution time in **seconds** (converted to ms for the backend).
        """
        _validate_sandbox_id(sandbox_id)
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

        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/commands/run", data)
        result = response.json()
        return CommandRunResponse(**result)

    # Code Execution Methods

    def run_code(
        self,
        sandbox_id: str,
        code: str,
        language: Optional[str] = "python",
        context_id: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> CodeRunResponse:
        """Execute code in the sandbox using Jupyter kernel.

        Args:
            sandbox_id: Target sandbox ID.
            code: Code to execute.
            language: Language (default: "python").
            context_id: Execution context ID for state persistence.
            environment: Environment variables.
            timeout: Maximum execution time in **seconds** (backend expects seconds for code execution).
        """
        _validate_sandbox_id(sandbox_id)
        data: Dict[str, Any] = {"code": code}
        if language is not None:
            data["language"] = language
        if context_id is not None:
            data["context_id"] = context_id
        if environment is not None:
            data["environment"] = environment
        if timeout is not None:
            data["timeout"] = timeout

        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/code/run", data)
        return CodeRunResponse.from_api(response.json())

    def create_code_context(
        self, sandbox_id: str, language: Optional[str] = "python", cwd: Optional[str] = None
    ) -> CodeContext:
        """Create an isolated code execution context."""
        _validate_sandbox_id(sandbox_id)
        data = {}
        if language:
            data["language"] = language
        if cwd:
            data["cwd"] = cwd

        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/code/contexts", data)
        result = response.json()

        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", language or "python"),
            "cwd": result.get("cwd", cwd or "/home/user"),
        }

        return CodeContext(**mapped_result)

    def get_code_context(self, sandbox_id: str, context_id: str) -> CodeContext:
        """Get information about a code execution context."""
        _validate_sandbox_id(sandbox_id)
        response = self._make_agents_request("GET", f"sandboxes/{sandbox_id}/code/contexts/{context_id}")
        result = response.json()

        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", "python"),
            "cwd": result.get("cwd", "/home/user"),
        }

        return CodeContext(**mapped_result)

    def delete_code_context(self, sandbox_id: str, context_id: str) -> CodeContextDeleteResponse:
        """Delete a code execution context."""
        _validate_sandbox_id(sandbox_id)
        response = self._make_agents_request("DELETE", f"sandboxes/{sandbox_id}/code/contexts/{context_id}")
        result = response.json()
        return CodeContextDeleteResponse(**result)

    # SSH Methods

    def enable_ssh(self, sandbox_id: str, regenerate_keys: bool = False) -> SSHInfo:
        """Enable SSH access on a sandbox.

        Args:
            sandbox_id: Target sandbox ID.
            regenerate_keys: If True, regenerate SSH keys even if already enabled.

        Returns:
            SSHInfo with connection details.
        """
        _validate_sandbox_id(sandbox_id)
        endpoint = f"sandboxes/{sandbox_id}/ssh/enable"
        if regenerate_keys:
            endpoint += "?regenerate_keys=true"
        response = self._make_agents_request("POST", endpoint)
        result = response.json()
        return SSHInfo(
            sandbox_id=result.get("sandbox_id", sandbox_id),
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

    def disable_ssh(self, sandbox_id: str) -> None:
        """Disable SSH access on a sandbox."""
        _validate_sandbox_id(sandbox_id)
        self._make_agents_request("POST", f"sandboxes/{sandbox_id}/ssh/disable")

    def ssh_status(self, sandbox_id: str) -> SSHStatus:
        """Get current SSH status for a sandbox."""
        _validate_sandbox_id(sandbox_id)
        response = self._make_agents_request("GET", f"sandboxes/{sandbox_id}/ssh/status")
        result = response.json()
        return SSHStatus(
            sandbox_id=result.get("sandbox_id", sandbox_id),
            enabled=result.get("enabled", False),
            port=result.get("port", 0),
            username=result.get("username", ""),
            daemon_running=result.get("daemon_running", False),
        )

    # State Management Methods

    def pause(self, sandbox_id: str) -> None:
        """Pause a running sandbox."""
        _validate_sandbox_id(sandbox_id)
        self._make_agents_request("POST", f"sandboxes/{sandbox_id}/pause")

    def resume(self, sandbox_id: str) -> None:
        """Resume a paused sandbox."""
        _validate_sandbox_id(sandbox_id)
        self._make_agents_request("POST", f"sandboxes/{sandbox_id}/resume")


class SandboxTemplates:
    """Sandbox Templates resource for synchronous client"""

    def __init__(self, client):
        self.client = client

    def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)"""
        return self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> TemplateList:
        """List available sandbox templates"""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        endpoint = f"templates?{urlencode(params)}" if params else "templates"
        response = self._make_agents_request("GET", endpoint)
        result = response.json()

        templates = [Template(**template) for template in result["templates"]]
        return TemplateList(templates=templates, limit=result["limit"], offset=result["offset"])


class SandboxResource:
    """Main Sandbox resource — the public API surface at ``client.sandbox``.

    All sandbox operations are available directly::

        client.sandbox.create(template="python-base-v1")
        client.sandbox.run_code(sandbox_id, "print('hi')")
        client.sandbox.kill(sandbox_id)

    Template listing is available via ``client.sandbox.templates.list()``.
    """

    def __init__(self, client):
        self.client = client
        self._sandboxes = Sandboxes(client)
        self.templates = SandboxTemplates(client)

    def __getattr__(self, name: str):
        """Delegate any attribute not on this class to the underlying Sandboxes instance."""
        return getattr(self._sandboxes, name)
