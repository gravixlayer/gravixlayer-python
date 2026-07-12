"""
Git sub-resource for runtime API: ``client.runtime.git.clone(...)``, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from ..types.runtime import GitOperationResult, _validate_path, _validate_runtime_id

if TYPE_CHECKING:
    from .runtime import Runtimes
    from .async_runtime import AsyncRuntimes


def _record_git_result(span: Any, result: GitOperationResult) -> None:
    """Attach git exit metadata to the active span."""
    if span is None:
        return
    from .. import telemetry

    telemetry.record_outputs(
        span,
        {
            "success": result.success,
            "exit_code": result.exit_code,
            "stdout_preview": (result.stdout[:500] + "...") if len(result.stdout) > 500 else result.stdout,
            "stderr_preview": (result.stderr[:500] + "...") if len(result.stderr) > 500 else result.stderr,
            "error": result.error or None,
        },
    )
    span.set_attribute("process.exit_code", int(result.exit_code))
    if not result.success:
        telemetry.mark_span_error(span, result.error or f"exit_code={result.exit_code}")


class RuntimeGitResource:
    """Git operations on runtimes (sync). Use ``client.runtime.git.clone(...)``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "Runtimes"):
        self._rt = runtimes

    def _call(
        self,
        operation: str,
        runtime_id: str,
        endpoint: str,
        data: Dict[str, Any],
        inputs: Mapping[str, Any],
        *,
        attributes: Optional[Mapping[str, Any]] = None,
    ) -> GitOperationResult:
        from .. import telemetry

        with telemetry.runtime_span(
            f"git.{operation}",
            runtime_id,
            inputs=dict(inputs),
            attributes=dict(attributes) if attributes else None,
        ) as span:
            response = self._rt._make_agents_request("POST", endpoint, data)
            result = GitOperationResult.from_api(response.json())
            _record_git_result(span, result)
            return result

    def clone(
        self,
        runtime_id: str,
        url: str,
        path: str,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        auth_token: Optional[str] = None,
    ) -> GitOperationResult:
        """Clone a repository into the runtime.

        ``url`` must use an allowed form (enforced by the API): ``http://``, ``https://``,
        ``ssh://``, ``git://``, or SCP-style SSH such as ``git@github.com:org/repo.git``.
        ``file://`` and other schemes are rejected. For private HTTPS repos, pass
        ``auth_token`` (sent as embedded credentials for that clone only).
        """
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        data: Dict[str, Any] = {"url": url, "path": path}
        if branch is not None:
            data["branch"] = branch
        if depth is not None:
            data["depth"] = int(depth)
        if auth_token is not None:
            data["auth_token"] = auth_token
        # Never put auth_token in span inputs (even with redaction).
        return self._call(
            "clone",
            runtime_id,
            f"runtime/{runtime_id}/git/clone",
            data,
            {"url": url, "path": path, "branch": branch, "depth": depth, "auth": bool(auth_token)},
            attributes={"git.repository_url": url, "file.path": path},
        )

    def status(self, runtime_id: str, repository_path: str) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data = {"repository_path": repository_path}
        return self._call(
            "status",
            runtime_id,
            f"runtime/{runtime_id}/git/status",
            data,
            {"repository_path": repository_path},
            attributes={"file.path": repository_path},
        )

    def branch_list(
        self,
        runtime_id: str,
        repository_path: str,
        scope: Optional[str] = None,
    ) -> GitOperationResult:
        """List branches: local (default), ``remote`` (``git branch -r``), or ``all`` (``git branch -a``)."""
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if scope is not None:
            data["scope"] = scope
        return self._call(
            "branch_list",
            runtime_id,
            f"runtime/{runtime_id}/git/branches",
            data,
            {"repository_path": repository_path, "scope": scope},
            attributes={"file.path": repository_path},
        )

    def checkout(
        self, runtime_id: str, repository_path: str, ref_name: str
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data = {"repository_path": repository_path, "ref_name": ref_name}
        return self._call(
            "checkout",
            runtime_id,
            f"runtime/{runtime_id}/git/checkout",
            data,
            {"repository_path": repository_path, "ref_name": ref_name},
            attributes={"file.path": repository_path, "git.ref": ref_name},
        )

    def pull(
        self,
        runtime_id: str,
        repository_path: str,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if remote is not None:
            data["remote"] = remote
        if branch is not None:
            data["branch"] = branch
        return self._call(
            "pull",
            runtime_id,
            f"runtime/{runtime_id}/git/pull",
            data,
            {"repository_path": repository_path, "remote": remote, "branch": branch},
            attributes={"file.path": repository_path},
        )

    def push(
        self,
        runtime_id: str,
        repository_path: str,
        remote: Optional[str] = None,
        refspec: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if remote is not None:
            data["remote"] = remote
        if refspec is not None:
            data["refspec"] = refspec
        if username is not None:
            data["username"] = username
        if password is not None:
            data["password"] = password
        return self._call(
            "push",
            runtime_id,
            f"runtime/{runtime_id}/git/push",
            data,
            {
                "repository_path": repository_path,
                "remote": remote,
                "refspec": refspec,
                "auth": bool(username or password),
            },
            attributes={"file.path": repository_path},
        )

    def fetch(
        self, runtime_id: str, repository_path: str, remote: Optional[str] = None
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if remote is not None:
            data["remote"] = remote
        return self._call(
            "fetch",
            runtime_id,
            f"runtime/{runtime_id}/git/fetch",
            data,
            {"repository_path": repository_path, "remote": remote},
            attributes={"file.path": repository_path},
        )

    def add(
        self, runtime_id: str, repository_path: str, paths: Optional[List[str]] = None
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if paths is not None:
            data["paths"] = paths
        return self._call(
            "add",
            runtime_id,
            f"runtime/{runtime_id}/git/add",
            data,
            {"repository_path": repository_path, "paths": paths},
            attributes={"file.path": repository_path},
        )

    def commit(
        self,
        runtime_id: str,
        repository_path: str,
        message: str,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
        allow_empty: Optional[bool] = None,
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path, "message": message}
        if author_name is not None:
            data["author_name"] = author_name
        if author_email is not None:
            data["author_email"] = author_email
        if allow_empty is not None:
            data["allow_empty"] = allow_empty
        return self._call(
            "commit",
            runtime_id,
            f"runtime/{runtime_id}/git/commit",
            data,
            {
                "repository_path": repository_path,
                "message": message,
                "author_name": author_name,
                "allow_empty": allow_empty,
            },
            attributes={"file.path": repository_path},
        )

    def create_branch(
        self,
        runtime_id: str,
        repository_path: str,
        branch_name: str,
        start_point: Optional[str] = None,
    ) -> GitOperationResult:
        """Create a branch: ``git branch <name> [start_point]``."""
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {
            "repository_path": repository_path,
            "branch_name": branch_name,
        }
        if start_point is not None:
            data["start_point"] = start_point
        return self._call(
            "create_branch",
            runtime_id,
            f"runtime/{runtime_id}/git/branch/create",
            data,
            {
                "repository_path": repository_path,
                "branch_name": branch_name,
                "start_point": start_point,
            },
            attributes={"file.path": repository_path, "git.branch": branch_name},
        )

    def delete_branch(
        self,
        runtime_id: str,
        repository_path: str,
        branch_name: str,
        force: Optional[bool] = None,
    ) -> GitOperationResult:
        """Delete a branch: ``git branch -d`` or ``-D`` when ``force`` is true."""
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {
            "repository_path": repository_path,
            "branch_name": branch_name,
        }
        if force is not None:
            data["force"] = force
        return self._call(
            "delete_branch",
            runtime_id,
            f"runtime/{runtime_id}/git/branch/delete",
            data,
            {
                "repository_path": repository_path,
                "branch_name": branch_name,
                "force": force,
            },
            attributes={"file.path": repository_path, "git.branch": branch_name},
        )


class AsyncRuntimeGitResource:
    """Git operations on runtimes (async). Use ``await client.runtime.git.clone(...)``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "AsyncRuntimes"):
        self._rt = runtimes

    async def _call(
        self,
        operation: str,
        runtime_id: str,
        endpoint: str,
        data: Dict[str, Any],
        inputs: Mapping[str, Any],
        *,
        attributes: Optional[Mapping[str, Any]] = None,
    ) -> GitOperationResult:
        from .. import telemetry

        with telemetry.runtime_span(
            f"git.{operation}",
            runtime_id,
            inputs=dict(inputs),
            attributes=dict(attributes) if attributes else None,
        ) as span:
            response = await self._rt._make_agents_request("POST", endpoint, data)
            result = GitOperationResult.from_api(response.json())
            _record_git_result(span, result)
            return result

    async def clone(
        self,
        runtime_id: str,
        url: str,
        path: str,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        auth_token: Optional[str] = None,
    ) -> GitOperationResult:
        """Clone a repository into the runtime.

        Same URL rules as :meth:`RuntimeGitResource.clone` (``http``/``https``/``ssh``/``git``
        URL schemes or SCP-style ``git@host:path``; ``file://`` not allowed).
        """
        _validate_runtime_id(runtime_id)
        _validate_path(path)
        data: Dict[str, Any] = {"url": url, "path": path}
        if branch is not None:
            data["branch"] = branch
        if depth is not None:
            data["depth"] = int(depth)
        if auth_token is not None:
            data["auth_token"] = auth_token
        return await self._call(
            "clone",
            runtime_id,
            f"runtime/{runtime_id}/git/clone",
            data,
            {"url": url, "path": path, "branch": branch, "depth": depth, "auth": bool(auth_token)},
            attributes={"git.repository_url": url, "file.path": path},
        )

    async def status(self, runtime_id: str, repository_path: str) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data = {"repository_path": repository_path}
        return await self._call(
            "status",
            runtime_id,
            f"runtime/{runtime_id}/git/status",
            data,
            {"repository_path": repository_path},
            attributes={"file.path": repository_path},
        )

    async def branch_list(
        self,
        runtime_id: str,
        repository_path: str,
        scope: Optional[str] = None,
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if scope is not None:
            data["scope"] = scope
        return await self._call(
            "branch_list",
            runtime_id,
            f"runtime/{runtime_id}/git/branches",
            data,
            {"repository_path": repository_path, "scope": scope},
            attributes={"file.path": repository_path},
        )

    async def checkout(
        self, runtime_id: str, repository_path: str, ref_name: str
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data = {"repository_path": repository_path, "ref_name": ref_name}
        return await self._call(
            "checkout",
            runtime_id,
            f"runtime/{runtime_id}/git/checkout",
            data,
            {"repository_path": repository_path, "ref_name": ref_name},
            attributes={"file.path": repository_path, "git.ref": ref_name},
        )

    async def pull(
        self,
        runtime_id: str,
        repository_path: str,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if remote is not None:
            data["remote"] = remote
        if branch is not None:
            data["branch"] = branch
        return await self._call(
            "pull",
            runtime_id,
            f"runtime/{runtime_id}/git/pull",
            data,
            {"repository_path": repository_path, "remote": remote, "branch": branch},
            attributes={"file.path": repository_path},
        )

    async def push(
        self,
        runtime_id: str,
        repository_path: str,
        remote: Optional[str] = None,
        refspec: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if remote is not None:
            data["remote"] = remote
        if refspec is not None:
            data["refspec"] = refspec
        if username is not None:
            data["username"] = username
        if password is not None:
            data["password"] = password
        return await self._call(
            "push",
            runtime_id,
            f"runtime/{runtime_id}/git/push",
            data,
            {
                "repository_path": repository_path,
                "remote": remote,
                "refspec": refspec,
                "auth": bool(username or password),
            },
            attributes={"file.path": repository_path},
        )

    async def fetch(
        self, runtime_id: str, repository_path: str, remote: Optional[str] = None
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if remote is not None:
            data["remote"] = remote
        return await self._call(
            "fetch",
            runtime_id,
            f"runtime/{runtime_id}/git/fetch",
            data,
            {"repository_path": repository_path, "remote": remote},
            attributes={"file.path": repository_path},
        )

    async def add(
        self, runtime_id: str, repository_path: str, paths: Optional[List[str]] = None
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if paths is not None:
            data["paths"] = paths
        return await self._call(
            "add",
            runtime_id,
            f"runtime/{runtime_id}/git/add",
            data,
            {"repository_path": repository_path, "paths": paths},
            attributes={"file.path": repository_path},
        )

    async def commit(
        self,
        runtime_id: str,
        repository_path: str,
        message: str,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
        allow_empty: Optional[bool] = None,
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path, "message": message}
        if author_name is not None:
            data["author_name"] = author_name
        if author_email is not None:
            data["author_email"] = author_email
        if allow_empty is not None:
            data["allow_empty"] = allow_empty
        return await self._call(
            "commit",
            runtime_id,
            f"runtime/{runtime_id}/git/commit",
            data,
            {
                "repository_path": repository_path,
                "message": message,
                "author_name": author_name,
                "allow_empty": allow_empty,
            },
            attributes={"file.path": repository_path},
        )

    async def create_branch(
        self,
        runtime_id: str,
        repository_path: str,
        branch_name: str,
        start_point: Optional[str] = None,
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {
            "repository_path": repository_path,
            "branch_name": branch_name,
        }
        if start_point is not None:
            data["start_point"] = start_point
        return await self._call(
            "create_branch",
            runtime_id,
            f"runtime/{runtime_id}/git/branch/create",
            data,
            {
                "repository_path": repository_path,
                "branch_name": branch_name,
                "start_point": start_point,
            },
            attributes={"file.path": repository_path, "git.branch": branch_name},
        )

    async def delete_branch(
        self,
        runtime_id: str,
        repository_path: str,
        branch_name: str,
        force: Optional[bool] = None,
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {
            "repository_path": repository_path,
            "branch_name": branch_name,
        }
        if force is not None:
            data["force"] = force
        return await self._call(
            "delete_branch",
            runtime_id,
            f"runtime/{runtime_id}/git/branch/delete",
            data,
            {
                "repository_path": repository_path,
                "branch_name": branch_name,
                "force": force,
            },
            attributes={"file.path": repository_path, "git.branch": branch_name},
        )
