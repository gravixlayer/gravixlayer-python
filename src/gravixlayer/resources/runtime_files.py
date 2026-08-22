"""
Nested filesystem API: ``client.runtime.file.read``, ``.write``, ``.delete``, etc.

Text writes use ``write`` (JSON API). Multipart upload uses ``upload``; batch multipart
uses ``write_many``.
"""

from __future__ import annotations

import asyncio
import contextvars
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncIterator, BinaryIO, Callable, Dict, Iterator, List, Optional, Union
from urllib.parse import urlencode

from ..types.exceptions import GravixLayerConnectionError, GravixLayerError
from ..types.runtime import (
    ChangeOwnerResponse,
    DirectoryCreateResponse,
    FileCopyResponse,
    FileDeleteResponse,
    FileFindResponse,
    FileGetInfoResponse,
    FileInfo,
    FileListResponse,
    FileMoveResponse,
    FileReadResponse,
    FileReplaceResponse,
    FileUploadResponse,
    FileWriteResponse,
    SetPermissionsResponse,
    WatchEvent,
    WriteEntry,
    WriteFilesResponse,
    WriteResult,
    _validate_path,
    _validate_runtime_id,
)


#: How many files ``write_many`` sends at the same time.
DEFAULT_WRITE_CONCURRENCY = 8


def _format_mode(mode: int) -> str:
    """Render permission bits the way the API parses them: four octal digits."""
    return format(mode, "04o")


def _write_many_failure(entry: WriteEntry, error: GravixLayerError) -> WriteResult:
    return WriteResult(
        path=entry.path,
        name=os.path.basename(entry.path),
        type="file",
        error=str(error),
    )


def _validate_write_many(entries: List[WriteEntry], runtime_id: str, concurrency: int) -> None:
    _validate_runtime_id(runtime_id)
    for entry in entries:
        _validate_path(entry.path)
    if concurrency <= 0:
        raise ValueError("concurrency must be positive")


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


def _optional_file_info(payload: Optional[Dict[str, Any]]) -> Optional[FileInfo]:
    if not isinstance(payload, dict) or not payload:
        return None
    return _file_info_from_dict(payload)


def _find_payload(
    path: str,
    pattern: Optional[str],
    glob: Optional[str],
    regex: bool,
    case_sensitive: bool,
    include_hidden: bool,
    max_results: Optional[int],
    max_depth: Optional[int],
) -> Dict[str, Any]:
    """Validate and build the ``files/find`` request body."""
    _validate_path(path)
    if not pattern and not glob:
        raise ValueError("at least one of pattern or glob must be provided")
    payload: Dict[str, Any] = {
        "path": path,
        "regex": bool(regex),
        "case_sensitive": bool(case_sensitive),
        "include_hidden": bool(include_hidden),
    }
    if pattern:
        payload["pattern"] = pattern
    if glob:
        payload["glob"] = glob
    if max_results is not None:
        if max_results <= 0:
            raise ValueError("max_results must be positive")
        payload["max_results"] = int(max_results)
    if max_depth is not None:
        if max_depth <= 0:
            raise ValueError("max_depth must be positive")
        payload["max_depth"] = int(max_depth)
    return payload


def _replace_payload(
    path: str,
    pattern: str,
    replacement: str,
    glob: Optional[str],
    regex: bool,
    case_sensitive: bool,
    include_hidden: bool,
    max_depth: Optional[int],
    dry_run: bool,
) -> Dict[str, Any]:
    """Validate and build the ``files/replace`` request body."""
    _validate_path(path)
    if not pattern:
        raise ValueError("pattern must not be empty")
    payload: Dict[str, Any] = {
        "path": path,
        "pattern": pattern,
        "replacement": replacement,
        "regex": bool(regex),
        "case_sensitive": bool(case_sensitive),
        "include_hidden": bool(include_hidden),
        "dry_run": bool(dry_run),
    }
    if glob:
        payload["glob"] = glob
    if max_depth is not None:
        if max_depth <= 0:
            raise ValueError("max_depth must be positive")
        payload["max_depth"] = int(max_depth)
    return payload


