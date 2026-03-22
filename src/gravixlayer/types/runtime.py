"""
Type definitions for Runtime API.

Aligned with the backend Go types in internal/agents/types.go and
internal/agents/runtime_api_handlers.go.
"""

import dataclasses
import os
import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _validate_runtime_id(runtime_id: str) -> None:
    """Validate that a runtime ID is a well-formed UUID."""
    if not runtime_id or not _UUID_RE.match(runtime_id):
        raise ValueError(f"Invalid runtime_id: expected UUID, got {runtime_id!r}")


def _validate_path(path: str) -> None:
    """Validate a filesystem path is non-empty, has no null bytes, and no traversal."""
    if not path:
        raise ValueError("Path must not be empty")
    if "\x00" in path:
        raise ValueError("Path must not contain null bytes")
    # Reject path traversal attempts
    normalized = os.path.normpath(path)
    if ".." in normalized.split(os.sep) or ".." in normalized.split("/"):
        raise ValueError("Path must not contain directory traversal (..)")


def _validate_template_id(template_id: str) -> None:
    """Validate a template identifier (UUID or name)."""
    if not template_id or not template_id.strip():
        raise ValueError("Template ID must not be empty")


@dataclass
class Runtime:
    """Runtime object returned by the API.

    Fields match the backend RuntimeAPIResponse struct.
    """

    runtime_id: str
    status: str
    template: Optional[str] = None
    template_id: Optional[str] = None
    provider: Optional[str] = None
    region: Optional[str] = None
    started_at: Optional[str] = None
    timeout_at: Optional[str] = None
    cpu_count: Optional[int] = None
    memory_mb: Optional[int] = None
    disk_size_mb: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    ended_at: Optional[str] = None
    ip_address: Optional[str] = None
    ssh_enabled: Optional[bool] = None

    # Cached set of public field names — populated once on first use
    _cached_fields: Optional[frozenset] = dataclasses.field(
        default=None, init=False, repr=False, compare=False
    )

    @classmethod
    def _known_fields(cls) -> frozenset:
        """Return the set of public field names for this dataclass (cached)."""
        if cls._cached_fields is None:
            cls._cached_fields = frozenset(
                f.name for f in dataclasses.fields(cls)
                if not f.name.startswith("_")
            )
        return cls._cached_fields

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Runtime":
        """Create a Runtime from an API response dict, ignoring unknown fields."""
        known = cls._known_fields()
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def __post_init__(self):
        """Initialize client reference after dataclass creation"""
        self._client = None
        self._alive = True
        self._timeout_seconds = None
        self._owns_client = False

    def _require_alive(self) -> None:
        """Guard: raise if runtime is terminated or client is missing."""
        if not self._alive:
            raise RuntimeError("Runtime has been terminated")
        if self._client is None:
            raise RuntimeError("Client not initialized. Use Runtime.create() or client.runtime.create() instead.")

    def close(self) -> None:
        """Close the underlying HTTP client if this Runtime owns it.

        Only closes the client when the Runtime was created via
        ``Runtime.create()`` without passing an existing client.
        """
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        # Best-effort cleanup for unclosed sessions
        if getattr(self, "_owns_client", False) and self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass

    @property
    def timeout(self) -> Optional[int]:
        """Get the timeout value in seconds"""
        return self._timeout_seconds

    @classmethod
    def create(
        cls,
        template: str = "python-base-v1",
        cloud: str = "azure",
        region: str = "eastus2",
        timeout: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        internet_access: Optional[bool] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> "Runtime":
        """
        Create a new runtime instance with simplified interface.

        Args:
            template: Template to use (default: "python-base-v1")
            cloud: Cloud provider (default: "azure")
            region: Region to deploy in (default: "eastus2")
            timeout: Timeout in seconds (default: None = no timeout). Pass 0 to explicitly disable timeout.
            metadata: Optional metadata tags
            internet_access: Whether to allow internet access (default: None = server default)
            api_key: API key (uses GRAVIXLAYER_API_KEY env var if not provided)
            base_url: Base URL (uses GRAVIXLAYER_BASE_URL env var if not provided)
            client: Existing GravixLayer client to reuse (avoids creating a new session)

        Returns:
            Runtime instance ready for code execution
        """
        if client is None:
            from ..client import GravixLayer
            client = GravixLayer(api_key=api_key, base_url=base_url, cloud=cloud, region=region)
            owns_client = True
        else:
            owns_client = False

        runtime_response = client.runtime.create(
            template=template,
            timeout=timeout,
            metadata=metadata or {},
            internet_access=internet_access,
        )

        instance = cls(
            runtime_id=runtime_response.runtime_id,
            status=runtime_response.status,
            template=runtime_response.template,
            template_id=runtime_response.template_id,
            provider=runtime_response.provider,
            region=runtime_response.region,
            started_at=runtime_response.started_at,
            timeout_at=runtime_response.timeout_at,
            cpu_count=runtime_response.cpu_count,
            memory_mb=runtime_response.memory_mb,
            disk_size_mb=runtime_response.disk_size_mb,
            metadata=runtime_response.metadata,
            ended_at=runtime_response.ended_at,
            ip_address=runtime_response.ip_address,
            ssh_enabled=runtime_response.ssh_enabled,
        )

        instance._client = client
        instance._timeout_seconds = timeout
        instance._owns_client = owns_client
        return instance

    def run_code(self, code: str, language: str = "python") -> "Execution":
        """Execute code in the runtime."""
        self._require_alive()
        response = self._client.runtime.run_code(self.runtime_id, code=code, language=language)
        return Execution(response)

    def run_cmd(
        self,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> "Execution":
        """Execute a shell command in the runtime.

        Args:
            command: The command string to execute.
            args: Additional arguments to append.
            working_dir: Working directory for the command.
            timeout: Maximum execution time in seconds.
        """
        self._require_alive()
        response = self._client.runtime.run_cmd(
            self.runtime_id, command=command, args=args or [], working_dir=working_dir, timeout=timeout
        )
        return Execution(response)

    def run_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> "Execution":
        """Execute a shell command in the runtime.

        Alias for :meth:`run_cmd`.
        """
        return self.run_cmd(
            command=command, args=args, working_dir=working_dir, timeout=timeout
        )

    def write_file(self, path: str, content: str) -> None:
        """Write content to a file in the runtime"""
        self._require_alive()
        self._client.runtime.write_file(self.runtime_id, path=path, content=content)

    def read_file(self, path: str) -> str:
        """Read content from a file in the runtime"""
        self._require_alive()
        response = self._client.runtime.read_file(self.runtime_id, path=path)
        return response.content

    def list_files(self, path: str = "/home/user") -> "List[FileInfo]":
        """List files in a directory.

        Returns:
            List of FileInfo objects with name, size, is_dir, modified_at, mode.
        """
        self._require_alive()
        response = self._client.runtime.list_files(self.runtime_id, path=path)
        return response.files

    def delete_file(self, path: str) -> None:
        """Delete a file in the runtime"""
        self._require_alive()
        self._client.runtime.delete_file(self.runtime_id, path=path)

    def upload_file(self, local_path: str, remote_path: str) -> None:
        """Upload a local file to the runtime"""
        self._require_alive()
        with open(local_path, "rb") as f:
            self._client.runtime.upload_file(self.runtime_id, file=f, path=remote_path)

    def write(
        self,
        path: str,
        data: Union[str, bytes, Any],
        user: Optional[str] = None,
        mode: Optional[int] = None,
    ) -> "WriteResult":
        """Write a file to the runtime using multipart upload (no base64).

        Args:
            path: Destination path (absolute or relative to /home/user/)
            data: Content as str, bytes, or file-like object
            user: Optional owner username
            mode: Optional file permissions as octal int (e.g. 0o755)

        Example:
            >>> runtime.write("/home/user/hello.py", "print('hello')")
            >>> runtime.write("data.bin", b"\\x00\\x01\\x02")
            >>> with open("local.txt", "rb") as f:
            ...     runtime.write("/tmp/remote.txt", f)
        """
        self._require_alive()
        return self._client.runtime.write(
            self.runtime_id, path=path, data=data, user=user, mode=mode
        )

    def write_files(
        self,
        entries: "List[WriteEntry]",
        user: Optional[str] = None,
    ) -> "WriteFilesResponse":
        """Write multiple files in a single multipart upload (no base64).

        Args:
            entries: List of WriteEntry(path, data, mode) objects
            user: Optional default owner username for all files

        Example:
            >>> from gravixlayer.types.runtime import WriteEntry
            >>> runtime.write_files([
            ...     WriteEntry(path="main.py", data="print('hello')"),
            ...     WriteEntry(path="config.json", data=b'{"key": "val"}'),
            ...     WriteEntry(path="/tmp/run.sh", data="#!/bin/bash\\necho hi", mode=0o755),
            ... ])
        """
        self._require_alive()
        return self._client.runtime.write_files(
            self.runtime_id, entries=entries, user=user
        )

    def kill(self) -> None:
        """Terminate the runtime and clean up resources."""
        if self._alive and self._client is not None:
            try:
                self._client.runtime.kill(self.runtime_id)
            except Exception:
                pass
            self._alive = False

    def is_alive(self) -> bool:
        """Check if the runtime is still running."""
        if not self._alive or self._client is None:
            return False
        try:
            info = self._client.runtime.get(self.runtime_id)
            return info.status == "running"
        except Exception:
            self._alive = False
            return False

    # -- SSH ---------------------------------------------------------------

    def enable_ssh(self, regenerate_keys: bool = False) -> "SSHInfo":
        """Enable SSH access on the runtime.

        Args:
            regenerate_keys: If True, regenerate SSH keys even if already enabled.

        Returns:
            SSHInfo with connection details.
        """
        self._require_alive()
        return self._client.runtime.enable_ssh(
            self.runtime_id, regenerate_keys=regenerate_keys
        )

    def disable_ssh(self) -> None:
        """Disable SSH access on the runtime."""
        self._require_alive()
        self._client.runtime.disable_ssh(self.runtime_id)

    def ssh_status(self) -> "SSHStatus":
        """Get current SSH status for the runtime."""
        self._require_alive()
        return self._client.runtime.ssh_status(self.runtime_id)

    # -- State management --------------------------------------------------

    def pause(self) -> None:
        """Pause the running runtime."""
        self._require_alive()
        self._client.runtime.pause(self.runtime_id)

    def resume(self) -> None:
        """Resume a paused runtime."""
        self._require_alive()
        self._client.runtime.resume(self.runtime_id)

    def show_info(self) -> None:
        """Display runtime information"""
        print(f"Created runtime: {self.runtime_id}")
        print(f"Template: {self.template}")
        print(f"Status: {self.status}")
        cpu_display = f"{self.cpu_count} CPU" if self.cpu_count else "Unknown CPU"
        memory_display = f"{self.memory_mb}MB RAM" if self.memory_mb else "Unknown RAM"
        print(f"Resources: {cpu_display}, {memory_display}")
        print(f"Started: {self.started_at}")
        print(f"Timeout: {self.timeout_at}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically terminate runtime"""
        self.kill()


@dataclass
class RuntimeList:
    """List of runtimes response"""

    runtimes: List[Runtime]
    total: int


@dataclass
class RuntimeMetrics:
    """Runtime resource usage metrics"""

    timestamp: str = ""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_total: float = 0.0
    disk_read: int = 0
    disk_write: int = 0
    network_rx: int = 0
    network_tx: int = 0


@dataclass
class RuntimeTimeout:
    """Runtime timeout update request"""

    timeout: int


@dataclass
class RuntimeTimeoutResponse:
    """Runtime timeout update response"""

    message: str
    timeout: Optional[int] = None
    timeout_at: Optional[str] = None


@dataclass
class RuntimeHostURL:
    """Runtime host URL response."""

    url: str


# ---------------------------------------------------------------------------
# SSH types (aligned with backend SSHEnableResponse / SSHStatusResponse)
# ---------------------------------------------------------------------------

@dataclass
class SSHInfo:
    """SSH connection info returned when SSH is enabled."""

    runtime_id: str
    enabled: bool
    port: int
    username: str
    connect_cmd: str
    key_fingerprint: Optional[str] = None
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    ssh_config: Optional[str] = None
    message: Optional[str] = None


@dataclass
class SSHStatus:
    """SSH status for a runtime."""

    runtime_id: str
    enabled: bool
    port: int = 0
    username: str = ""
    daemon_running: bool = False


@dataclass
class FileReadResponse:
    """File read response."""

    content: str
    path: Optional[str] = None
    size: Optional[int] = None


@dataclass
class FileWriteResponse:
    """File write response."""

    message: str
    path: Optional[str] = None
    bytes_written: Optional[int] = None


@dataclass
class FileInfo:
    """File information.

    Maps backend FileInfo which sends: name, size, mode, mod_time, is_dir.
    """

    name: str
    size: int
    is_dir: bool
    modified_at: str = ""
    mode: Optional[str] = None


@dataclass
class FileListResponse:
    """File list response."""

    files: List[FileInfo]


@dataclass
class FileDeleteResponse:
    """File delete response."""

    message: str
    path: Optional[str] = None


@dataclass
class DirectoryCreateResponse:
    """Directory create response."""

    message: str
    path: Optional[str] = None


@dataclass
class FileUploadResponse:
    """File upload response"""

    message: str
    path: Optional[str] = None
    size: Optional[int] = None


@dataclass
class WriteEntry:
    """Entry for batch file write via multipart upload

    Args:
        path: Destination path inside the runtime (absolute or relative to /home/user/)
        data: File content as str, bytes, or file-like object (BinaryIO)
        mode: Optional file permissions as octal int (e.g. 0o755)
    """

    path: str
    data: Union[str, bytes, Any]  # str | bytes | BinaryIO
    mode: Optional[int] = None


@dataclass
class WriteResult:
    """Result for a single file in a batch write"""

    path: str
    name: str
    type: str
    size: Optional[int] = None
    error: Optional[str] = None


@dataclass
class WriteFilesResponse:
    """Response from write/write_files operations"""

    files: List[WriteResult]
    partial_failure: bool = False


@dataclass
class CommandRunResponse:
    """Command execution response.

    Maps backend RuntimeAPICommandResponse exactly.
    """

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    success: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Code execution types (aligned with backend Execution / Result / Logs)
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """A single result from code execution.

    Maps to the backend Result struct: text, html, json, png, jpeg, svg,
    markdown, chart.
    """

    text: str = ""
    html: str = ""
    json: Optional[Any] = None
    png: str = ""
    jpeg: str = ""
    svg: str = ""
    markdown: str = ""
    chart: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionError:
    """Error from code execution.

    Maps to the backend ExecutionError struct: name, value, traceback.
    """

    name: str = ""
    value: str = ""
    traceback: str = ""


@dataclass
class ExecutionLogs:
    """Stdout/stderr from code execution.

    Maps to the backend Logs struct.
    """

    stdout: List[str] = field(default_factory=list)
    stderr: List[str] = field(default_factory=list)


@dataclass
class CodeRunResponse:
    """Code execution response.

    Maps to the backend Execution struct. Provides convenience properties
    for common access patterns so users don't need to dig into nested dicts.
    """

    results: List[ExecutionResult] = field(default_factory=list)
    logs: ExecutionLogs = field(default_factory=ExecutionLogs)
    error: Optional[ExecutionError] = None

    @property
    def text(self) -> str:
        """Get the text output from the first result, or stdout joined."""
        if self.results and self.results[0].text:
            return self.results[0].text
        return self.stdout_text

    @property
    def stdout_text(self) -> str:
        """Get stdout as a single string."""
        return "\n".join(self.logs.stdout or [])

    @property
    def stderr_text(self) -> str:
        """Get stderr as a single string."""
        return "\n".join(self.logs.stderr or [])

    @property
    def success(self) -> bool:
        """True if no error occurred."""
        return self.error is None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "CodeRunResponse":
        """Parse a backend Execution JSON dict into a typed CodeRunResponse."""
        # Parse results list
        raw_results = data.get("results") or []
        results: List[ExecutionResult] = []
        if isinstance(raw_results, list):
            for r in raw_results:
                if isinstance(r, dict):
                    results.append(ExecutionResult(
                        text=r.get("text", ""),
                        html=r.get("html", ""),
                        json=r.get("json"),
                        png=r.get("png", ""),
                        jpeg=r.get("jpeg", ""),
                        svg=r.get("svg", ""),
                        markdown=r.get("markdown", ""),
                        chart=r.get("chart"),
                    ))

        # Parse logs
        raw_logs = data.get("logs") or {}
        logs = ExecutionLogs(
            stdout=(raw_logs.get("stdout") or []) if isinstance(raw_logs, dict) else [],
            stderr=(raw_logs.get("stderr") or []) if isinstance(raw_logs, dict) else [],
        )

        # Parse error
        error = None
        raw_error = data.get("error")
        if raw_error and isinstance(raw_error, dict):
            error = ExecutionError(
                name=raw_error.get("name", ""),
                value=raw_error.get("value", ""),
                traceback=raw_error.get("traceback", ""),
            )
        elif raw_error and isinstance(raw_error, str):
            error = ExecutionError(value=raw_error)

        return cls(results=results, logs=logs, error=error)


@dataclass
class CodeContext:
    """Code execution context.

    Only context_id, language, and cwd are populated by the backend.
    """

    context_id: str
    language: str
    cwd: str


@dataclass
class CodeContextDeleteResponse:
    """Code context delete response"""

    message: str
    context_id: Optional[str] = None


@dataclass
class Template:
    """Runtime template.

    Maps to backend TemplateResponse. Identical fields to TemplateInfo
    in types/templates.py — kept as a convenience alias for runtime-centric code.
    """

    id: str
    name: str
    description: str
    vcpu_count: int
    memory_mb: int
    disk_size_mb: int
    visibility: str
    created_at: str
    updated_at: str
    provider: Optional[str] = None
    region: Optional[str] = None


@dataclass
class TemplateList:
    """List of templates response"""

    templates: List[Template]
    limit: int
    offset: int


@dataclass
class RuntimeKillResponse:
    """Runtime kill response"""

    message: str
    runtime_id: Optional[str] = None


class Execution:
    """Unified result wrapper for code or command execution.

    Wraps either a CodeRunResponse or CommandRunResponse, providing a
    consistent interface regardless of execution type. Uses a cached type
    check for fast property access.
    """

    __slots__ = ("_response", "_is_command")

    def __init__(self, response: Union[CodeRunResponse, CommandRunResponse]):
        self._response = response
        self._is_command = isinstance(response, CommandRunResponse)

    @property
    def logs(self) -> Dict[str, List[str]]:
        """Get execution logs with stdout and stderr."""
        if not self._is_command:
            resp: CodeRunResponse = self._response
            return {
                "stdout": list(resp.logs.stdout),
                "stderr": list(resp.logs.stderr),
            }
        cmd_resp: CommandRunResponse = self._response
        result: Dict[str, List[str]] = {"stdout": [], "stderr": []}
        if cmd_resp.stdout:
            result["stdout"] = cmd_resp.stdout.split("\n")
        if cmd_resp.stderr:
            result["stderr"] = cmd_resp.stderr.split("\n")
        return result

    @property
    def stdout(self) -> str:
        """Get standard output as a string."""
        if self._is_command:
            return self._response.stdout or ""
        return self._response.stdout_text

    @property
    def stderr(self) -> str:
        """Get standard error as a string."""
        if self._is_command:
            return self._response.stderr or ""
        return self._response.stderr_text

    @property
    def text(self) -> str:
        """Get the primary text output."""
        if self._is_command:
            return self._response.stdout or ""
        return self._response.text

    @property
    def exit_code(self) -> int:
        """Get the exit code of the execution."""
        return self._response.exit_code if self._is_command else 0

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        if self._is_command:
            return self._response.success
        return self._response.error is None

    @property
    def error(self) -> Optional[Any]:
        """Get execution error if any."""
        return self._response.error

    @property
    def results(self) -> List[ExecutionResult]:
        """Get rich results (only for code execution)."""
        if self._is_command:
            return []
        return self._response.results

    @property
    def duration_ms(self) -> int:
        """Get execution duration in milliseconds (command execution only)."""
        if self._is_command:
            return self._response.duration_ms
        return 0

    def __repr__(self) -> str:
        kind = "command" if self._is_command else "code"
        return f"Execution(type={kind}, success={self.success})"
