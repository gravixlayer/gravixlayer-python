"""Type definitions for the Runtime API."""

import dataclasses
import inspect
import os
import re
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _validate_runtime_id(runtime_id: str) -> None:
    """Validate that a runtime ID is a well-formed UUID."""
    if not runtime_id or len(runtime_id) != 36 or _UUID_RE.match(runtime_id) is None:
        raise ValueError(f"Invalid runtime_id: expected UUID, got {runtime_id!r}")


def _validate_path(path: str) -> None:
    """Validate a filesystem path is non-empty, has no null bytes, and no traversal."""
    if not path:
        raise ValueError("Path must not be empty")
    if "\x00" in path:
        raise ValueError("Path must not contain null bytes")
    # After normpath, ``/a/../b`` is ``/b`` (allowed). A remaining ``..`` component
    # is traversal. Check both separators so Windows paths still fail on POSIX
    # ``/`` splits and POSIX paths with literal backslashes are not rewritten.
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

    Fields match the Gravix Layer runtime API response.
    """

    runtime_id: str
    status: str
    template: Optional[str] = None
    template_id: Optional[str] = None
    cloud: Optional[str] = None
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

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Runtime":
        """Create a Runtime from an API response dict, ignoring unknown fields."""
        filtered = {k: data[k] for k in _RUNTIME_KNOWN_FIELDS if k in data}
        if filtered.get("cloud") is None:
            provider = data.get("provider")
            if provider is not None:
                filtered["cloud"] = provider
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
        template: str = "base-small",
        cloud: str = "aws",
        region: str = "us-east-1",
        timeout: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        internet_access: Optional[bool] = None,
        env_vars: Optional[Dict[str, str]] = None,
        providers: Optional[List[str]] = None,
        network_policy_ids: Optional[List[str]] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Optional[Any] = None,
        snapshot: Optional[str] = None,
    ) -> "Runtime":
        """
        Create a new runtime instance with simplified interface.

        Args:
            template: Template to use (default: "base-small")
            cloud: Cloud (aws/azure/gcp; default: "aws")
            region: Region to deploy in (default: "us-east-1")
            timeout: Timeout in seconds (default: None = no timeout). Pass 0 to explicitly disable timeout.
            metadata: Optional metadata tags
            internet_access: Whether to allow internet access (default: None = server default)
            env_vars: Environment variables for the runtime
            providers: Optional secret provider IDs to attach at creation
            network_policy_ids: Optional network policy IDs to attach at creation
                (the system default empty allowlist is always attached; attach an
                ``allow_all`` or allowlist policy for guest egress such as PyPI)
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
            env_vars=env_vars,
            providers=providers,
            network_policy_ids=network_policy_ids,
            snapshot=snapshot,
        )

        instance = cls(
            runtime_id=runtime_response.runtime_id,
            status=runtime_response.status,
            template=runtime_response.template,
            template_id=runtime_response.template_id,
            cloud=runtime_response.cloud,
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

    @classmethod
    def connect(
        cls,
        runtime_id: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> "Runtime":
        """Connect to an existing running runtime by ID.

        Use this to reconnect to a runtime that was created earlier — e.g.
        after saving the ``runtime_id`` and coming back later, or to share a
        runtime across multiple processes.

        Args:
            runtime_id: The ID of the running runtime to reconnect to.
            api_key: API key (uses GRAVIXLAYER_API_KEY env var if not provided).
            base_url: Base URL (uses GRAVIXLAYER_BASE_URL env var if not provided).
            client: Existing GravixLayer client to reuse.

        Returns:
            Runtime instance with all convenience methods available.

        Raises:
            ValueError: If runtime_id is not a valid UUID.
            GravixLayerNotFoundError: If the runtime does not exist.
            RuntimeError: If the runtime is not in a usable state.

        Example::

            # In one process — save the ID
            sandbox = Runtime.create()  # defaults to template="base-small"
            saved_id = sandbox.runtime_id

            # Later, in the same or a different process — reconnect
            sandbox = Runtime.connect(saved_id)
            result = sandbox.run_cmd("whoami")
        """
        _validate_runtime_id(runtime_id)

        if client is None:
            from ..client import GravixLayer
            client = GravixLayer(api_key=api_key, base_url=base_url)
            owns_client = True
        else:
            owns_client = False

        runtime_response = client.runtime.get(runtime_id)

        instance = cls(
            runtime_id=runtime_response.runtime_id,
            status=runtime_response.status,
            template=runtime_response.template,
            template_id=runtime_response.template_id,
            cloud=runtime_response.cloud,
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
        instance._owns_client = owns_client
        return instance

    def run_code(
        self,
        code: str,
        language: str = "python",
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
        on_result: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Any], None]] = None,
    ) -> "Execution":
        """Execute code in the runtime.

        Args:
            code: Source to execute.
            language: Language of the source (default: "python").
            on_stdout: Optional callback invoked with each incremental stdout chunk.
                Providing any callback streams the execution over SSE.
            on_stderr: Optional callback invoked with each incremental stderr chunk.
            on_result: Optional callback invoked with each ``ExecutionResult``.
            on_error: Optional callback invoked with the ``ExecutionError`` on failure.
        """
        self._require_alive()
        response = self._client.runtime.run_code(
            self.runtime_id,
            code=code,
            language=language,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            on_result=on_result,
            on_error=on_error,
        )
        return Execution(response)

    def run_cmd(
        self,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
    ) -> "Execution":
        """Execute a shell command in the runtime.

        Args:
            command: The command string to execute.
            args: Additional arguments to append.
            working_dir: Working directory for the command.
            timeout: Maximum execution time in seconds.
            on_stdout: Optional callback invoked with each stdout chunk. When any
                callback is provided the command is streamed over SSE.
            on_stderr: Optional callback invoked with each stderr chunk.
            on_exit: Optional callback invoked with the final exit code.
        """
        self._require_alive()
        response = self._client.runtime.run_cmd(
            self.runtime_id,
            command=command,
            args=args or [],
            working_dir=working_dir,
            timeout=timeout,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            on_exit=on_exit,
        )
        return Execution(response)

    def run_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
    ) -> "Execution":
        """Execute a shell command in the runtime.

        Alias for :meth:`run_cmd`.
        """
        return self.run_cmd(
            command=command,
            args=args,
            working_dir=working_dir,
            timeout=timeout,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            on_exit=on_exit,
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

    @property
    def git(self) -> "RuntimeGit":
        """Git operations in the runtime (clone, status, pull, push, etc.)."""
        self._require_alive()
        return RuntimeGit(self._client, self.runtime_id)

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

    @property
    def file(self) -> "RuntimeFileBound":
        """Filesystem API for this runtime (same as ``client.runtime.file``, without ``runtime_id``)."""
        return RuntimeFileBound(self)

    @property
    def pty(self) -> "RuntimePtyBound":
        """PTY session API for this runtime (same as ``client.runtime.pty``, without ``runtime_id``)."""
        return RuntimePtyBound(self)

    def service(
        self,
        port: int,
        *,
        expires_in_seconds: int = 3600,
        is_public: bool = False,
        rotate_token: bool = False,
    ) -> Any:
        """Open a web service for a guest HTTP port on ``*.service.gravixlayer.ai``."""
        self._require_alive()
        return self._client.runtime.service(
            self.runtime_id,
            port,
            expires_in_seconds=expires_in_seconds,
            is_public=is_public,
            rotate_token=rotate_token,
        )


class RuntimeFileBound:
    """Bound view of :attr:`Runtime.file` — mirrors ``client.runtime.file.*`` signatures minus ``runtime_id``."""

    __slots__ = ("_runtime",)

    def __init__(self, runtime: "Runtime") -> None:
        object.__setattr__(self, "_runtime", runtime)

    def _rc(self) -> tuple[str, Any]:
        r = object.__getattribute__(self, "_runtime")
        r._require_alive()
        return r.runtime_id, r._client

    def read(self, path: str) -> "FileReadResponse":
        rid, client = self._rc()
        return client.runtime.file.read(rid, path)

    def write(self, path: str, content: str) -> "FileWriteResponse":
        rid, client = self._rc()
        return client.runtime.file.write(rid, path, content)

    def delete(self, path: str) -> "FileDeleteResponse":
        rid, client = self._rc()
        return client.runtime.file.delete(rid, path)

    def list(self, path: str = "/workspace") -> "FileListResponse":
        rid, client = self._rc()
        return client.runtime.file.list(rid, path)

    def upload(
        self,
        path: str,
        data: Union[str, bytes, Any],
        user: Optional[str] = None,
        mode: Optional[int] = None,
    ) -> "WriteResult":
        rid, client = self._rc()
        return client.runtime.file.upload(rid, path, data, user=user, mode=mode)

    def write_many(
        self,
        entries: List["WriteEntry"],
        user: Optional[str] = None,
        concurrency: int = 8,
    ) -> "WriteFilesResponse":
        rid, client = self._rc()
        return client.runtime.file.write_many(rid, entries, user=user, concurrency=concurrency)

    def create_directory(
        self,
        path: str,
        *,
        recursive: bool = True,
        mode: Optional[str] = None,
    ) -> "DirectoryCreateResponse":
        rid, client = self._rc()
        return client.runtime.file.create_directory(rid, path, recursive=recursive, mode=mode)

    def get_info(self, path: str) -> "FileGetInfoResponse":
        rid, client = self._rc()
        return client.runtime.file.get_info(rid, path)

    def set_permissions(self, path: str, mode: str) -> "SetPermissionsResponse":
        rid, client = self._rc()
        return client.runtime.file.set_permissions(rid, path, mode)

    def move(self, source: str, destination: str, overwrite: bool = False) -> "FileMoveResponse":
        rid, client = self._rc()
        return client.runtime.file.move(rid, source, destination, overwrite=overwrite)

    def copy(
        self,
        source: str,
        destination: str,
        recursive: bool = False,
        overwrite: bool = False,
    ) -> "FileCopyResponse":
        rid, client = self._rc()
        return client.runtime.file.copy(
            rid, source, destination, recursive=recursive, overwrite=overwrite
        )

    def chown(
        self,
        path: str,
        user: Optional[str] = None,
        group: Optional[str] = None,
        recursive: bool = False,
    ) -> "ChangeOwnerResponse":
        rid, client = self._rc()
        return client.runtime.file.chown(rid, path, user=user, group=group, recursive=recursive)

    def watch(
        self,
        path: str,
        recursive: bool = False,
        on_event: Optional[Callable[["WatchEvent"], None]] = None,
    ) -> Any:
        """Watch a directory for filesystem changes. Returns an iterator of ``WatchEvent``."""
        rid, client = self._rc()
        return client.runtime.file.watch(rid, path, recursive=recursive, on_event=on_event)

    def find(
        self,
        path: str,
        pattern: Optional[str] = None,
        glob: Optional[str] = None,
        *,
        regex: bool = False,
        case_sensitive: bool = False,
        include_hidden: bool = False,
        max_results: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> "FileFindResponse":
        rid, client = self._rc()
        return client.runtime.file.find(
            rid,
            path,
            pattern=pattern,
            glob=glob,
            regex=regex,
            case_sensitive=case_sensitive,
            include_hidden=include_hidden,
            max_results=max_results,
            max_depth=max_depth,
        )

    def replace(
        self,
        path: str,
        pattern: str,
        replacement: str,
        glob: Optional[str] = None,
        *,
        regex: bool = False,
        case_sensitive: bool = False,
        include_hidden: bool = False,
        max_depth: Optional[int] = None,
        dry_run: bool = False,
    ) -> "FileReplaceResponse":
        rid, client = self._rc()
        return client.runtime.file.replace(
            rid,
            path,
            pattern,
            replacement,
            glob=glob,
            regex=regex,
            case_sensitive=case_sensitive,
            include_hidden=include_hidden,
            max_depth=max_depth,
            dry_run=dry_run,
        )

    def upload_file(self, file: BinaryIO, path: Optional[str] = None) -> "FileUploadResponse":
        rid, client = self._rc()
        return client.runtime.file.upload_file(rid, file, path=path)

    def download_file(self, path: str) -> bytes:
        rid, client = self._rc()
        return client.runtime.file.download_file(rid, path)


class RuntimePtyBound:
    """Bound view of :attr:`Runtime.pty` - mirrors ``client.runtime.pty.*`` minus ``runtime_id``."""

    __slots__ = ("_runtime",)

    def __init__(self, runtime: "Runtime") -> None:
        object.__setattr__(self, "_runtime", runtime)

    def _rc(self) -> tuple[str, Any]:
        r = object.__getattribute__(self, "_runtime")
        r._require_alive()
        return r.runtime_id, r._client

    def create(
        self,
        shell: Optional[str] = None,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
    ) -> "PtySession":
        rid, client = self._rc()
        return client.runtime.pty.create(
            rid,
            shell=shell,
            args=args,
            working_dir=working_dir,
            environment=environment,
            cols=cols,
            rows=rows,
        )

    def list(self) -> List["PtySession"]:
        rid, client = self._rc()
        return client.runtime.pty.list(rid)

    def get(self, session_id: str) -> "PtySession":
        rid, client = self._rc()
        return client.runtime.pty.get(rid, session_id)

    def send_input(self, session_id: str, data: Any) -> "PtyInputResponse":
        rid, client = self._rc()
        return client.runtime.pty.send_input(rid, session_id, data)

    def resize(self, session_id: str, cols: int, rows: int) -> bool:
        rid, client = self._rc()
        return client.runtime.pty.resize(rid, session_id, cols, rows)

    def send_signal(self, session_id: str, signal: str) -> bool:
        rid, client = self._rc()
        return client.runtime.pty.send_signal(rid, session_id, signal)

    def stream(
        self,
        session_id: str,
        on_data: Optional[Callable[[bytes], None]] = None,
        on_exit: Optional[Callable[[int, str], None]] = None,
    ) -> Any:
        """Stream the session's output. Returns an iterator of event dicts."""
        rid, client = self._rc()
        return client.runtime.pty.stream(rid, session_id, on_data=on_data, on_exit=on_exit)

    def kill(self, session_id: str) -> bool:
        rid, client = self._rc()
        return client.runtime.pty.kill(rid, session_id)

    def handle(self, session_id: str) -> Any:
        """Return a connection-managing PTY handle for ``session_id``.

        The handle adds ``connect``, ``wait_for_connection``, ``wait_for_completion``,
        ``is_connected`` and ``disconnect`` on top of the stateless calls above.
        """
        rid, client = self._rc()
        return client.runtime.pty.handle(rid, session_id)


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
class RuntimeWebService:
    """Public HTTPS web service for a guest HTTP port (*.service.gravixlayer.ai)."""

    runtime_id: str
    port: int
    url: str
    web_url: str
    browser_url: str
    service_url: str
    expires_at: str
    is_public: bool = False
    token: Optional[str] = None
    subdomain: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "RuntimeWebService":
        url = data.get("web_url") or data.get("url") or ""
        service_url = data.get("service_url") or (url if url.endswith("/") else url + "/")
        return cls(
            runtime_id=str(data.get("runtime_id") or ""),
            port=int(data.get("port") or 0),
            url=url,
            web_url=url,
            browser_url=str(data.get("browser_url") or url),
            service_url=service_url,
            expires_at=str(data.get("expires_at") or ""),
            is_public=bool(data.get("is_public")),
            token=data.get("token"),
            subdomain=data.get("subdomain"),
        )


# ---------------------------------------------------------------------------
# SSH types (enable / status API responses)
# ---------------------------------------------------------------------------

@dataclass
class SSHInfo:
    """SSH connection info returned when SSH is enabled."""

    runtime_id: str
    enabled: bool
    port: int
    username: str
    connect_cmd: str
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

    Maps API FileInfo fields: name, size, mode, mod_time, is_dir.

    ``size`` is the file length in **bytes**. ``modified_at`` is last modification time
    as an ISO 8601 string (typically UTC, suffix ``Z``).
    """

    name: str
    size: int
    is_dir: bool
    modified_at: str = ""
    mode: Optional[str] = None
    path: Optional[str] = None
    permissions: Optional[str] = None


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
    success: Optional[bool] = None


@dataclass
class FileGetInfoResponse:
    """Response from ``runtime.file.get_info`` (native stat)."""

    exists: bool
    info: Optional["FileInfo"] = None


@dataclass
class SetPermissionsResponse:
    """Response from ``runtime.file.set_permissions``."""

    message: str
    success: bool = True


@dataclass
class FileMoveResponse:
    """Response from ``runtime.file.move`` (native ``rename``/``renameat2``)."""

    success: bool
    source: str
    destination: str
    entry: Optional["FileInfo"] = None


@dataclass
class FileCopyResponse:
    """Response from ``runtime.file.copy``."""

    success: bool
    source: str
    destination: str
    entry: Optional["FileInfo"] = None


@dataclass
class ChangeOwnerResponse:
    """Response from ``runtime.file.chown``."""

    success: bool
    path: str
    message: str = ""


@dataclass
class WatchEvent:
    """A single filesystem notification from ``runtime.file.watch``.

    ``type`` is one of ``start``, ``create``, ``write``, ``remove``, ``rename`` or
    ``chmod``. ``new_path`` is only populated for ``rename``. The first event of a
    stream is always ``start``, which confirms the watch is armed.
    """

    type: str
    name: str = ""
    path: str = ""
    new_path: Optional[str] = None
    watcher_id: Optional[str] = None
    timestamp: Optional[int] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "WatchEvent":
        return cls(
            type=str(data.get("type") or ""),
            name=str(data.get("name") or ""),
            path=str(data.get("path") or ""),
            new_path=data.get("new_path") or None,
            watcher_id=data.get("watcher_id") or None,
            timestamp=data.get("timestamp"),
        )


@dataclass
class FileSearchMatch:
    """A single hit from ``runtime.file.find``.

    For a pure name search (no ``pattern`` supplied) ``line`` is ``0`` and
    ``content`` is empty: the match is the file itself. For a content search
    ``line`` and ``column`` are 1-based and ``content`` is the matching line,
    truncated to a bounded length.
    """

    path: str
    line: int = 0
    column: int = 0
    content: str = ""

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "FileSearchMatch":
        return cls(
            path=str(data.get("path") or ""),
            line=int(data.get("line") or 0),
            column=int(data.get("column") or 0),
            content=str(data.get("content") or ""),
        )


@dataclass
class FileFindResponse:
    """Response from ``runtime.file.find``.

    ``truncated`` is ``True`` when the result limit was reached before the walk
    finished, meaning more matches exist than were returned.
    """

    success: bool
    matches: List[FileSearchMatch] = field(default_factory=list)
    truncated: bool = False
    files_scanned: int = 0

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "FileFindResponse":
        raw = data.get("matches") or []
        return cls(
            success=bool(data.get("success", True)),
            matches=[FileSearchMatch.from_api(m) for m in raw if isinstance(m, dict)],
            truncated=bool(data.get("truncated", False)),
            files_scanned=int(data.get("files_scanned") or 0),
        )

    def __len__(self) -> int:
        return len(self.matches)

    def __iter__(self):
        return iter(self.matches)


@dataclass
class FileReplaceEntry:
    """Per-file replacement count from ``runtime.file.replace``."""

    path: str
    replacements: int = 0

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "FileReplaceEntry":
        return cls(
            path=str(data.get("path") or ""),
            replacements=int(data.get("replacements") or 0),
        )


@dataclass
class FileReplaceResponse:
    """Response from ``runtime.file.replace``.

    When ``dry_run`` is set the counts describe what *would* have changed and no
    file on the guest was modified.
    """

    success: bool
    files: List[FileReplaceEntry] = field(default_factory=list)
    total_replacements: int = 0
    files_scanned: int = 0
    dry_run: bool = False

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "FileReplaceResponse":
        raw = data.get("files") or []
        return cls(
            success=bool(data.get("success", True)),
            files=[FileReplaceEntry.from_api(f) for f in raw if isinstance(f, dict)],
            total_replacements=int(data.get("total_replacements") or 0),
            files_scanned=int(data.get("files_scanned") or 0),
            dry_run=bool(data.get("dry_run", False)),
        )

    def __len__(self) -> int:
        return len(self.files)

    def __iter__(self):
        return iter(self.files)


@dataclass
class GitOperationResult:
    """Result of a git operation (stdout/stderr from ``git`` inside the runtime)."""

    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "GitOperationResult":
        return cls(
            success=bool(data.get("success")),
            exit_code=int(data.get("exit_code", 0)),
            stdout=str(data.get("stdout") or ""),
            stderr=str(data.get("stderr") or ""),
            error=str(data.get("error") or ""),
        )


class RuntimeGit:
    """Git operations for a bound :class:`Runtime` (uses ``/v1/agents/runtime/:id/git/*``).

    Only the synchronous :class:`gravixlayer.GravixLayer` client is supported here.
    With :class:`gravixlayer.AsyncGravixLayer`, use ``await client.runtime.git.clone(...)`` (etc.) instead.
    """

    def __init__(self, client: Any, runtime_id: str):
        self._client = client
        self._runtime_id = runtime_id

    @staticmethod
    def _sync_git_result(result: Any) -> GitOperationResult:
        if inspect.isawaitable(result):
            raise TypeError(
                "runtime.git only works with the synchronous GravixLayer client. "
                "With AsyncGravixLayer, use await client.runtime.git.clone(...) and related methods."
            )
        return result

    def clone(
        self,
        url: str,
        path: str,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        auth_token: Optional[str] = None,
    ) -> GitOperationResult:
        """Clone into ``path`` on the runtime.

        ``url`` must be ``http://``, ``https://``, ``ssh://``, ``git://``, or SCP-style
        (e.g. ``git@github.com:org/repo.git``). ``file://`` is not allowed.

        ``auth_token`` authenticates this clone only and is not stored in the
        checkout, so ``pull``, ``fetch``, and ``push`` each take their own token.
        """
        return self._sync_git_result(
            self._client.runtime.git.clone(
                self._runtime_id,
                url=url,
                path=path,
                branch=branch,
                depth=depth,
                auth_token=auth_token,
            )
        )

    def status(self, repository_path: str) -> GitOperationResult:
        return self._sync_git_result(
            self._client.runtime.git.status(self._runtime_id, repository_path=repository_path)
        )

    def branch_list(
        self, repository_path: str, scope: Optional[str] = None
    ) -> GitOperationResult:
        return self._sync_git_result(
            self._client.runtime.git.branch_list(
                self._runtime_id, repository_path, scope=scope
            )
        )

    def checkout(self, repository_path: str, ref_name: str) -> GitOperationResult:
        return self._sync_git_result(
            self._client.runtime.git.checkout(
                self._runtime_id, repository_path=repository_path, ref_name=ref_name
            )
        )

    def pull(
        self,
        repository_path: str,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> GitOperationResult:
        """Pull from a remote. Pass ``auth_token`` for a private HTTPS remote."""
        return self._sync_git_result(
            self._client.runtime.git.pull(
                self._runtime_id,
                repository_path=repository_path,
                remote=remote,
                branch=branch,
                auth_token=auth_token,
            )
        )

    def push(
        self,
        repository_path: str,
        remote: Optional[str] = None,
        refspec: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> GitOperationResult:
        """Push to a remote.

        ``auth_token`` is the usual credential for a forge and takes precedence
        when ``username``/``password`` are also given.
        """
        return self._sync_git_result(
            self._client.runtime.git.push(
                self._runtime_id,
                repository_path=repository_path,
                remote=remote,
                refspec=refspec,
                username=username,
                password=password,
                auth_token=auth_token,
            )
        )

    def fetch(
        self,
        repository_path: str,
        remote: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> GitOperationResult:
        """Fetch from a remote. Pass ``auth_token`` for a private HTTPS remote."""
        return self._sync_git_result(
            self._client.runtime.git.fetch(
                self._runtime_id, repository_path=repository_path, remote=remote, auth_token=auth_token
            )
        )

    def add(self, repository_path: str, paths: Optional[List[str]] = None) -> GitOperationResult:
        return self._sync_git_result(
            self._client.runtime.git.add(
                self._runtime_id, repository_path=repository_path, paths=paths
            )
        )

    def commit(
        self,
        repository_path: str,
        message: str,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
        allow_empty: Optional[bool] = None,
    ) -> GitOperationResult:
        return self._sync_git_result(
            self._client.runtime.git.commit(
                self._runtime_id,
                repository_path=repository_path,
                message=message,
                author_name=author_name,
                author_email=author_email,
                allow_empty=allow_empty,
            )
        )

    def create_branch(
        self,
        repository_path: str,
        branch_name: str,
        start_point: Optional[str] = None,
    ) -> GitOperationResult:
        return self._sync_git_result(
            self._client.runtime.git.create_branch(
                self._runtime_id,
                repository_path=repository_path,
                branch_name=branch_name,
                start_point=start_point,
            )
        )

    def delete_branch(
        self,
        repository_path: str,
        branch_name: str,
        force: Optional[bool] = None,
    ) -> GitOperationResult:
        return self._sync_git_result(
            self._client.runtime.git.delete_branch(
                self._runtime_id,
                repository_path=repository_path,
                branch_name=branch_name,
                force=force,
            )
        )


@dataclass
class FileUploadResponse:
    """File upload response"""

    message: str
    path: Optional[str] = None
    size: Optional[int] = None


@dataclass
class WriteEntry:
    """Entry for a batch file write.

    Args:
        path: Destination path inside the runtime (absolute, or relative to /workspace/)
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
    """Response from multipart ``upload`` / ``write_many`` operations."""

    files: List[WriteResult]
    partial_failure: bool = False


@dataclass
class CommandRunResponse:
    """Command execution response.

    Maps the Gravix Layer command-run API response.
    """

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    success: bool
    error: Optional[str] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "CommandRunResponse":
        """Build from an API dict, ignoring unknown fields."""
        return cls(
            stdout=data["stdout"],
            stderr=data["stderr"],
            exit_code=data["exit_code"],
            duration_ms=data["duration_ms"],
            success=data["success"],
            error=data.get("error"),
        )


# ---------------------------------------------------------------------------
# Code execution types (Execution / Result / Logs API shapes)
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """A single result from code execution.

    Maps the API Result payload: text, html, json, png, jpeg, svg,
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

    Maps the API ExecutionError payload: name, value, traceback.
    """

    name: str = ""
    value: str = ""
    traceback: str = ""


@dataclass
class ExecutionLogs:
    """Stdout/stderr from code execution.

    Maps the API Logs payload.
    """

    stdout: List[str] = field(default_factory=list)
    stderr: List[str] = field(default_factory=list)


@dataclass
class CodeRunResponse:
    """Code execution response.

    Maps the API Execution payload. Provides convenience properties
    for common access patterns so users don't need to dig into nested dicts.
    """

    results: List[ExecutionResult] = field(default_factory=list)
    logs: ExecutionLogs = field(default_factory=ExecutionLogs)
    error: Optional[ExecutionError] = None

    @property
    def text(self) -> str:
        """The primary textual result.

        A cell reports its outputs in the order they were produced, so the last
        one carries the value the code evaluated to. Code that printed instead
        of returning a value falls back to its standard output.
        """
        for result in reversed(self.results):
            if result.text:
                return result.text
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
        """Parse an Execution JSON dict into a typed CodeRunResponse."""
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
    """Persistent execution context (Jupyter kernel session) in a runtime.

    ``context_id`` is returned from :meth:`~gravixlayer.resources.runtime.Runtimes.create_context`
    and passed to :meth:`~gravixlayer.resources.runtime.Runtimes.run_code` as ``context_id``.
    """

    context_id: str
    language: str
    cwd: str


@dataclass
class CodeContextDeleteResponse:
    """Response from deleting an execution context."""

    message: str
    context_id: Optional[str] = None


@dataclass
class Template:
    """Runtime template.

    Maps the template API response. Identical fields to TemplateInfo
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
    cloud: Optional[str] = None
    region: Optional[str] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Template":
        """Create a Template from an API response dict, ignoring unknown fields."""
        if data.get("cloud") is None and data.get("provider") is not None:
            data = {**data, "cloud": data["provider"]}
        known = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


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


@dataclass
class PtySession:
    """A programmatic PTY session running inside a runtime.

    The session is owned by the execution plane, not by the connection that created
    it, so it survives client disconnects and can be re-attached to at any time.
    ``status`` is ``running`` or ``exited``; ``exit_code`` is only meaningful once the
    session has exited.
    """

    session_id: str
    runtime_id: str
    pid: int = 0
    shell: str = ""
    args: List[str] = field(default_factory=list)
    working_dir: str = ""
    cols: int = 0
    rows: int = 0
    status: str = ""
    exit_code: int = 0
    created_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "PtySession":
        return cls(
            session_id=str(data.get("session_id") or ""),
            runtime_id=str(data.get("runtime_id") or ""),
            pid=int(data.get("pid") or 0),
            shell=str(data.get("shell") or ""),
            args=list(data.get("args") or []),
            working_dir=str(data.get("working_dir") or ""),
            cols=int(data.get("cols") or 0),
            rows=int(data.get("rows") or 0),
            status=str(data.get("status") or ""),
            exit_code=int(data.get("exit_code") or 0),
            created_at=data.get("created_at"),
        )


@dataclass
class PtyInputResponse:
    """Response from ``runtime.pty.send_input``."""

    success: bool
    bytes_written: int = 0


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


# ---------------------------------------------------------------------------
# Module-level constants (computed once at import time, shared by resources)
# ---------------------------------------------------------------------------

_RUNTIME_KNOWN_FIELDS: frozenset = frozenset(
    f.name for f in dataclasses.fields(Runtime) if not f.name.startswith("_")
)

_METRICS_FIELDS: frozenset = frozenset(
    f.name for f in dataclasses.fields(RuntimeMetrics)
)

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