def _iter_sse_payloads(lines: Any) -> Iterator[str]:
    """Yield the JSON body of each ``data:`` frame in an SSE line iterator."""
    for line in lines:
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if payload:
            yield payload


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
            params["mode"] = _format_mode(mode)
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
        concurrency: int = DEFAULT_WRITE_CONCURRENCY,
    ) -> WriteFilesResponse:
        """Write several files, each to its own destination path.

        Every entry names its own absolute destination and may carry its own
        permission bits. Entries are sent concurrently, ``concurrency`` at a
        time, and the results come back in the order the entries were given.

        When some files are written and others are rejected, ``partial_failure``
        is set and each rejected entry carries its own ``error``. When every
        entry is rejected, the first failure is raised, since that means the
        batch as a whole did not apply.
        """
        if not entries:
            return WriteFilesResponse(files=[], partial_failure=False)
        _validate_write_many(entries, runtime_id, concurrency)

        paths = [entry.path for entry in entries]
        results: List[Optional[WriteResult]] = [None] * len(entries)
        failures: List[Optional[GravixLayerError]] = [None] * len(entries)

        def write_one(index: int) -> None:
            entry = entries[index]
            try:
                results[index] = self.upload(
                    runtime_id, entry.path, entry.data, user=user, mode=entry.mode
                )
            except GravixLayerConnectionError:
                # The transport failed, so this says nothing about one file.
                raise
            except GravixLayerError as error:
                failures[index] = error
                results[index] = _write_many_failure(entry, error)

        from .. import telemetry

        with telemetry.runtime_span(
            "file.write_many",
            runtime_id,
            inputs={"count": len(entries), "paths": paths[:32], "user": user},
        ) as span:
            workers = min(concurrency, len(entries))
            if workers == 1:
                for index in range(len(entries)):
                    write_one(index)
            else:
                # Each worker runs under its own copy of the calling context so
                # that the spans it opens stay children of this one. The copies
                # are taken here, on the calling thread, because a single
                # context cannot be entered from two threads at once.
                contexts = [contextvars.copy_context() for _ in entries]
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [
                        pool.submit(contexts[index].run, write_one, index)
                        for index in range(len(entries))
                    ]
                    for future in futures:
                        future.result()

            file_results = [result for result in results if result is not None]
            failed = [error for error in failures if error is not None]
            if len(failed) == len(entries):
                raise failed[0]

            partial_failure = bool(failed)
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

    def move(
        self, runtime_id: str, source: str, destination: str, overwrite: bool = False
    ) -> FileMoveResponse:
        """Move or rename a path inside the runtime.

        Uses the guest's native ``rename`` syscall when source and destination share a
        filesystem, falling back to a copy plus unlink across filesystems.

        Args:
            runtime_id: Target runtime ID.
            source: Existing absolute path.
            destination: New absolute path.
            overwrite: Replace ``destination`` if it already exists.
        """
        _validate_runtime_id(runtime_id)
        _validate_path(source)
        _validate_path(destination)
        payload = {"source": source, "destination": destination, "overwrite": overwrite}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.move",
            runtime_id,
            inputs={"source": source, "destination": destination, "overwrite": overwrite},
            attributes={"file.path": source},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/move", payload)
            result = response.json()
            moved = FileMoveResponse(
                success=bool(result.get("success", True)),
                source=source,
                destination=destination,
                entry=_optional_file_info(result.get("entry")),
            )
            if span is not None:
                telemetry.record_outputs(span, {"destination": destination, "success": moved.success})
            return moved

    def copy(
        self,
        runtime_id: str,
        source: str,
        destination: str,
        recursive: bool = False,
        overwrite: bool = False,
    ) -> FileCopyResponse:
        """Copy a file or directory inside the runtime.

        Args:
            runtime_id: Target runtime ID.
            source: Existing absolute path.
            destination: Destination absolute path.
            recursive: Required to copy a directory tree.
            overwrite: Replace ``destination`` if it already exists.
        """
        _validate_runtime_id(runtime_id)
        _validate_path(source)
        _validate_path(destination)
        payload = {
            "source": source,
            "destination": destination,
            "recursive": recursive,
            "overwrite": overwrite,
        }
        from .. import telemetry

        with telemetry.runtime_span(
            "file.copy",
            runtime_id,
            inputs={"source": source, "destination": destination, "recursive": recursive},
            attributes={"file.path": source},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/copy", payload)
            result = response.json()
            copied = FileCopyResponse(
                success=bool(result.get("success", True)),
                source=source,
                destination=destination,
                entry=_optional_file_info(result.get("entry")),
            )
            if span is not None:
                telemetry.record_outputs(span, {"destination": destination, "success": copied.success})
            return copied

    def chown(
        self,
        runtime_id: str,
        path: str,
        user: Optional[str] = None,
        group: Optional[str] = None,
        recursive: bool = False,
    ) -> ChangeOwnerResponse:
        """Change the owning user and/or group of a path.

        At least one of ``user`` or ``group`` must be supplied. Names are resolved
        inside the guest, so both names and numeric IDs are accepted.
        """
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        if not (user or group):
            raise ValueError("at least one of user or group must be provided")
        payload: Dict[str, Any] = {"path": path, "recursive": recursive}
        if user:
            payload["user"] = user
        if group:
            payload["group"] = group
        from .. import telemetry

        with telemetry.runtime_span(
            "file.chown",
            runtime_id,
            inputs={"path": path, "user": user, "group": group, "recursive": recursive},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/chown", payload)
            result = response.json()
            owner = ChangeOwnerResponse(
                success=bool(result.get("success", True)),
                path=path,
                message=str(result.get("message", "")),
            )
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "success": owner.success})
            return owner

    def watch(
        self,
        runtime_id: str,
        path: str,
        recursive: bool = False,
        on_event: Optional[Callable[[WatchEvent], None]] = None,
    ) -> Iterator[WatchEvent]:
        """Watch a directory for filesystem changes, backed by guest ``inotify``.

        Yields :class:`~gravixlayer.types.runtime.WatchEvent` objects as they occur.
        The first event is always ``start``, which confirms the watch is armed; only
        after receiving it are subsequent changes guaranteed to be observed.

        The stream is open ended: iterate it for as long as you want notifications and
        break out (or close the generator) to stop watching. The underlying HTTP
        response is always released.

        Args:
            runtime_id: Target runtime ID.
            path: Absolute directory path to watch.
            recursive: Also watch subdirectories, including ones created later.
            on_event: Optional callable invoked with each event before it is yielded.

        Example:
            >>> for event in client.runtime.file.watch(rid, "/workspace", recursive=True):
            ...     if event.type == "write":
            ...         print("changed:", event.path)
        """
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path, "recursive": recursive}
        return self._watch_stream(runtime_id, payload, on_event)

    def _watch_stream(
        self,
        runtime_id: str,
        payload: Dict[str, Any],
        on_event: Optional[Callable[[WatchEvent], None]],
    ) -> Iterator[WatchEvent]:
        import json

        response = self._req("POST", f"runtime/{runtime_id}/files/watch", payload, stream=True)
        try:
            for raw in _iter_sse_payloads(response.iter_lines()):
                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if evt.get("type") == "error":
                    raise RuntimeError(str(evt.get("message") or "filesystem watch failed"))
                event = WatchEvent.from_api(evt)
                if on_event is not None:
                    on_event(event)
                yield event
        finally:
            response.close()

    def find(
        self,
        runtime_id: str,
        path: str,
        pattern: Optional[str] = None,
        glob: Optional[str] = None,
        *,
        regex: bool = False,
        case_sensitive: bool = False,
        include_hidden: bool = False,
        max_results: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> FileFindResponse:
        """Find files by name glob and/or content pattern.

        The search runs natively inside the guest: no shell, no ``find`` and no
        ``grep`` process is spawned. Binary files and files above the guest's size
        ceiling are skipped, and directory symlinks are never followed.

        Supply ``glob`` to select which files are considered (``"*.py"``), and/or
        ``pattern`` to match their contents. With ``glob`` alone you get one match
        per file with ``line == 0``. With ``pattern`` you get one match per matching
        line.

        Args:
            runtime_id: Target runtime ID.
            path: Absolute directory to search under.
            pattern: Content pattern. Literal by default; set ``regex`` for a regex.
            glob: Shell-style name pattern applied to the path relative to ``path``.
            regex: Treat ``pattern`` as a regular expression.
            case_sensitive: Match case exactly. Defaults to case-insensitive.
            include_hidden: Descend into and match dot-files.
            max_results: Stop after this many matches. Server-capped.
            max_depth: Directory recursion limit. Server-capped.

        Returns:
            :class:`~gravixlayer.types.runtime.FileFindResponse`.

        Example:
            >>> hits = client.runtime.file.find(rid, "/workspace", "TODO", glob="*.py")
            >>> for m in hits:
            ...     print(f"{m.path}:{m.line}: {m.content}")
        """
        _validate_runtime_id(runtime_id)
        payload = _find_payload(
            path, pattern, glob, regex, case_sensitive, include_hidden, max_results, max_depth
        )
        from .. import telemetry

        with telemetry.runtime_span(
            "file.find",
            runtime_id,
            inputs={"path": path, "pattern": pattern, "glob": glob, "regex": regex},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/find", payload)
            found = FileFindResponse.from_api(response.json())
            if span is not None:
                telemetry.record_outputs(
                    span,
                    {
                        "matches": len(found.matches),
                        "truncated": found.truncated,
                        "files_scanned": found.files_scanned,
                    },
                )
            return found

    def replace(
        self,
        runtime_id: str,
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
    ) -> FileReplaceResponse:
        """Replace a pattern across every matching file, in place.

        Each file is rewritten through a temporary sibling and renamed into place,
        so a reader never observes a partially written file. Mode and ownership are
        preserved. Set ``dry_run`` to count replacements without writing anything.

        Args:
            runtime_id: Target runtime ID.
            path: Absolute directory to search under.
            pattern: Pattern to replace. Literal by default; set ``regex`` for a regex.
            replacement: Replacement text. With ``regex`` it may reference capture
                groups as ``$1``; without it the text is inserted verbatim.
            glob: Shell-style name pattern limiting which files are rewritten.
            regex: Treat ``pattern`` as a regular expression.
            case_sensitive: Match case exactly. Defaults to case-insensitive.
            include_hidden: Descend into and match dot-files.
            max_depth: Directory recursion limit. Server-capped.
            dry_run: Report counts without modifying any file.

        Returns:
            :class:`~gravixlayer.types.runtime.FileReplaceResponse`.

        Example:
            >>> res = client.runtime.file.replace(rid, "/workspace", "v1", "v2", glob="*.py")
            >>> print(res.total_replacements, "replacements in", len(res.files), "files")
        """
        _validate_runtime_id(runtime_id)
        payload = _replace_payload(
            path, pattern, replacement, glob, regex, case_sensitive, include_hidden, max_depth, dry_run
        )
        from .. import telemetry

        with telemetry.runtime_span(
            "file.replace",
            runtime_id,
            inputs={"path": path, "pattern": pattern, "glob": glob, "dry_run": dry_run},
            attributes={"file.path": path},
        ) as span:
            response = self._req("POST", f"runtime/{runtime_id}/files/replace", payload)
            replaced = FileReplaceResponse.from_api(response.json())
            if span is not None:
                telemetry.record_outputs(
                    span,
                    {
                        "files": len(replaced.files),
                        "total_replacements": replaced.total_replacements,
                        "files_scanned": replaced.files_scanned,
                    },
                )
            return replaced

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
            params["mode"] = _format_mode(mode)
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
        concurrency: int = DEFAULT_WRITE_CONCURRENCY,
    ) -> WriteFilesResponse:
        """Write several files, each to its own destination path.

        Every entry names its own absolute destination and may carry its own
        permission bits. Entries are sent concurrently, ``concurrency`` at a
        time, and the results come back in the order the entries were given.

        When some files are written and others are rejected, ``partial_failure``
        is set and each rejected entry carries its own ``error``. When every
        entry is rejected, the first failure is raised, since that means the
        batch as a whole did not apply.
        """
        if not entries:
            return WriteFilesResponse(files=[], partial_failure=False)
        _validate_write_many(entries, runtime_id, concurrency)

        paths = [entry.path for entry in entries]
        results: List[Optional[WriteResult]] = [None] * len(entries)
        failures: List[Optional[GravixLayerError]] = [None] * len(entries)
        limit = asyncio.Semaphore(min(concurrency, len(entries)))

        async def write_one(index: int) -> None:
            entry = entries[index]
            async with limit:
                try:
                    results[index] = await self.upload(
                        runtime_id, entry.path, entry.data, user=user, mode=entry.mode
                    )
                except GravixLayerConnectionError:
                    # The transport failed, so this says nothing about one file.
                    raise
                except GravixLayerError as error:
                    failures[index] = error
                    results[index] = _write_many_failure(entry, error)

        from .. import telemetry

        with telemetry.runtime_span(
            "file.write_many",
            runtime_id,
            inputs={"count": len(entries), "paths": paths[:32], "user": user},
        ) as span:
            await asyncio.gather(*(write_one(index) for index in range(len(entries))))

            file_results = [result for result in results if result is not None]
            failed = [error for error in failures if error is not None]
            if len(failed) == len(entries):
                raise failed[0]

            partial_failure = bool(failed)
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

    async def move(
        self, runtime_id: str, source: str, destination: str, overwrite: bool = False
    ) -> FileMoveResponse:
        """Move or rename a path inside the runtime."""
        _validate_runtime_id(runtime_id)
        _validate_path(source)
        _validate_path(destination)
        payload = {"source": source, "destination": destination, "overwrite": overwrite}
        from .. import telemetry

        with telemetry.runtime_span(
            "file.move",
            runtime_id,
            inputs={"source": source, "destination": destination, "overwrite": overwrite},
            attributes={"file.path": source},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/move", payload)
            result = response.json()
            moved = FileMoveResponse(
                success=bool(result.get("success", True)),
                source=source,
                destination=destination,
                entry=_optional_file_info(result.get("entry")),
            )
            if span is not None:
                telemetry.record_outputs(span, {"destination": destination, "success": moved.success})
            return moved

    async def copy(
        self,
        runtime_id: str,
        source: str,
        destination: str,
        recursive: bool = False,
        overwrite: bool = False,
    ) -> FileCopyResponse:
        """Copy a file or directory inside the runtime."""
        _validate_runtime_id(runtime_id)
        _validate_path(source)
        _validate_path(destination)
        payload = {
            "source": source,
            "destination": destination,
            "recursive": recursive,
            "overwrite": overwrite,
        }
        from .. import telemetry

        with telemetry.runtime_span(
            "file.copy",
            runtime_id,
            inputs={"source": source, "destination": destination, "recursive": recursive},
            attributes={"file.path": source},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/copy", payload)
            result = response.json()
            copied = FileCopyResponse(
                success=bool(result.get("success", True)),
                source=source,
                destination=destination,
                entry=_optional_file_info(result.get("entry")),
            )
            if span is not None:
                telemetry.record_outputs(span, {"destination": destination, "success": copied.success})
            return copied

    async def chown(
        self,
        runtime_id: str,
        path: str,
        user: Optional[str] = None,
        group: Optional[str] = None,
        recursive: bool = False,
    ) -> ChangeOwnerResponse:
        """Change the owning user and/or group of a path."""
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        if not (user or group):
            raise ValueError("at least one of user or group must be provided")
        payload: Dict[str, Any] = {"path": path, "recursive": recursive}
        if user:
            payload["user"] = user
        if group:
            payload["group"] = group
        from .. import telemetry

        with telemetry.runtime_span(
            "file.chown",
            runtime_id,
            inputs={"path": path, "user": user, "group": group, "recursive": recursive},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/chown", payload)
            result = response.json()
            owner = ChangeOwnerResponse(
                success=bool(result.get("success", True)),
                path=path,
                message=str(result.get("message", "")),
            )
            if span is not None:
                telemetry.record_outputs(span, {"path": path, "success": owner.success})
            return owner

    async def watch(
        self,
        runtime_id: str,
        path: str,
        recursive: bool = False,
        on_event: Optional[Callable[[WatchEvent], Any]] = None,
    ) -> AsyncIterator[WatchEvent]:
        """Watch a directory for filesystem changes, backed by guest ``inotify``.

        Async generator yielding :class:`~gravixlayer.types.runtime.WatchEvent`. The
        first event is always ``start``. ``on_event`` may be a coroutine function.

        Example:
            >>> async for event in client.runtime.file.watch(rid, "/workspace"):
            ...     print(event.type, event.path)
        """
        import inspect
        import json

        _validate_runtime_id(runtime_id)
        _validate_path(path)
        payload = {"path": path, "recursive": recursive}

        response = await self._req(
            "POST", f"runtime/{runtime_id}/files/watch", payload, stream=True
        )
        try:
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[len("data:"):].strip()
                if not raw:
                    continue
                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if evt.get("type") == "error":
                    raise RuntimeError(str(evt.get("message") or "filesystem watch failed"))
                event = WatchEvent.from_api(evt)
                if on_event is not None:
                    maybe = on_event(event)
                    if inspect.isawaitable(maybe):
                        await maybe
                yield event
        finally:
            await response.aclose()

    async def find(
        self,
        runtime_id: str,
        path: str,
        pattern: Optional[str] = None,
        glob: Optional[str] = None,
        *,
        regex: bool = False,
        case_sensitive: bool = False,
        include_hidden: bool = False,
        max_results: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> FileFindResponse:
        """Find files by name glob and/or content pattern (native guest search)."""
        _validate_runtime_id(runtime_id)
        payload = _find_payload(
            path, pattern, glob, regex, case_sensitive, include_hidden, max_results, max_depth
        )
        from .. import telemetry

        with telemetry.runtime_span(
            "file.find",
            runtime_id,
            inputs={"path": path, "pattern": pattern, "glob": glob, "regex": regex},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/find", payload)
            found = FileFindResponse.from_api(response.json())
            if span is not None:
                telemetry.record_outputs(
                    span,
                    {
                        "matches": len(found.matches),
                        "truncated": found.truncated,
                        "files_scanned": found.files_scanned,
                    },
                )
            return found

    async def replace(
        self,
        runtime_id: str,
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
    ) -> FileReplaceResponse:
        """Replace a pattern across every matching file, atomically per file."""
        _validate_runtime_id(runtime_id)
        payload = _replace_payload(
            path, pattern, replacement, glob, regex, case_sensitive, include_hidden, max_depth, dry_run
        )
        from .. import telemetry

        with telemetry.runtime_span(
            "file.replace",
            runtime_id,
            inputs={"path": path, "pattern": pattern, "glob": glob, "dry_run": dry_run},
            attributes={"file.path": path},
        ) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/files/replace", payload)
            replaced = FileReplaceResponse.from_api(response.json())
            if span is not None:
                telemetry.record_outputs(
                    span,
                    {
                        "files": len(replaced.files),
                        "total_replacements": replaced.total_replacements,
                        "files_scanned": replaced.files_scanned,
                    },
                )
            return replaced

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
