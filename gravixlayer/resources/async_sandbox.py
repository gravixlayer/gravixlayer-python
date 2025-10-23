"""
Sandbox API resource for asynchronous client
"""
import httpx
from typing import List, Dict, Any, Optional, BinaryIO
from ..types.sandbox import (
    SandboxCreate, Sandbox, SandboxList, SandboxMetrics, SandboxTimeout,
    SandboxTimeoutResponse, SandboxHostURL, FileRead, FileReadResponse,
    FileWrite, FileWriteResponse, FileList, FileListResponse, FileInfo,
    FileDelete, FileDeleteResponse, DirectoryCreate, DirectoryCreateResponse,
    FileUploadResponse, CommandRun, CommandRunResponse, CodeRun,
    CodeRunResponse, CodeContextCreate, CodeContext, CodeContextDeleteResponse,
    Template, TemplateList, SandboxKillResponse
)


class AsyncSandboxes:
    """Sandboxes resource for asynchronous client"""
    
    def __init__(self, client):
        self.client = client
        self._agents_base_url = None
    
    def _get_agents_base_url(self) -> str:
        """Get the agents API base URL"""
        if self._agents_base_url is None:
            # Replace /v1/inference with /v1/agents for agent endpoints
            self._agents_base_url = self.client.base_url.replace("/v1/inference", "/v1/agents")
        return self._agents_base_url
    
    async def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API"""
        original_base_url = self.client.base_url
        self.client.base_url = self._get_agents_base_url()
        
        try:
            return await self.client._make_request(method, endpoint, data, **kwargs)
        finally:
            self.client.base_url = original_base_url

    # Sandbox Lifecycle Methods
    
    async def create(
        self,
        provider: str,
        region: str,
        template: Optional[str] = "python-base-v1",
        timeout: Optional[int] = 300,
        env_vars: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Sandbox:
        """Create a new sandbox instance"""
        data = {
            "provider": provider,
            "region": region,
            "template": template,
            "timeout": timeout
        }
        if env_vars:
            data["env_vars"] = env_vars
        if metadata:
            data["metadata"] = metadata
        
        response = await self._make_agents_request("POST", "sandboxes", data)
        result = response.json()
        
        # Ensure all fields have defaults if missing
        defaults = {
            "metadata": {},
            "template": template,  # Use the requested template as default
            "template_id": None,
            "started_at": None,
            "timeout_at": None,
            "cpu_count": None,
            "memory_mb": None,
            "ended_at": None
        }
        
        for key, default_value in defaults.items():
            if key not in result or result[key] is None:
                result[key] = default_value
            
        return Sandbox(**result)
    
    async def list(
        self,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0
    ) -> SandboxList:
        """List all sandboxes"""
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        
        endpoint = "sandboxes"
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"sandboxes?{query_string}"
        
        response = await self._make_agents_request("GET", endpoint)
        result = response.json()
        
        # Fix missing fields for each sandbox
        sandboxes = []
        defaults = {
            "metadata": {},
            "template": None,
            "template_id": None,
            "started_at": None,
            "timeout_at": None,
            "cpu_count": None,
            "memory_mb": None,
            "ended_at": None
        }
        
        for sandbox_data in result["sandboxes"]:
            for key, default_value in defaults.items():
                if key not in sandbox_data or sandbox_data[key] is None:
                    sandbox_data[key] = default_value
            sandboxes.append(Sandbox(**sandbox_data))
            
        return SandboxList(sandboxes=sandboxes, total=result["total"])
    
    async def get(self, sandbox_id: str) -> Sandbox:
        """Get detailed information about a specific sandbox"""
        response = await self._make_agents_request("GET", f"sandboxes/{sandbox_id}")
        result = response.json()
        
        # Ensure all fields have defaults if missing
        defaults = {
            "metadata": {},
            "template": None,
            "template_id": None,
            "started_at": None,
            "timeout_at": None,
            "cpu_count": None,
            "memory_mb": None,
            "ended_at": None
        }
        
        for key, default_value in defaults.items():
            if key not in result or result[key] is None:
                result[key] = default_value
            
        return Sandbox(**result)
    
    async def kill(self, sandbox_id: str) -> SandboxKillResponse:
        """Terminate a running sandbox immediately"""
        response = await self._make_agents_request("DELETE", f"sandboxes/{sandbox_id}")
        result = response.json()
        return SandboxKillResponse(**result)

    # Sandbox Configuration Methods
    
    async def set_timeout(self, sandbox_id: str, timeout: int) -> SandboxTimeoutResponse:
        """Update the timeout for a running sandbox"""
        data = {"timeout": timeout}
        response = await self._make_agents_request("POST", f"sandboxes/{sandbox_id}/timeout", data)
        result = response.json()
        return SandboxTimeoutResponse(**result)
    
    async def get_metrics(self, sandbox_id: str) -> SandboxMetrics:
        """Get current resource usage metrics for a sandbox"""
        response = await self._make_agents_request("GET", f"sandboxes/{sandbox_id}/metrics")
        result = response.json()
        return SandboxMetrics(**result)
    
    async def get_host_url(self, sandbox_id: str, port: int) -> SandboxHostURL:
        """Get the public URL for accessing a specific port on the sandbox"""
        response = await self._make_agents_request("GET", f"sandboxes/{sandbox_id}/host/{port}")
        result = response.json()
        return SandboxHostURL(**result)

    # File Operations Methods
    
    async def read_file(self, sandbox_id: str, path: str) -> FileReadResponse:
        """Read the contents of a file from the sandbox filesystem"""
        data = {"path": path}
        response = await self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/read", data)
        result = response.json()
        return FileReadResponse(**result)
    
    async def write_file(self, sandbox_id: str, path: str, content: str) -> FileWriteResponse:
        """Write content to a file in the sandbox filesystem"""
        data = {"path": path, "content": content}
        response = await self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/write", data)
        result = response.json()
        return FileWriteResponse(**result)
    
    async def list_files(self, sandbox_id: str, path: str) -> FileListResponse:
        """List files and directories in a specified path"""
        data = {"path": path}
        response = await self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/list", data)
        result = response.json()
        
        # Filter and map file info fields
        files = []
        for file_info in result["files"]:
            # Map API fields to our dataclass fields
            mapped_info = {
                "name": file_info.get("name", ""),
                "path": file_info.get("path", ""),
                "size": file_info.get("size", 0),
                "is_dir": file_info.get("is_dir", False),
                "modified_at": file_info.get("modified_at") or file_info.get("mod_time", ""),
                "mode": file_info.get("mode")
            }
            files.append(FileInfo(**mapped_info))
            
        return FileListResponse(files=files)
    
    async def delete_file(self, sandbox_id: str, path: str) -> FileDeleteResponse:
        """Delete a file or directory from the sandbox filesystem"""
        data = {"path": path}
        response = await self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/delete", data)
        result = response.json()
        return FileDeleteResponse(**result)
    
    async def make_directory(self, sandbox_id: str, path: str) -> DirectoryCreateResponse:
        """Create a new directory in the sandbox filesystem"""
        data = {"path": path}
        response = await self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/mkdir", data)
        result = response.json()
        return DirectoryCreateResponse(**result)
    
    async def upload_file(
        self,
        sandbox_id: str,
        file: BinaryIO,
        path: Optional[str] = None
    ) -> FileUploadResponse:
        """Upload a file to the sandbox filesystem using multipart form data"""
        # For async, we need to handle file uploads differently
        # We'll use httpx directly for multipart uploads
        url = f"{self._get_agents_base_url()}/sandboxes/{sandbox_id}/upload"
        headers = {
            "Authorization": f"Bearer {self.client.api_key}",
            "User-Agent": self.client.user_agent,
            **self.client.custom_headers,
        }
        
        files = {"file": file}
        data = {}
        if path:
            data["path"] = path
        
        async with httpx.AsyncClient(timeout=self.client.timeout) as client:
            response = await client.post(url, headers=headers, files=files, data=data)
            
            if response.status_code in [200, 201]:
                result = response.json()
                return FileUploadResponse(**result)
            else:
                response.raise_for_status()
    
    async def download_file(self, sandbox_id: str, path: str) -> bytes:
        """Download a file from the sandbox filesystem"""
        endpoint = f"sandboxes/{sandbox_id}/download?path={path}"
        response = await self._make_agents_request("GET", endpoint)
        return response.content

    # Command Execution Methods
    
    async def run_command(
        self,
        sandbox_id: str,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> CommandRunResponse:
        """Execute a shell command in the sandbox"""
        data = {"command": command}
        if args:
            data["args"] = args
        if working_dir:
            data["working_dir"] = working_dir
        if environment:
            data["environment"] = environment
        if timeout:
            data["timeout"] = timeout
        
        response = await self._make_agents_request("POST", f"sandboxes/{sandbox_id}/commands/run", data)
        result = response.json()
        return CommandRunResponse(**result)

    # Code Execution Methods
    
    async def run_code(
        self,
        sandbox_id: str,
        code: str,
        language: Optional[str] = "python",
        context_id: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        on_stdout: Optional[bool] = False,
        on_stderr: Optional[bool] = False,
        on_result: Optional[bool] = False,
        on_error: Optional[bool] = False
    ) -> CodeRunResponse:
        """Execute code in the sandbox using Jupyter kernel"""
        data = {"code": code}
        if language:
            data["language"] = language
        if context_id:
            data["context_id"] = context_id
        if environment:
            data["environment"] = environment
        if timeout:
            data["timeout"] = timeout
        if on_stdout:
            data["on_stdout"] = on_stdout
        if on_stderr:
            data["on_stderr"] = on_stderr
        if on_result:
            data["on_result"] = on_result
        if on_error:
            data["on_error"] = on_error
        
        response = await self._make_agents_request("POST", f"sandboxes/{sandbox_id}/code/run", data)
        result = response.json()
        
        # Ensure all required fields have defaults
        if "execution_id" not in result:
            result["execution_id"] = None
        if "results" not in result:
            result["results"] = {}
        if "error" not in result:
            result["error"] = None
        if "logs" not in result:
            result["logs"] = {"stdout": [], "stderr": []}
            
        return CodeRunResponse(**result)
    
    async def create_code_context(
        self,
        sandbox_id: str,
        language: Optional[str] = "python",
        cwd: Optional[str] = None
    ) -> CodeContext:
        """Create an isolated code execution context"""
        data = {}
        if language:
            data["language"] = language
        if cwd:
            data["cwd"] = cwd
        
        response = await self._make_agents_request("POST", f"sandboxes/{sandbox_id}/code/contexts", data)
        result = response.json()
        
        # Map API response to our dataclass fields
        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", language or "python"),
            "cwd": result.get("cwd", cwd or "/home/user"),
            "created_at": result.get("created_at"),
            "expires_at": result.get("expires_at"),
            "status": result.get("status"),
            "last_used": result.get("last_used")
        }
        
        return CodeContext(**mapped_result)
    
    async def get_code_context(self, sandbox_id: str, context_id: str) -> CodeContext:
        """Get information about a code execution context"""
        response = await self._make_agents_request("GET", f"sandboxes/{sandbox_id}/code/contexts/{context_id}")
        result = response.json()
        
        # Map API response to our dataclass fields
        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", "python"),
            "cwd": result.get("cwd", "/home/user"),
            "created_at": result.get("created_at"),
            "expires_at": result.get("expires_at"),
            "status": result.get("status"),
            "last_used": result.get("last_used")
        }
        
        return CodeContext(**result)
    
    async def delete_code_context(self, sandbox_id: str, context_id: str) -> CodeContextDeleteResponse:
        """Delete a code execution context"""
        response = await self._make_agents_request("DELETE", f"sandboxes/{sandbox_id}/code/contexts/{context_id}")
        result = response.json()
        return CodeContextDeleteResponse(**result)


class AsyncSandboxTemplates:
    """Sandbox Templates resource for asynchronous client"""
    
    def __init__(self, client):
        self.client = client
        self._agents_base_url = None
    
    def _get_agents_base_url(self) -> str:
        """Get the agents API base URL"""
        if self._agents_base_url is None:
            # Replace /v1/inference with /v1/agents for agent endpoints
            self._agents_base_url = self.client.base_url.replace("/v1/inference", "/v1/agents")
        return self._agents_base_url
    
    async def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API"""
        original_base_url = self.client.base_url
        self.client.base_url = self._get_agents_base_url()
        
        try:
            return await self.client._make_request(method, endpoint, data, **kwargs)
        finally:
            self.client.base_url = original_base_url
    
    async def list(
        self,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0
    ) -> TemplateList:
        """List available sandbox templates"""
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        
        endpoint = "templates"
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"templates?{query_string}"
        
        response = await self._make_agents_request("GET", endpoint)
        result = response.json()
        
        templates = [Template(**template) for template in result["templates"]]
        return TemplateList(
            templates=templates,
            limit=result["limit"],
            offset=result["offset"]
        )


class AsyncSandboxResource:
    """Main Sandbox resource that contains sandboxes and templates"""
    
    def __init__(self, client):
        self.client = client
        self.sandboxes = AsyncSandboxes(client)
        self.templates = AsyncSandboxTemplates(client)