"""
Sandbox API resource for synchronous client
"""

from typing import List, Dict, Any, Optional, BinaryIO, Union
from ..types.sandbox import (
    SandboxCreate,
    Sandbox,
    SandboxList,
    SandboxMetrics,
    SandboxTimeout,
    SandboxTimeoutResponse,
    SandboxHostURL,
    FileRead,
    FileReadResponse,
    FileWrite,
    FileWriteResponse,
    FileList,
    FileListResponse,
    FileInfo,
    FileDelete,
    FileDeleteResponse,
    DirectoryCreate,
    DirectoryCreateResponse,
    FileUploadResponse,
    WriteEntry,
    WriteResult,
    WriteFilesResponse,
    CommandRun,
    CommandRunResponse,
    CodeRun,
    CodeRunResponse,
    CodeContextCreate,
    CodeContext,
    CodeContextDeleteResponse,
    Template,
    TemplateList,
    SandboxKillResponse,
)
import os
import io


class Sandboxes:
    """Sandboxes resource for synchronous client"""

    def __init__(self, client):
        self.client = client

    def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)"""
        return self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    # Sandbox Lifecycle Methods

    def create(
        self,
        provider: Optional[str] = None,
        region: Optional[str] = None,
        template: Optional[str] = "python-base-v1",
        timeout: Optional[int] = 300,
        env_vars: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Sandbox:
        """Create a new sandbox instance.

        Args:
            provider: Cloud provider (falls back to client.cloud if not set)
            region: Cloud region (falls back to client.region if not set)
            template: Template name or ID to use
            timeout: Sandbox timeout in seconds (default: 300, max: 43200)
            env_vars: Environment variables for the sandbox
            metadata: Metadata tags for the sandbox
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

        data = {"provider": resolved_provider, "region": resolved_region, "template": template, "timeout": timeout}
        if env_vars:
            data["env_vars"] = env_vars
        if metadata:
            data["metadata"] = metadata  # type: ignore[assignment]  # type: ignore[assignment]

        response = self._make_agents_request("POST", "sandboxes", data)
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
            "ended_at": None,
        }

        for key, default_value in defaults.items():
            if key not in result or result[key] is None:
                result[key] = default_value

        return Sandbox.from_api(result)

    def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> SandboxList:
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

        response = self._make_agents_request("GET", endpoint)
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
            "ended_at": None,
        }

        for sandbox_data in result["sandboxes"]:
            for key, default_value in defaults.items():
                if key not in sandbox_data or sandbox_data[key] is None:
                    sandbox_data[key] = default_value
            sandboxes.append(Sandbox.from_api(sandbox_data))

        return SandboxList(sandboxes=sandboxes, total=result["total"])

    def get(self, sandbox_id: str) -> Sandbox:
        """Get detailed information about a specific sandbox"""
        response = self._make_agents_request("GET", f"sandboxes/{sandbox_id}")
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
            "ended_at": None,
        }

        for key, default_value in defaults.items():
            if key not in result or result[key] is None:
                result[key] = default_value

        return Sandbox.from_api(result)

    def kill(self, sandbox_id: str) -> SandboxKillResponse:
        """Terminate a running sandbox immediately"""
        response = self._make_agents_request("DELETE", f"sandboxes/{sandbox_id}")
        result = response.json()
        return SandboxKillResponse(**result)

    # Sandbox Configuration Methods

    def set_timeout(self, sandbox_id: str, timeout: int) -> SandboxTimeoutResponse:
        """Update the timeout for a running sandbox"""
        data = {"timeout": timeout}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/timeout", data)
        result = response.json()
        return SandboxTimeoutResponse(**result)

    def get_metrics(self, sandbox_id: str) -> SandboxMetrics:
        """Get current resource usage metrics for a sandbox"""
        response = self._make_agents_request("GET", f"sandboxes/{sandbox_id}/metrics")
        result = response.json()
        return SandboxMetrics(**result)

    def get_host_url(self, sandbox_id: str, port: int) -> SandboxHostURL:
        """Get the public URL for accessing a specific port on the sandbox"""
        response = self._make_agents_request("GET", f"sandboxes/{sandbox_id}/host/{port}")
        result = response.json()
        return SandboxHostURL(**result)

    # File Operations Methods

    def read_file(self, sandbox_id: str, path: str) -> FileReadResponse:
        """Read the contents of a file from the sandbox filesystem"""
        data = {"path": path}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/read", data)
        result = response.json()
        return FileReadResponse(**result)

    def write_file(self, sandbox_id: str, path: str, content: str) -> FileWriteResponse:
        """Write content to a file in the sandbox filesystem"""
        data = {"path": path, "content": content}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/write", data)
        result = response.json()
        return FileWriteResponse(**result)

    def list_files(self, sandbox_id: str, path: str) -> FileListResponse:
        """List files and directories in a specified path"""
        data = {"path": path}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/list", data)
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
                "mode": file_info.get("mode"),
            }
            files.append(FileInfo(**mapped_info))

        return FileListResponse(files=files)

    def delete_file(self, sandbox_id: str, path: str) -> FileDeleteResponse:
        """Delete a file or directory from the sandbox filesystem"""
        data = {"path": path}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/delete", data)
        result = response.json()
        return FileDeleteResponse(**result)

    def make_directory(self, sandbox_id: str, path: str) -> DirectoryCreateResponse:
        """Create a new directory in the sandbox filesystem"""
        data = {"path": path}
        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/files/mkdir", data)
        result = response.json()
        return DirectoryCreateResponse(**result)

    def upload_file(self, sandbox_id: str, file: BinaryIO, path: Optional[str] = None) -> FileUploadResponse:
        """Upload a file to the sandbox filesystem using multipart form data"""
        files = {"file": file}
        data = {}
        if path:
            data["path"] = path

        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/upload", data=data, files=files)
        result = response.json()
        return FileUploadResponse(**result)

    def download_file(self, sandbox_id: str, path: str) -> bytes:
        """Download a file from the sandbox filesystem"""
        endpoint = f"sandboxes/{sandbox_id}/download?path={path}"
        response = self._make_agents_request("GET", endpoint)
        return response.content

    # Multipart File Write Methods (E2B-style)

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

        # Build query params
        params = [f"path={path}"]
        if user:
            params.append(f"username={user}")
        if mode is not None:
            params.append(f"mode={oct(mode)}")
        query = "&".join(params)

        endpoint = f"sandboxes/{sandbox_id}/files?{query}"
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

        # Build query params
        params = []
        if user:
            params.append(f"username={user}")
        query = f"?{'&'.join(params)}" if params else ""

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

    def run_command(
        self,
        sandbox_id: str,
        command: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> CommandRunResponse:
        """Execute a shell command in the sandbox"""
        data = {"command": command}
        if args:
            data["args"] = args
        if working_dir:
            data["working_dir"] = working_dir
        if environment:
            data["environment"] = environment  # type: ignore[assignment]  # type: ignore[assignment]  # type: ignore[assignment]  # type: ignore[assignment]
        if timeout:
            data["timeout"] = timeout  # type: ignore[assignment]  # type: ignore[assignment]

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
        on_stdout: Optional[bool] = False,
        on_stderr: Optional[bool] = False,
        on_result: Optional[bool] = False,
        on_error: Optional[bool] = False,
    ) -> CodeRunResponse:
        """Execute code in the sandbox using Jupyter kernel"""
        data = {"code": code}
        if language:
            data["language"] = language
        if context_id:
            data["context_id"] = context_id
        if environment:
            data["environment"] = environment  # type: ignore[assignment]  # type: ignore[assignment]  # type: ignore[assignment]  # type: ignore[assignment]
        if timeout:
            data["timeout"] = timeout  # type: ignore[assignment]  # type: ignore[assignment]
        if on_stdout:
            data["on_stdout"] = on_stdout  # type: ignore[assignment]  # type: ignore[assignment]
        if on_stderr:
            data["on_stderr"] = on_stderr  # type: ignore[assignment]  # type: ignore[assignment]
        if on_result:
            data["on_result"] = on_result  # type: ignore[assignment]  # type: ignore[assignment]
        if on_error:
            data["on_error"] = on_error  # type: ignore[assignment]  # type: ignore[assignment]

        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/code/run", data)
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

    def create_code_context(
        self, sandbox_id: str, language: Optional[str] = "python", cwd: Optional[str] = None
    ) -> CodeContext:
        """Create an isolated code execution context"""
        data = {}
        if language:
            data["language"] = language
        if cwd:
            data["cwd"] = cwd

        response = self._make_agents_request("POST", f"sandboxes/{sandbox_id}/code/contexts", data)
        result = response.json()

        # Map API response to our dataclass fields
        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", language or "python"),
            "cwd": result.get("cwd", cwd or "/home/user"),
            "created_at": result.get("created_at"),
            "expires_at": result.get("expires_at"),
            "status": result.get("status"),
            "last_used": result.get("last_used"),
        }

        return CodeContext(**mapped_result)

    def get_code_context(self, sandbox_id: str, context_id: str) -> CodeContext:
        """Get information about a code execution context"""
        response = self._make_agents_request("GET", f"sandboxes/{sandbox_id}/code/contexts/{context_id}")
        result = response.json()

        # Map API response to our dataclass fields
        mapped_result = {
            "context_id": result.get("id") or result.get("context_id", ""),
            "language": result.get("language", "python"),
            "cwd": result.get("cwd", "/home/user"),
            "created_at": result.get("created_at"),
            "expires_at": result.get("expires_at"),
            "status": result.get("status"),
            "last_used": result.get("last_used"),
        }

        return CodeContext(**mapped_result)

    def delete_code_context(self, sandbox_id: str, context_id: str) -> CodeContextDeleteResponse:
        """Delete a code execution context"""
        response = self._make_agents_request("DELETE", f"sandboxes/{sandbox_id}/code/contexts/{context_id}")
        result = response.json()
        return CodeContextDeleteResponse(**result)


class SandboxTemplates:
    """Sandbox Templates resource for synchronous client"""

    def __init__(self, client):
        self.client = client

    def _make_agents_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a request to the agents API (/v1/agents/...)"""
        return self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    def list(self, limit: Optional[int] = 100, offset: Optional[int] = 0) -> TemplateList:
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

        response = self._make_agents_request("GET", endpoint)
        result = response.json()

        templates = [Template(**template) for template in result["templates"]]
        return TemplateList(templates=templates, limit=result["limit"], offset=result["offset"])


class SandboxResource:
    """Main Sandbox resource that contains sandboxes and templates"""

    def __init__(self, client):
        self.client = client
        self.sandboxes = Sandboxes(client)
        self.templates = SandboxTemplates(client)
