"""
Type definitions for Template Build Pipeline API.

Provides dataclasses and enums for template creation, build orchestration,
and status tracking. Aligned with the backend template build API contract.
"""

from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum


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
        import base64
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
    that get serialized into a single API request. All mutator methods
    return self for chaining.

    Example:
        >>> template = (
        ...     TemplateBuilder("my-ml-template")
        ...     .from_image("python:3.11-slim")
        ...     .apt_install("git", "curl")
        ...     .pip_install("numpy", "pandas", "torch")
        ...     .copy_file("/app/config.yaml", b"model: gpt2")
        ...     .run("python -c 'import torch; print(torch.__version__)'")
        ...     .set_start_cmd("python /app/server.py")
        ...     .set_ready_cmd("curl -s http://localhost:8000/health")
        ... )
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
        """Set the base Docker image (e.g. 'python:3.11-slim')."""
        if self._dockerfile:
            raise ValueError("Cannot set docker_image when dockerfile is already set")
        self._docker_image = image
        return self

    def from_dockerfile(self, content: str) -> "TemplateBuilder":
        """Set the base image via Dockerfile content."""
        if self._docker_image:
            raise ValueError("Cannot set dockerfile when docker_image is already set")
        self._dockerfile = content
        return self

    def from_python(self, version: str = "3.11-slim") -> "TemplateBuilder":
        """Use a Python base image."""
        return self.from_image(f"python:{version}")

    def from_node(self, version: str = "lts") -> "TemplateBuilder":
        """Use a Node.js base image."""
        return self.from_image(f"node:{version}")

    def from_ubuntu(self, version: str = "22.04") -> "TemplateBuilder":
        """Use an Ubuntu base image."""
        return self.from_image(f"ubuntu:{version}")

    # -- Resource configuration ---------------------------------------------

    def set_vcpu(self, count: int) -> "TemplateBuilder":
        """Set the number of vCPUs (default: 2)."""
        if count < 1:
            raise ValueError("vcpu_count must be >= 1")
        self._vcpu_count = count
        return self

    def set_memory(self, mb: int) -> "TemplateBuilder":
        """Set memory in MB (default: 512)."""
        if mb < 1:
            raise ValueError("memory_mb must be >= 1")
        self._memory_mb = mb
        return self

    def set_disk(self, mb: int) -> "TemplateBuilder":
        """Set disk size in MB (default: 4096)."""
        if mb < 1:
            raise ValueError("disk_mb must be >= 1")
        self._disk_mb = mb
        return self

    def set_template_id(self, template_id: str) -> "TemplateBuilder":
        """Set a custom template ID (auto-generated by default)."""
        self._template_id = template_id
        return self

    # -- Startup and readiness ----------------------------------------------

    def set_start_cmd(self, cmd: str) -> "TemplateBuilder":
        """Set the command to run after VM starts (captured in snapshot)."""
        self._start_cmd = cmd
        return self

    def set_ready_cmd(self, cmd: str, timeout_secs: int = 60) -> "TemplateBuilder":
        """Set the readiness check command that must exit 0.

        The build process polls this command until success or timeout.
        """
        self._ready_cmd = cmd
        self._ready_timeout_secs = timeout_secs
        return self

    # -- Environment and tags -----------------------------------------------

    def set_envs(self, envs: Dict[str, str]) -> "TemplateBuilder":
        """Set environment variables (persisted to /etc/profile.d/)."""
        self._environment.update(envs)
        return self

    def set_env(self, key: str, value: str) -> "TemplateBuilder":
        """Set a single environment variable."""
        self._environment[key] = value
        return self

    def set_tags(self, tags: Dict[str, str]) -> "TemplateBuilder":
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
        dest_path: str,
        content: Union[str, bytes],
        mode: Optional[str] = None,
        user: Optional[str] = None,
    ) -> "TemplateBuilder":
        """Copy file content to a path inside the VM.

        Args:
            dest_path: Destination path inside the VM
            content: File content as str (utf-8 encoded) or bytes
            mode: Optional file permissions (e.g. "0755")
            user: Optional file owner
        """
        if isinstance(content, str):
            content = content.encode("utf-8")
        options = {}
        if mode:
            options["mode"] = mode
        if user:
            options["user"] = user
        self._build_steps.append(
            BuildStep(type="copy_file", args=[dest_path], content=content,
                      options=options if options else None)
        )
        return self

    def copy_local_file(
        self,
        local_path: str,
        dest_path: str,
        mode: Optional[str] = None,
        user: Optional[str] = None,
    ) -> "TemplateBuilder":
        """Copy a local file into the template VM.

        Args:
            local_path: Path to the local file
            dest_path: Destination path inside the VM
            mode: Optional file permissions (e.g. "0755")
            user: Optional file owner
        """
        with open(local_path, "rb") as f:
            content = f.read()
        return self.copy_file(dest_path, content, mode=mode, user=user)

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
            url: Repository URL
            dest: Destination directory (optional)
            branch: Branch to clone (optional)
            depth: Clone depth for shallow clone (optional)
            auth_token: HTTPS auth token for private repos (optional)
        """
        args = [url]
        if dest:
            args.append(dest)
        options = {}
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
        """Create a directory with parents (like mkdir -p)."""
        options = {}
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
        return f"curl -sf -o /dev/null -w '%{{http_code}}' {url} | grep -q {expected_status}"

    @staticmethod
    def wait_for_file(path: str) -> str:
        """Generate a ready_cmd that waits for a file to exist."""
        return f"test -f {path}"

    @staticmethod
    def wait_for_process(name: str) -> str:
        """Generate a ready_cmd that waits for a process to be running."""
        return f"pgrep {name} > /dev/null"

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
