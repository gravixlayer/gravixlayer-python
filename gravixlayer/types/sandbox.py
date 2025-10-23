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
    
    def __post_init__(self):
        """Initialize client reference after dataclass creation"""
        self._client = None
        self._alive = True
    
    @classmethod
    def create(
        cls,
        template: str = "python-base-v1",
        provider: str = "gravix",
        region: str = "eu-west-1",
        timeout_minutes: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> "Sandbox":
        """
        Create a new sandbox instance with simplified interface.
        
        Args:
            template: Template to use (default: "python-base-v1")
            provider: Cloud provider (default: "gravix")
            region: Region to deploy in (default: "eu-west-1")
            timeout_minutes: How long the instance stays alive (default: 5 minutes)
            metadata: Optional metadata tags
            api_key: API key (uses GRAVIXLAYER_API_KEY env var if not provided)
            base_url: Base URL (uses GRAVIXLAYER_BASE_URL env var if not provided)
        
        Returns:
            Sandbox instance ready for code execution
        """
        from ..client import GravixLayer
        
        client = GravixLayer(api_key=api_key, base_url=base_url)
        
        sandbox_response = client.sandbox.sandboxes.create(
            provider=provider,
            region=region,
            template=template,
            timeout=timeout_minutes * 60,  # Convert to seconds
            metadata=metadata or {}
        )
        
        # Create instance from response
        instance = cls(
            sandbox_id=sandbox_response.sandbox_id,
            status=sandbox_response.status,
            template=sandbox_response.template,
            template_id=sandbox_response.template_id,
            started_at=sandbox_response.started_at,
            timeout_at=sandbox_response.timeout_at,
            cpu_count=sandbox_response.cpu_count,
            memory_mb=sandbox_response.memory_mb,
            metadata=sandbox_response.metadata,
            ended_at=sandbox_response.ended_at
        )
        
        instance._client = client
        return instance
    
    def run_code(self, code: str, language: str = "python") -> "Execution":
        """Execute code in the sandbox"""
        if not self._alive:
            raise RuntimeError("Sandbox has been terminated")
        
        if self._client is None:
            raise RuntimeError("Client not initialized. Use Sandbox.create() to create a new instance.")
        
        response = self._client.sandbox.sandboxes.run_code(
            self.sandbox_id,
            code=code,
            language=language
        )
        
        return Execution(response)
    
    def run_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> "Execution":
        """Execute a shell command in the sandbox"""
        if not self._alive:
            raise RuntimeError("Sandbox has been terminated")
        
        if self._client is None:
            raise RuntimeError("Client not initialized. Use Sandbox.create() to create a new instance.")
        
        response = self._client.sandbox.sandboxes.run_command(
            self.sandbox_id,
            command=command,
            args=args or [],
            working_dir=working_dir,
            timeout=timeout
        )
        
        return Execution(response)
    
    def write_file(self, path: str, content: str) -> None:
        """Write content to a file in the sandbox"""
        if not self._alive:
            raise RuntimeError("Sandbox has been terminated")
        
        if self._client is None:
            raise RuntimeError("Client not initialized. Use Sandbox.create() to create a new instance.")
        
        self._client.sandbox.sandboxes.write_file(
            self.sandbox_id,
            path=path,
            content=content
        )
    
    def read_file(self, path: str) -> str:
        """Read content from a file in the sandbox"""
        if not self._alive:
            raise RuntimeError("Sandbox has been terminated")
        
        if self._client is None:
            raise RuntimeError("Client not initialized. Use Sandbox.create() to create a new instance.")
        
        response = self._client.sandbox.sandboxes.read_file(
            self.sandbox_id,
            path=path
        )
        return response.content
    
    def list_files(self, path: str = "/home/user") -> List[str]:
        """List files in a directory"""
        if not self._alive:
            raise RuntimeError("Sandbox has been terminated")
        
        if self._client is None:
            raise RuntimeError("Client not initialized. Use Sandbox.create() to create a new instance.")
        
        response = self._client.sandbox.sandboxes.list_files(
            self.sandbox_id,
            path=path
        )
        return [f.name for f in response.files]
    
    def delete_file(self, path: str) -> None:
        """Delete a file in the sandbox"""
        if not self._alive:
            raise RuntimeError("Sandbox has been terminated")
        
        if self._client is None:
            raise RuntimeError("Client not initialized. Use Sandbox.create() to create a new instance.")
        
        self._client.sandbox.sandboxes.delete_file(
            self.sandbox_id,
            path=path
        )
    
    def upload_file(self, local_path: str, remote_path: str) -> None:
        """Upload a local file to the sandbox"""
        if not self._alive:
            raise RuntimeError("Sandbox has been terminated")
        
        if self._client is None:
            raise RuntimeError("Client not initialized. Use Sandbox.create() to create a new instance.")
        
        with open(local_path, 'rb') as f:
            self._client.sandbox.sandboxes.upload_file(
                self.sandbox_id,
                file=f,
                path=remote_path
            )
    
    def kill(self) -> None:
        """Terminate the sandbox and clean up resources"""
        if self._alive and self._client is not None:
            try:
                self._client.sandbox.sandboxes.kill(self.sandbox_id)
            except Exception:
                pass  # Ignore errors during cleanup
            self._alive = False
    
    def is_alive(self) -> bool:
        """Check if the sandbox is still running"""
        if not self._alive or self._client is None:
            return False
        
        try:
            info = self._client.sandbox.sandboxes.get(self.sandbox_id)
            return info.status == "running"
        except:
            self._alive = False
            return False
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically terminate sandbox"""
        self.kill()
    
    def __del__(self):
        """Destructor - ensure sandbox is terminated"""
        if hasattr(self, '_alive') and self._alive:
            try:
                self.kill()
            except:
                pass  # Ignore errors during cleanup


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


class Execution:
    """Represents the result of code or command execution in a sandbox"""
    
    def __init__(self, response: Union[CodeRunResponse, CommandRunResponse]):
        self._response = response
    
    @property
    def logs(self) -> Dict[str, List[str]]:
        """Get execution logs with stdout and stderr"""
        if hasattr(self._response, 'logs') and self._response.logs:
            return self._response.logs
        
        # Fallback for command responses
        logs = {"stdout": [], "stderr": []}
        if hasattr(self._response, 'stdout') and self._response.stdout:
            logs["stdout"] = self._response.stdout.split('\n')
        if hasattr(self._response, 'stderr') and self._response.stderr:
            logs["stderr"] = self._response.stderr.split('\n')
        return logs
    
    @property
    def stdout(self) -> str:
        """Get standard output as a string"""
        if hasattr(self._response, 'stdout'):
            return self._response.stdout or ""
        if hasattr(self._response, 'logs') and self._response.logs:
            return '\n'.join(self._response.logs.get('stdout', []))
        return ""
    
    @property
    def stderr(self) -> str:
        """Get standard error as a string"""
        if hasattr(self._response, 'stderr'):
            return self._response.stderr or ""
        if hasattr(self._response, 'logs') and self._response.logs:
            return '\n'.join(self._response.logs.get('stderr', []))
        return ""
    
    @property
    def exit_code(self) -> int:
        """Get the exit code of the execution"""
        return getattr(self._response, 'exit_code', 0)
    
    @property
    def success(self) -> bool:
        """Check if execution was successful"""
        return getattr(self._response, 'success', self.exit_code == 0)