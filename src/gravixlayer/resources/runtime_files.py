"""
Nested filesystem API: ``client.runtime.file.read``, ``.write``, ``.delete``, etc.

Text writes use ``write`` (JSON API). Multipart upload uses ``upload``; batch multipart
uses ``write_many``.
"""

from __future__ import annotations

import os
from typing import Any, BinaryIO, Dict, List, Optional, Union
from urllib.parse import urlencode

from ..types.runtime import (
    DirectoryCreateResponse,
    FileDeleteResponse,
    FileGetInfoResponse,
    FileInfo,
    FileListResponse,
    FileReadResponse,
    FileUploadResponse,
    FileWriteResponse,
    SetPermissionsResponse,
    WriteEntry,
    WriteFilesResponse,
    WriteResult,
    _validate_path,
    _validate_runtime_id,
)


def _file_info_from_dict(file_info: Dict[str, Any]) -> FileInfo:
    return FileInfo(
        name=file_info.get("name", ""),
        size=file_info.get("size", 0),
        is_dir=file_info.get("is_dir", False),
        modified_at=file_info.get("modified_at") or file_info.get("mod_time", ""),
        mode=file_info.get("mode"),
        path=file_info.get("path"),
        permissions=file_info.get("permissions"),
    )


class RuntimeFileResource:
    """Filesystem operations under ``client.runtime.file``."""

    def __init__(self, runtimes: Any):
        self._r = runtimes

    def _req(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any):
        return self._r._make_agents_request(method, endpoint, data, **kwargs)

    def read(self, runtime_id: str, path: str) -> FileReadResponse:
        """Read file contents from the runtime."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        data = {"path": path}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.read",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/read", data)
            result = response.json()
            content = result.get("content", "")
            if result.get("path") is None:
                result["path"] = path
            if result.get("size") is None and isinstance(content, str):
                result["size"] = len(content.encode("utf-8"))
            if span is not None:
                size = result.get("size")
                if size is None and isinstance(content, str):
                    size = len(content.encode("utf-8"))
                telemetry.record_outputs(span, {"path": path, "size": size})
            return FileReadResponse(**result)

    def write(self, runtime_id: str, path: str, content: str) -> FileWriteResponse:
        """Write text content via JSON API (``POST .../files/write``)."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path, "content": content}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.write",
            runtime_id,
            inputs={"path": path, "size": len(content)},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/write", payload)
            result = response.json()
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "size": len(content)})
            return FileWriteResponse(**result)

    def delete(self, runtime_id: str, path: str) -> FileDeleteResponse:
        """Delete a file or directory."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.delete",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/delete", payload)
            result = response.json()
            if span is not None:
                telemetry.record_outputs(span, {"path": path})
            return FileDeleteResponse(**result)

    def list(self, runtime_id: str, path: str) -> FileListResponse:
        """List files and directories at ``path``."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.list",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/list", payload)
            result = response.json()
            files = [_file_info_from_dict(f) for f in result.get("files", ())]
            if span is not None:
                telemetry.record_outputs(
                    span,
                    {"path": path, "count": len(files), "names": [f.name for f in files[:32]]},
                )
            return FileListResponse(files=files)

    def upload(
        self,
        runtime_id: str,
        path: str,
        data: Union[str, bytes, BinaryIO],
        user: Optional[str] = None,
        mode: Optional[int] = None,
    ) -> WriteResult:
        """Write raw content via multipart upload (``POST .../files``)."""
        _validate_runtime_id(runtime_id)
        content = self._coerce_to_bytes(data)
        filename = os.path.basename(path)
        params: Dict[str, str] = {"path": path}
        if user:
            params["username"] = user
        if mode is not None:
            params["mode"] = oct(mode)
        endpoint = f"runtime/{runtime_id}/files?{urlencode(params)}"
        files = {"file": (filename, content, "application/octet-stream")}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.upload",
            runtime_id,
            inputs={"path": path, "size": len(content), "user": user, "mode": mode},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", endpoint, data=None, files=files)
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                entry = result[0]
                written = WriteResult(
                    path=entry.get("path", path),
                    name=entry.get("name", filename),
                    type=entry.get("type", "file"),
                    size=len(content),
                )
            else:
                written = WriteResult(path=path, name=filename, type="file", size=len(content))
            if span is not None:
                telemetry.record_outputs(
                    span, {"path": written.path, "size": written.size, "name": written.name}
                )
            return written

    def write_many(
        self,
        runtime_id: str,
        entries: List[WriteEntry],
        user: Optional[str] = None,
    ) -> WriteFilesResponse:
        """Write multiple files in one multipart request."""
        if not entries:
            return WriteFilesResponse(files=[], partial_failure=False)
        multipart_files = []
        paths: List[str] = []
        for entry in entries:
            content = self._coerce_to_bytes(entry.data)
            multipart_files.append(("file", (entry.path, content, "application/octet-stream")))
            paths.append(entry.path)
        params: Dict[str, str] = {}
        if user:
            params["username"] = user
        query = f"?{urlencode(params)}" if params else ""
        endpoint = f"runtime/{runtime_id}/files{query}"
        from .. import telemetry

        with telemetry.runtime_span(
            "file.write_many",
            runtime_id,
            inputs={"count": len(entries), "paths": paths[:32], "user": user},
        ) as span:
            response = self._req("POST", endpoint, data=None, files=multipart_files)
            result = response.json()
            partial_failure = response.status_code == 207
            file_results: List[WriteResult] = []
            if isinstance(result, list):
                for entry_result in result:
                    file_results.append(
                        WriteResult(
                            path=entry_result.get("path", ""),
                            name=entry_result.get("name", ""),
                            type=entry_result.get("type", "file"),
                            error=entry_result.get("error"),
                        )
                    )
            elif isinstance(result, dict) and "files" in result:
                for entry_result in result["files"]:
                    file_results.append(
                        WriteResult(
                            path=entry_result.get("path", ""),
                            name=entry_result.get("name", ""),
                            type=entry_result.get("type", "file"),
                            error=entry_result.get("error"),
                        )
                    )
            written = WriteFilesResponse(files=file_results, partial_failure=partial_failure)
            if span is not None:
                telemetry.record_outputs(
                    span,
                    {
                        "count": len(file_results),
                        "partial_failure": partial_failure,
                        "paths": [f.path for f in file_results[:32]],
                    },
                )
                if partial_failure:
                    telemetry.mark_span_error(span, "partial_failure")
            return written

    def create_directory(
        self,
        runtime_id: str,
        path: str,
        *,
        recursive: bool = True,
        mode: Optional[str] = None,
    ) -> DirectoryCreateResponse:
        """Create a directory using the native filesystem path (no shell ``mkdir``)."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload: Dict[str, Any] = {"path": path, "recursive": recursive}
        if mode is not None:
            payload["mode"] = mode
        from .. import telemetry

        with telemetry.runtime_span(
            "file.create_directory",
            runtime_id,
            inputs={"path": path, "recursive": recursive, "mode": mode},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/create-directory", payload)
            result = response.json()
            created = DirectoryCreateResponse(
                message=str(result.get("message", "Directory created successfully")),
                path=result.get("path", path),
                success=result.get("success"),
            )
            if span is not None:
                telemetry.record_outputs(
                    span, {"path": created.path, "success": created.success, "message": created.message}
                )
            return created

    def get_info(self, runtime_id: str, path: str) -> FileGetInfoResponse:
        """Return stat metadata (permissions, size, mtime, etc.) for a path."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.get_info",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/info", payload)
            result = response.json()
            if not result.get("exists"):
                info = FileGetInfoResponse(exists=False, info=None)
            else:
                info_raw = result.get("info") or {}
                info = FileGetInfoResponse(exists=True, info=_file_info_from_dict(info_raw))
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "exists": info.exists})
            return info

    def set_permissions(self, runtime_id: str, path: str, mode: str) -> SetPermissionsResponse:
        """Set Unix permission bits using an octal string (e.g. ``\"644\"`` or ``\"0755\"``)."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        if not str(mode).strip():
            raise ValueError("mode must be a non-empty chmod-style octal string")
        payload = {"path": path, "mode": mode}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.set_permissions",
            runtime_id,
            inputs={"path": path, "mode": mode},
            attributes={"file.path": path, "file.mode": mode},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/set-mode", payload)
            result = response.json()
            perms = SetPermissionsResponse(
                message=str(result.get("message", "")), success=bool(result.get("success", True))
            )
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "mode": mode, "success": perms.success})
            return perms

    def upload_file(self, runtime_id: str, file: BinaryIO, path: Optional[str] = None) -> FileUploadResponse:
        _validate_runtime_id(runtime_id)
        data = {}
        if path:
            data["path"] = path
        files = {"file": file}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.upload_file",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path or ""},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/upload", data=data, files=files)
            result = response.json()
            uploaded = FileUploadResponse(**result)
            if span is not None:
                telemetry.record_outputs(span, {"path": path or getattr(uploaded, "path", None)})
            return uploaded

    def download_file(self, runtime_id: str, path: str) -> bytes:
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        endpoint = f"runtime/{runtime_id}/download?{urlencode({'path': path})}"
        from .. import telemetry

        with telemetry.runtime_span(
            "file.download",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = self._req("GET", endpoint)
            content = response.content
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "size": len(content)})
            return content

    @staticmethod
    def _coerce_to_bytes(data: Union[str, bytes, BinaryIO]) -> bytes:
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, bytes):
            return data
        if hasattr(data, "read"):
            return data.read()
        raise TypeError(f"Expected str, bytes, or file-like object, got {type(data).__name__}")


class AsyncRuntimeFileResource:
    """Async filesystem operations under ``await client.runtime.file.*``."""

    def __init__(self, runtimes: Any):
        self._r = runtimes

    async def _req(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any):
        return await self._r._make_agents_request(method, endpoint, data, **kwargs)

    async def read(self, runtime_id: str, path: str) -> FileReadResponse:
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.read",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/read", payload)
            result = response.json()
            content = result.get("content", "")
            if result.get("path") is None:
                result["path"] = path
            if result.get("size") is None and isinstance(content, str):
                result["size"] = len(content.encode("utf-8"))
            if span is not None:
                size = result.get("size")
                if size is None and isinstance(content, str):
                    size = len(content.encode("utf-8"))
                telemetry.record_outputs(span, {"path": path, "size": size})
            return FileReadResponse(**result)

    async def write(self, runtime_id: str, path: str, content: str) -> FileWriteResponse:
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path, "content": content}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.write",
            runtime_id,
            inputs={"path": path, "size": len(content)},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/write", payload)
            result = response.json()
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "size": len(content)})
            return FileWriteResponse(**result)

    async def delete(self, runtime_id: str, path: str) -> FileDeleteResponse:
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.delete",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/delete", payload)
            result = response.json()
            if span is not None:
                telemetry.record_outputs(span, {"path": path})
            return FileDeleteResponse(**result)

    async def list(self, runtime_id: str, path: str) -> FileListResponse:
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.list",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/list", payload)
            result = response.json()
            files = [_file_info_from_dict(f) for f in result.get("files", ())]
            if span is not None:
                telemetry.record_outputs(
                    span,
                    {"path": path, "count": len(files), "names": [f.name for f in files[:32]]},
                )
            return FileListResponse(files=files)

    async def upload(
        self,
        runtime_id: str,
        path: str,
        data: Union[str, bytes, BinaryIO],
        user: Optional[str] = None,
        mode: Optional[int] = None,
    ) -> WriteResult:
        _validate_runtime_id(runtime_id)
        content = self._coerce_to_bytes(data)
        filename = os.path.basename(path)
        params: Dict[str, str] = {"path": path}
        if user:
            params["username"] = user
        if mode is not None:
            params["mode"] = oct(mode)
        endpoint = f"runtime/{runtime_id}/files?{urlencode(params)}"
        files = {"file": (filename, content, "application/octet-stream")}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.upload",
            runtime_id,
            inputs={"path": path, "size": len(content), "user": user, "mode": mode},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", endpoint, data=None, files=files)
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                entry = result[0]
                written = WriteResult(
                    path=entry.get("path", path),
                    name=entry.get("name", filename),
                    type=entry.get("type", "file"),
                    size=len(content),
                )
            else:
                written = WriteResult(path=path, name=filename, type="file", size=len(content))
            if span is not None:
                telemetry.record_outputs(
                    span, {"path": written.path, "size": written.size, "name": written.name}
                )
            return written

    async def write_many(
        self,
        runtime_id: str,
        entries: List[WriteEntry],
        user: Optional[str] = None,
    ) -> WriteFilesResponse:
        if not entries:
            return WriteFilesResponse(files=[], partial_failure=False)
        multipart_files = []
        paths: List[str] = []
        for entry in entries:
            content = self._coerce_to_bytes(entry.data)
            multipart_files.append(("file", (entry.path, content, "application/octet-stream")))
            paths.append(entry.path)
        params: Dict[str, str] = {}
        if user:
            params["username"] = user
        query = f"?{urlencode(params)}" if params else ""
        endpoint = f"runtime/{runtime_id}/files{query}"
        from .. import telemetry

        with telemetry.runtime_span(
            "file.write_many",
            runtime_id,
            inputs={"count": len(entries), "paths": paths[:32], "user": user},
        ) as span:
            response = await self._req("POST", endpoint, data=None, files=multipart_files)
            result = response.json()
            partial_failure = response.status_code == 207
            file_results: List[WriteResult] = []
            if isinstance(result, list):
                for entry_result in result:
                    file_results.append(
                        WriteResult(
                            path=entry_result.get("path", ""),
                            name=entry_result.get("name", ""),
                            type=entry_result.get("type", "file"),
                            error=entry_result.get("error"),
                        )
                    )
            elif isinstance(result, dict) and "files" in result:
                for entry_result in result["files"]:
                    file_results.append(
                        WriteResult(
                            path=entry_result.get("path", ""),
                            name=entry_result.get("name", ""),
                            type=entry_result.get("type", "file"),
                            error=entry_result.get("error"),
                        )
                    )
            written = WriteFilesResponse(files=file_results, partial_failure=partial_failure)
            if span is not None:
                telemetry.record_outputs(
                    span,
                    {
                        "count": len(file_results),
                        "partial_failure": partial_failure,
                        "paths": [f.path for f in file_results[:32]],
                    },
                )
                if partial_failure:
                    telemetry.mark_span_error(span, "partial_failure")
            return written

    async def create_directory(
        self,
        runtime_id: str,
        path: str,
        *,
        recursive: bool = True,
        mode: Optional[str] = None,
    ) -> DirectoryCreateResponse:
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload: Dict[str, Any] = {"path": path, "recursive": recursive}
        if mode is not None:
            payload["mode"] = mode
        from .. import telemetry

        with telemetry.runtime_span(
            "file.create_directory",
            runtime_id,
            inputs={"path": path, "recursive": recursive, "mode": mode},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/create-directory", payload)
            result = response.json()
            created = DirectoryCreateResponse(
                message=str(result.get("message", "Directory created successfully")),
                path=result.get("path", path),
                success=result.get("success"),
            )
            if span is not None:
                telemetry.record_outputs(
                    span, {"path": created.path, "success": created.success, "message": created.message}
                )
            return created

    async def get_info(self, runtime_id: str, path: str) -> FileGetInfoResponse:
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.get_info",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/info", payload)
            result = response.json()
            if not result.get("exists"):
                info = FileGetInfoResponse(exists=False, info=None)
            else:
                info_raw = result.get("info") or {}
                info = FileGetInfoResponse(exists=True, info=_file_info_from_dict(info_raw))
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "exists": info.exists})
            return info

    async def set_permissions(self, runtime_id: str, path: str, mode: str) -> SetPermissionsResponse:
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        if not str(mode).strip():
            raise ValueError("mode must be a non-empty chmod-style octal string")
        payload = {"path": path, "mode": mode}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.set_permissions",
            runtime_id,
            inputs={"path": path, "mode": mode},
            attributes={"file.path": path, "file.mode": mode},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/set-mode", payload)
            result = response.json()
            perms = SetPermissionsResponse(
                message=str(result.get("message", "")), success=bool(result.get("success", True))
            )
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "mode": mode, "success": perms.success})
            return perms

    async def upload_file(self, runtime_id: str, file: BinaryIO, path: Optional[str] = None) -> FileUploadResponse:
        _validate_runtime_id(runtime_id)
        data = {}
        if path:
            data["path"] = path
        files = {"file": file}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.upload_file",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path or ""},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/upload", data=data, files=files)
            result = response.json()
            uploaded = FileUploadResponse(**result)
            if span is not None:
                telemetry.record_outputs(span, {"path": path or getattr(uploaded, "path", None)})
            return uploaded

    async def download_file(self, runtime_id: str, path: str) -> bytes:
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        endpoint = f"runtime/{runtime_id}/download?{urlencode({'path': path})}"
        from .. import telemetry

        with telemetry.runtime_span(
            "file.download",
            runtime_id,
            inputs={"path": path},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("GET", endpoint)
            content = response.content
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "size": len(content)})
            return content

    @staticmethod
    def _coerce_to_bytes(data: Union[str, bytes, BinaryIO]) -> bytes:
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, bytes):
            return data
        if hasattr(data, "read"):
            return data.read()
        raise TypeError(f"Expected str, bytes, or file-like object, got {type(data).__name__}")
