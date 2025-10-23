"""
Type definitions for Sandbox API
"""
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SandboxCreate:
    """Request body for creating a sandbox"""
    provider: str
    region: str
    template: Optional[str] = "python-base-v1"
    timeout: Optional[int] = 300
    env_vars: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Sandbox:
    """Sandbox object"""
    sandbox_id: str
    status: str
    template: Optional[str] = None
    template_id: Optional[str] = None
    started_at: Optional[str] = None
    timeout_at: Optional[str] = None
    cpu_count: Optional[int] = None
    memory_mb: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    ended_at: Optional[str] = None


@dataclass
class SandboxList:
    """List of sandboxes response"""
    sandboxes: List[Sandbox]
    total: int


@dataclass
class SandboxMetrics:
    """Sandbox resource usage metrics"""
    timestamp: str
    cpu_usage: float
    memory_usage: float
    memory_total: float
    disk_read: int
    disk_write: int
    network_rx: int
    network_tx: int


@dataclass
class SandboxTimeout:
    """Sandbox timeout update request"""
    timeout: int


@dataclass
class SandboxTimeoutResponse:
    """Sandbox timeout update response"""
    message: str
    timeout: Optional[int] = None
    timeout_at: Optional[str] = None


@dataclass
class SandboxHostURL:
    """Sandbox host URL response"""
    url: str


@dataclass
class FileRead:
    """File read request"""
    path: str


@dataclass
class FileReadResponse:
    """File read response"""
    content: str
    path: Optional[str] = None
    size: Optional[int] = None


@dataclass
class FileWrite:
    """File write request"""
    path: str
    content: str


@dataclass
class FileWriteResponse:
    """File write response"""
    message: str
    path: Optional[str] = None
    bytes_written: Optional[int] = None


@dataclass
class FileList:
    """File list request"""
    path: str


@dataclass
class FileInfo:
    """File information"""
    name: str
    path: str
    size: int
    is_dir: bool
    modified_at: str
    mode: Optional[str] = None  # File permissions mode


@dataclass
class FileListResponse:
    """File list response"""
    files: List[FileInfo]


@dataclass
class FileDelete:
    """File delete request"""
    path: str


@dataclass
class FileDeleteResponse:
    """File delete response"""
    message: str
    path: Optional[str] = None


@dataclass
class DirectoryCreate:
    """Directory create request"""
    path: str


@dataclass
class DirectoryCreateResponse:
    """Directory create response"""
    message: str
    path: Optional[str] = None


@dataclass
class FileUploadResponse:
    """File upload response"""
    message: str
    path: Optional[str] = None
    size: Optional[int] = None


@dataclass
class CommandRun:
    """Command execution request"""
    command: str
    args: Optional[List[str]] = None
    working_dir: Optional[str] = None
    environment: Optional[Dict[str, str]] = None
    timeout: Optional[int] = None


@dataclass
class CommandRunResponse:
    """Command execution response"""
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    success: bool
    error: Optional[str] = None


@dataclass
class CodeRun:
    """Code execution request"""
    code: str
    language: Optional[str] = "python"
    context_id: Optional[str] = None
    environment: Optional[Dict[str, str]] = None
    timeout: Optional[int] = None
    on_stdout: Optional[bool] = False
    on_stderr: Optional[bool] = False
    on_result: Optional[bool] = False
    on_error: Optional[bool] = False


@dataclass
class CodeEvent:
    """Code execution event"""
    type: str
    line: Optional[str] = None
    timestamp: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    execution_count: Optional[int] = None


@dataclass
class CodeRunResponse:
    """Code execution response"""
    execution_id: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    logs: Optional[Dict[str, List[str]]] = None


@dataclass
class CodeContextCreate:
    """Code context creation request"""
    language: Optional[str] = "python"
    cwd: Optional[str] = None


@dataclass
class CodeContext:
    """Code execution context"""
    context_id: str
    language: str
    cwd: str
    created_at: str
    expires_at: str
    status: Optional[str] = None
    last_used: Optional[str] = None


@dataclass
class CodeContextDeleteResponse:
    """Code context delete response"""
    message: str
    context_id: Optional[str] = None


@dataclass
class Template:
    """Sandbox template"""
    id: str
    name: str
    description: str
    vcpu_count: int
    memory_mb: int
    disk_size_mb: int
    visibility: str
    created_at: str
    updated_at: str


@dataclass
class TemplateList:
    """List of templates response"""
    templates: List[Template]
    limit: int
    offset: int


@dataclass
class SandboxKillResponse:
    """Sandbox kill response"""
    message: str
    sandbox_id: Optional[str] = None