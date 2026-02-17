"""
Type definitions for Template Build Pipeline API.

Provides dataclasses and enums for template creation, build orchestration,
and status tracking. Aligned with the backend template build API contract.
"""

import base64
import os
import shlex
import warnings
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Build step types (aligned with backend template_build.go)
# ---------------------------------------------------------------------------

class BuildStepType(str, Enum):
    """Valid build step types for template construction."""
    RUN = "run"
    PIP_INSTALL = "pip_install"
    NPM_INSTALL = "npm_install"
    APT_INSTALL = "apt_install"
    BUN_INSTALL = "bun_install"
    COPY_FILE = "copy_file"
    GIT_CLONE = "git_clone"
    MKDIR = "mkdir"


@dataclass
class BuildStep:
    """A single build step in the template build pipeline.

    Args:
        type: The step type (see BuildStepType enum)
        args: Positional arguments for the step
        content: File content bytes (used only for copy_file steps)
        options: Key-value options (e.g. branch, depth, auth_token, mode, user)
    """
    type: str
    args: List[str] = field(default_factory=list)
    content: Optional[bytes] = None
    options: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to API request format."""
        result: Dict[str, Any] = {"type": self.type, "args": self.args}
        if self.content is not None:
            result["content"] = base64.b64encode(self.content).decode("ascii")
        if self.options:
            result["options"] = self.options
        return result


# ---------------------------------------------------------------------------
# Build status and phases
# ---------------------------------------------------------------------------

class TemplateBuildStatusEnum(str, Enum):
    """Build lifecycle status values."""
    PENDING = "pending"
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TemplateBuildPhase(str, Enum):
    """User-facing build phases.

    The server may return phases not listed here;
    callers should handle unknown phase strings gracefully.
    """
    INITIALIZING = "initializing"
    PREPARING = "preparing"
    BUILDING = "building"
    FINALIZING = "finalizing"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# API response types
# ---------------------------------------------------------------------------

@dataclass
class TemplateBuildResponse:
    """Response from POST /v1/agents/templates/build (202 Accepted)."""
    build_id: str
    template_id: str
    status: str
    message: str


@dataclass
class TemplateBuildStatus:
    """Response from GET /v1/agents/templates/builds/:build_id/status."""
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
        """True when the build has reached a final state."""
        return self.status in (
            TemplateBuildStatusEnum.COMPLETED.value,
            TemplateBuildStatusEnum.FAILED.value,
        )

    @property
    def is_success(self) -> bool:
        """True when the build completed without errors."""
        return self.status == TemplateBuildStatusEnum.COMPLETED.value


@dataclass
class TemplateInfo:
    """Full template metadata returned by GET /v1/agents/templates/:id."""
    id: str
    name: str
    description: str
    vcpu_count: int
    memory_mb: int
    disk_size_mb: int
    visibility: str
    created_at: str
    updated_at: str
    base_image: Optional[str] = None
    environment: Optional[Dict[str, str]] = None
    tags: Optional[Dict[str, str]] = None


@dataclass
class TemplateSnapshot:
    """Template with snapshot info from GET /v1/agents/templates/:id/snapshot."""
    template_id: str
    name: str
    description: str
    has_snapshot: bool
    vcpu_count: int
    memory_mb: int
    created_at: str
    envd_version: Optional[str] = None
    snapshot_size_bytes: Optional[int] = None


@dataclass
class TemplateListResponse:
    """Response from GET /v1/agents/templates."""
    templates: List[TemplateInfo]
    limit: int
    offset: int


@dataclass
class TemplateDeleteResponse:
    """Result of DELETE /v1/agents/templates/:id (HTTP 204 No Content)."""
    template_id: str
    deleted: bool = True


# ---------------------------------------------------------------------------
# Build log callback types
# ---------------------------------------------------------------------------

@dataclass
class BuildLogEntry:
    """A single log entry from the build process."""
    timestamp: Optional[str] = None
    level: str = "info"
    message: str = ""


BuildLogCallback = Callable[[BuildLogEntry], None]
"""Callback type for receiving build log entries during polling."""


# ---------------------------------------------------------------------------
# Template builder (fluent API)
# ---------------------------------------------------------------------------

class TemplateBuilder:
    """Fluent builder for constructing template build configurations.

    Accumulates build steps, environment variables, and configuration
    that get serialized into a single API request. All methods return
    ``self`` for chaining.

    Example::

        template = (
            TemplateBuilder("my-ml-template")
            .from_image("python:3.11-slim")
            .vcpu(2)
            .memory(512)
            .apt_install("git", "curl")
            .pip_install("numpy", "pandas")
            .copy_file("./src/main.py", "/app/main.py")
            .start_cmd("python /app/main.py")
            .ready_cmd(TemplateBuilder.wait_for_port(8080))
        )
    """

    def __init__(self, name: str, description: str = ""):
        if not name:
            raise ValueError("Template name is required")
        self._name: str = name
        self._description: str = description
        self._template_id: Optional[str] = None
        self._docker_image: Optional[str] = None
        self._dockerfile: Optional[str] = None
        self._vcpu_count: int = 2
        self._memory_mb: int = 512
        self._disk_mb: int = 4096
        self._start_cmd: Optional[str] = None
        self._ready_cmd: Optional[str] = None
        self._ready_timeout_secs: int = 60
        self._environment: Dict[str, str] = {}
        self._build_steps: List[BuildStep] = []
        self._tags: Dict[str, str] = {}

    # -- Base image selection -----------------------------------------------

    def from_image(self, image: str) -> "TemplateBuilder":
        """Set the base Docker image.

        Works exactly like ``FROM`` in a Dockerfile.  Pass the full image
        reference including the tag.

        Examples::

            builder.from_image("python:3.11-slim")
            builder.from_image("node:20-slim")
            builder.from_image("ubuntu:22.04")
            builder.from_image("nvidia/cuda:12.2.0-base-ubuntu22.04")
        """
        if self._dockerfile:
            raise ValueError("Cannot set docker_image when dockerfile is already set")
        self._docker_image = image
        return self

    def dockerfile(self, content: str) -> "TemplateBuilder":
        """Build the base image from raw Dockerfile content.

        When using this method you do NOT need ``pip_install`` or
        ``apt_install`` build steps -- handle everything inside the
        Dockerfile.  You still need ``start_cmd`` and ``ready_cmd`` so
        the build pipeline knows how to launch and verify the app.

        Example::

            builder.dockerfile(open("Dockerfile").read())
        """
        if self._docker_image:
            raise ValueError("Cannot set dockerfile when docker_image is already set")
        self._dockerfile = content
        return self

    # -- Resource configuration ---------------------------------------------

    def vcpu(self, count: int) -> "TemplateBuilder":
        """Set the number of vCPUs (default: 2)."""
        if count < 1:
            raise ValueError("vcpu_count must be >= 1")
        self._vcpu_count = count
        return self

    def memory(self, mb: int) -> "TemplateBuilder":
        """Set memory in MB (default: 512)."""
        if mb < 1:
            raise ValueError("memory_mb must be >= 1")
        self._memory_mb = mb
        return self

    def disk(self, mb: int) -> "TemplateBuilder":
        """Set disk size in MB (default: 4096)."""
        if mb < 1:
            raise ValueError("disk_mb must be >= 1")
        self._disk_mb = mb
        return self

    def template_id(self, tid: str) -> "TemplateBuilder":
        """Set a custom template ID (auto-generated by default)."""
        self._template_id = tid
        return self

    # -- Startup and readiness ----------------------------------------------

    def start_cmd(self, cmd: str) -> "TemplateBuilder":
        """Set the command to run after VM starts (captured in snapshot)."""
        self._start_cmd = cmd
        return self

    def ready_cmd(self, cmd: str, timeout_secs: int = 60) -> "TemplateBuilder":
        """Set the readiness check command that must exit 0.

        The build process polls this command until success or timeout.
        """
        self._ready_cmd = cmd
        self._ready_timeout_secs = timeout_secs
        return self

    # -- Environment and tags -----------------------------------------------

    def envs(self, envs: Dict[str, str]) -> "TemplateBuilder":
        """Set multiple environment variables (persisted to /etc/profile.d/)."""
        self._environment.update(envs)
        return self

    def env(self, key: str, value: str) -> "TemplateBuilder":
        """Set a single environment variable."""
        self._environment[key] = value
        return self

    def tags(self, tags: Dict[str, str]) -> "TemplateBuilder":
        """Set metadata tags."""
        self._tags.update(tags)
        return self

    # -- Build steps (fluent) -----------------------------------------------

    def run(self, command: str) -> "TemplateBuilder":
        """Execute a shell command as root."""
        self._build_steps.append(BuildStep(type="run", args=[command]))
        return self

    def pip_install(self, *packages: str) -> "TemplateBuilder":
        """Install Python packages via pip."""
        if not packages:
            raise ValueError("At least one package name is required")
        self._build_steps.append(BuildStep(type="pip_install", args=list(packages)))
        return self

    def npm_install(self, *packages: str) -> "TemplateBuilder":
        """Install Node.js packages via npm (global)."""
        if not packages:
            raise ValueError("At least one package name is required")
        self._build_steps.append(BuildStep(type="npm_install", args=list(packages)))
        return self

    def apt_install(self, *packages: str) -> "TemplateBuilder":
        """Install system packages via apt-get."""
        if not packages:
            raise ValueError("At least one package name is required")
        self._build_steps.append(BuildStep(type="apt_install", args=list(packages)))
        return self

    def bun_install(self, *packages: str) -> "TemplateBuilder":
        """Install Bun packages (global)."""
        if not packages:
            raise ValueError("At least one package name is required")
        self._build_steps.append(BuildStep(type="bun_install", args=list(packages)))
        return self

    def copy_file(
        self,
        src: Union[str, bytes, Path],
        dest: str,
        mode: Optional[str] = None,
        user: Optional[str] = None,
    ) -> "TemplateBuilder":
        """Copy a file into the template VM.

        The SDK automatically detects whether *src* is a local file path
        or inline content:

        - **Local file** — if *src* points to an existing file on disk,
          its contents are read and uploaded.
        - **Inline string** — if *src* is a string that is not a file path,
          it is treated as file content and encoded as UTF-8.
        - **Raw bytes** — if *src* is ``bytes``, it is used as-is.

        Args:
            src:  Local file path, inline string content, or raw bytes.
            dest: Destination path inside the VM (e.g. ``"/app/main.py"``).
            mode: Optional file permissions (e.g. ``"0755"``).
            user: Optional file owner.

        Examples::

            # Copy a local file
            builder.copy_file("./src/main.py", "/app/main.py")

            # Copy inline content
            builder.copy_file("print('hello')", "/app/hello.py")

            # Copy with permissions
            builder.copy_file("./run.sh", "/app/run.sh", mode="0755")
        """
        if isinstance(src, bytes):
            content = src
        elif isinstance(src, Path):
            with open(str(src), "rb") as f:
                content = f.read()
        elif isinstance(src, str) and os.path.isfile(src):
            with open(src, "rb") as f:
                content = f.read()
        elif isinstance(src, str):
            content = src.encode("utf-8")
        else:
            raise ValueError(
                f"src must be a file path, string content, or bytes, got {type(src)}"
            )

        options: Dict[str, str] = {}
        if mode:
            options["mode"] = mode
        if user:
            options["user"] = user
        self._build_steps.append(
            BuildStep(type="copy_file", args=[dest], content=content,
                      options=options if options else None)
        )
        return self

    def copy_dir(
        self,
        src: Union[str, Path],
        dest: str,
        mode: Optional[str] = None,
        user: Optional[str] = None,
    ) -> "TemplateBuilder":
        """Copy an entire local directory into the template VM.

        Recursively walks *src* and copies every file, preserving the
        relative directory structure under *dest*.

        Args:
            src:  Path to the local directory.
            dest: Destination root inside the VM (e.g. ``"/app/src"``).
            mode: Optional file permissions applied to every file.
            user: Optional file owner applied to every file.

        Raises:
            FileNotFoundError: If *src* does not exist.
            NotADirectoryError: If *src* is not a directory.

        Examples::

            builder.copy_dir("./src", "/app/src")
            builder.copy_dir(Path("my_project"), "/app")
        """
        src_abs = os.path.abspath(str(src))
        if not os.path.exists(src_abs):
            raise FileNotFoundError(f"Local directory not found: {src_abs}")
        if not os.path.isdir(src_abs):
            raise NotADirectoryError(f"Path is not a directory: {src_abs}")

        for dirpath, _dirnames, filenames in os.walk(src_abs):
            for filename in filenames:
                local_path = os.path.join(dirpath, filename)
                relative = os.path.relpath(local_path, src_abs)
                vm_path = os.path.join(dest, relative).replace("\\", "/")
                self.copy_file(local_path, vm_path, mode=mode, user=user)
        return self

    def git_clone(
        self,
        url: str,
        dest: Optional[str] = None,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        auth_token: Optional[str] = None,
    ) -> "TemplateBuilder":
        """Clone a git repository inside the VM.

        Args:
            url: Repository URL.
            dest: Destination directory (optional).
            branch: Branch to clone (optional).
            depth: Clone depth for shallow clone (optional).
            auth_token: HTTPS auth token for private repos (optional).
        """
        args = [url]
        if dest:
            args.append(dest)
        options: Dict[str, str] = {}
        if branch:
            options["branch"] = branch
        if depth is not None:
            options["depth"] = str(depth)
        if auth_token:
            options["auth_token"] = auth_token
        self._build_steps.append(
            BuildStep(type="git_clone", args=args,
                      options=options if options else None)
        )
        return self

    def mkdir(self, path: str, mode: Optional[str] = None) -> "TemplateBuilder":
        """Create a directory with parents (like ``mkdir -p``)."""
        options: Dict[str, str] = {}
        if mode:
            options["mode"] = mode
        self._build_steps.append(
            BuildStep(type="mkdir", args=[path],
                      options=options if options else None)
        )
        return self

    # -- Ready command helpers ----------------------------------------------

    @staticmethod
    def wait_for_port(port: int) -> str:
        """Generate a ready_cmd that waits for a TCP port to be listening."""
        return f"ss -tuln | grep -q :{port}"

    @staticmethod
    def wait_for_url(url: str, expected_status: int = 200) -> str:
        """Generate a ready_cmd that waits for an HTTP endpoint."""
        return f"curl -sf -o /dev/null -w '%{{http_code}}' {shlex.quote(url)} | grep -q {expected_status}"

    @staticmethod
    def wait_for_file(path: str) -> str:
        """Generate a ready_cmd that waits for a file to exist."""
        return f"test -f {shlex.quote(path)}"

    @staticmethod
    def wait_for_process(name: str) -> str:
        """Generate a ready_cmd that waits for a process to be running."""
        return f"pgrep {shlex.quote(name)} > /dev/null"

    # -- Backward-compatible aliases (deprecated) ---------------------------

    def set_vcpu(self, count: int) -> "TemplateBuilder":
        """Deprecated: use :meth:`vcpu` instead."""
        warnings.warn("set_vcpu() is deprecated, use vcpu() instead", DeprecationWarning, stacklevel=2)
        return self.vcpu(count)

    def set_memory(self, mb: int) -> "TemplateBuilder":
        """Deprecated: use :meth:`memory` instead."""
        warnings.warn("set_memory() is deprecated, use memory() instead", DeprecationWarning, stacklevel=2)
        return self.memory(mb)

    def set_disk(self, mb: int) -> "TemplateBuilder":
        """Deprecated: use :meth:`disk` instead."""
        warnings.warn("set_disk() is deprecated, use disk() instead", DeprecationWarning, stacklevel=2)
        return self.disk(mb)

    def set_template_id(self, tid: str) -> "TemplateBuilder":
        """Deprecated: use :meth:`template_id` instead."""
        warnings.warn("set_template_id() is deprecated, use template_id() instead", DeprecationWarning, stacklevel=2)
        return self.template_id(tid)

    def set_start_cmd(self, cmd: str) -> "TemplateBuilder":
        """Deprecated: use :meth:`start_cmd` instead."""
        warnings.warn("set_start_cmd() is deprecated, use start_cmd() instead", DeprecationWarning, stacklevel=2)
        return self.start_cmd(cmd)

    def set_ready_cmd(self, cmd: str, timeout_secs: int = 60) -> "TemplateBuilder":
        """Deprecated: use :meth:`ready_cmd` instead."""
        warnings.warn("set_ready_cmd() is deprecated, use ready_cmd() instead", DeprecationWarning, stacklevel=2)
        return self.ready_cmd(cmd, timeout_secs)

    def set_envs(self, e: Dict[str, str]) -> "TemplateBuilder":
        """Deprecated: use :meth:`envs` instead."""
        warnings.warn("set_envs() is deprecated, use envs() instead", DeprecationWarning, stacklevel=2)
        return self.envs(e)

    def set_env(self, key: str, value: str) -> "TemplateBuilder":
        """Deprecated: use :meth:`env` instead."""
        warnings.warn("set_env() is deprecated, use env() instead", DeprecationWarning, stacklevel=2)
        return self.env(key, value)

    def set_tags(self, t: Dict[str, str]) -> "TemplateBuilder":
        """Deprecated: use :meth:`tags` instead."""
        warnings.warn("set_tags() is deprecated, use tags() instead", DeprecationWarning, stacklevel=2)
        return self.tags(t)

    def copy_local_file(
        self, local_path: str, dest_path: str,
        mode: Optional[str] = None, user: Optional[str] = None,
    ) -> "TemplateBuilder":
        """Deprecated: use :meth:`copy_file` instead."""
        warnings.warn("copy_local_file() is deprecated, use copy_file() instead", DeprecationWarning, stacklevel=2)
        return self.copy_file(local_path, dest_path, mode=mode, user=user)

    def from_python(self, version: str = "3.11-slim") -> "TemplateBuilder":
        """Deprecated: use :meth:`from_image` with ``'python:<version>'``."""
        warnings.warn("from_python() is deprecated, use from_image('python:...') instead", DeprecationWarning, stacklevel=2)
        return self.from_image(f"python:{version}")

    def from_node(self, version: str = "lts") -> "TemplateBuilder":
        """Deprecated: use :meth:`from_image` with ``'node:<version>'``."""
        warnings.warn("from_node() is deprecated, use from_image('node:...') instead", DeprecationWarning, stacklevel=2)
        return self.from_image(f"node:{version}")

    def from_ubuntu(self, version: str = "22.04") -> "TemplateBuilder":
        """Deprecated: use :meth:`from_image` with ``'ubuntu:<version>'``."""
        warnings.warn("from_ubuntu() is deprecated, use from_image('ubuntu:...') instead", DeprecationWarning, stacklevel=2)
        return self.from_image(f"ubuntu:{version}")

    def from_dockerfile(self, content: str) -> "TemplateBuilder":
        """Deprecated: use :meth:`dockerfile` instead."""
        warnings.warn("from_dockerfile() is deprecated, use dockerfile() instead", DeprecationWarning, stacklevel=2)
        return self.dockerfile(content)

    # -- Serialization ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the builder state to the API request body."""
        data: Dict[str, Any] = {"name": self._name}

        if self._description:
            data["description"] = self._description
        if self._template_id:
            data["template_id"] = self._template_id
        if self._docker_image:
            data["docker_image"] = self._docker_image
        if self._dockerfile:
            data["dockerfile"] = self._dockerfile

        data["vcpu_count"] = self._vcpu_count
        data["memory_mb"] = self._memory_mb
        data["disk_mb"] = self._disk_mb

        if self._start_cmd:
            data["start_cmd"] = self._start_cmd
        if self._ready_cmd:
            data["ready_cmd"] = self._ready_cmd
            data["ready_timeout_secs"] = self._ready_timeout_secs
        if self._environment:
            data["environment"] = self._environment
        if self._build_steps:
            data["build_steps"] = [step.to_dict() for step in self._build_steps]
        if self._tags:
            data["tags"] = self._tags

        return data
