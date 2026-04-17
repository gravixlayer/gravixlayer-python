"""
Git sub-resource for runtime API: ``client.runtime.git.clone(...)``, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..types.runtime import GitOperationResult, _validate_path, _validate_runtime_id

if TYPE_CHECKING:
    from .runtime import Runtimes
    from .async_runtime import AsyncRuntimes


class RuntimeGitResource:
    """Git operations on runtimes (sync). Use ``client.runtime.git.clone(...)``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "Runtimes"):
        self._rt = runtimes

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
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/clone", data
        )
        return GitOperationResult.from_api(response.json())

    def status(self, runtime_id: str, repository_path: str) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data = {"repository_path": repository_path}
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/status", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/branches", data
        )
        return GitOperationResult.from_api(response.json())

    def checkout(
        self, runtime_id: str, repository_path: str, ref_name: str
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data = {"repository_path": repository_path, "ref_name": ref_name}
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/checkout", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/pull", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/push", data
        )
        return GitOperationResult.from_api(response.json())

    def fetch(
        self, runtime_id: str, repository_path: str, remote: Optional[str] = None
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if remote is not None:
            data["remote"] = remote
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/fetch", data
        )
        return GitOperationResult.from_api(response.json())

    def add(
        self, runtime_id: str, repository_path: str, paths: Optional[List[str]] = None
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if paths is not None:
            data["paths"] = paths
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/add", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/commit", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/branch/create", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/branch/delete", data
        )
        return GitOperationResult.from_api(response.json())


class AsyncRuntimeGitResource:
    """Git operations on runtimes (async). Use ``await client.runtime.git.clone(...)``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "AsyncRuntimes"):
        self._rt = runtimes

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
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/clone", data
        )
        return GitOperationResult.from_api(response.json())

    async def status(self, runtime_id: str, repository_path: str) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data = {"repository_path": repository_path}
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/status", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/branches", data
        )
        return GitOperationResult.from_api(response.json())

    async def checkout(
        self, runtime_id: str, repository_path: str, ref_name: str
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data = {"repository_path": repository_path, "ref_name": ref_name}
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/checkout", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/pull", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/push", data
        )
        return GitOperationResult.from_api(response.json())

    async def fetch(
        self, runtime_id: str, repository_path: str, remote: Optional[str] = None
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if remote is not None:
            data["remote"] = remote
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/fetch", data
        )
        return GitOperationResult.from_api(response.json())

    async def add(
        self, runtime_id: str, repository_path: str, paths: Optional[List[str]] = None
    ) -> GitOperationResult:
        _validate_runtime_id(runtime_id)
        _validate_path(repository_path)
        data: Dict[str, Any] = {"repository_path": repository_path}
        if paths is not None:
            data["paths"] = paths
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/add", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/commit", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/branch/create", data
        )
        return GitOperationResult.from_api(response.json())

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
        response = await self._rt._make_agents_request(
            "POST", f"runtime/{runtime_id}/git/branch/delete", data
        )
        return GitOperationResult.from_api(response.json())
