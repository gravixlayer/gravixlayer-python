"""Background commands: list, inspect, attach, and stop.

A command started with ``background=True`` keeps running after ``run_cmd``
returns. Output is available later through ``wait`` or ``connect``.
"""

from __future__ import annotations

import inspect
import json
import time
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Optional, Set

import httpx

from .._resource_utils import aiter_sse_payloads, iter_sse_payloads
from ..types.exceptions import GravixLayerConnectionError
from ..types.runtime import CommandInfo, CommandRunResponse, _validate_runtime_id

_SIGNALS = frozenset({"KILL", "TERM", "INT", "HUP"})
_DEADLINE_MARGIN_S = 30.0
_PING_GRACE_S = 45.0
_STREAM_HEADERS = {"Accept": "text/event-stream"}


def command_request_timeout(timeout_seconds: Optional[int]) -> Dict[str, Any]:
    """HTTP budget that outlasts a guest command deadline."""
    if timeout_seconds is None:
        return {}
    return {"timeout": httpx.Timeout(float(timeout_seconds) + _DEADLINE_MARGIN_S)}


def stream_timeout(client_timeout: float) -> Dict[str, Any]:
    """HTTP budget for a command event stream. A read always outlasts three
    of the server's 15 s keepalive pings, whatever the client timeout is."""
    return {"timeout": httpx.Timeout(client_timeout, read=max(client_timeout, _PING_GRACE_S))}


def _signal_params(signal: Optional[str]) -> Optional[Dict[str, str]]:
    if signal is None:
        return None
    if signal not in _SIGNALS:
        raise ValueError("signal must be KILL, TERM, INT, or HUP")
    return {"signal": signal}


def _chunk(value: Any) -> str:
    return value if isinstance(value, str) else str(value)


def fold_command_sse(
    payloads: Iterator[str],
    on_stdout: Optional[Callable[[str], None]],
    on_stderr: Optional[Callable[[str], None]],
    on_exit: Optional[Callable[[int], None]],
    detached: bool = False,
) -> CommandRunResponse:
    """Collect a command event stream into one result.

    ``detached`` commands outlive the stream, so a broken stream says nothing
    about how they ended and raises. Otherwise the command stops with its
    stream, and the failure is reported the way the command's own failure
    would be, so callers have one path to handle.
    """
    stdout_parts: List[str] = []
    stderr_parts: List[str] = []
    exit_code = 0
    duration_ms: Optional[int] = None
    timed_out = False
    finished = False
    start = time.monotonic()

    for payload in payloads:
        evt = _load_event(payload)
        if evt is None:
            continue
        kind = evt.get("type")
        if kind == "stdout":
            chunk = _chunk(evt.get("data", ""))
            stdout_parts.append(chunk)
            if on_stdout is not None:
                on_stdout(chunk)
        elif kind == "stderr":
            chunk = _chunk(evt.get("data", ""))
            stderr_parts.append(chunk)
            if on_stderr is not None:
                on_stderr(chunk)
        elif kind == "end":
            exit_code = int(evt.get("exit_code", 0))
            if evt.get("duration_ms") is not None:
                duration_ms = int(evt["duration_ms"])
            timed_out = bool(evt.get("timed_out", False))
            finished = True
            if on_exit is not None:
                on_exit(exit_code)
            break
        elif kind == "error":
            message = str(evt.get("message", ""))
            if detached:
                raise GravixLayerConnectionError(message)
            stderr_parts.append(message)
            if on_stderr is not None:
                on_stderr(message)
            exit_code = 1
            finished = True
            if on_exit is not None:
                on_exit(exit_code)
            break

    if not finished:
        raise GravixLayerConnectionError("command stream ended before the command finished")
    if duration_ms is None:
        duration_ms = int((time.monotonic() - start) * 1000)
    return CommandRunResponse(
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
        exit_code=exit_code,
        duration_ms=duration_ms,
        success=exit_code == 0,
        timed_out=timed_out,
    )


async def afold_command_sse(
    payloads: AsyncIterator[str],
    on_stdout: Optional[Any],
    on_stderr: Optional[Any],
    on_exit: Optional[Any],
    detached: bool = False,
) -> CommandRunResponse:
    """Async counterpart of :func:`fold_command_sse`."""

    async def dispatch(callback: Optional[Any], value: Any) -> None:
        if callback is None:
            return
        maybe = callback(value)
        if inspect.isawaitable(maybe):
            await maybe

    stdout_parts: List[str] = []
    stderr_parts: List[str] = []
    exit_code = 0
    duration_ms: Optional[int] = None
    timed_out = False
    finished = False
    start = time.monotonic()

    async for payload in payloads:
        evt = _load_event(payload)
        if evt is None:
            continue
        kind = evt.get("type")
        if kind == "stdout":
            chunk = _chunk(evt.get("data", ""))
            stdout_parts.append(chunk)
            await dispatch(on_stdout, chunk)
        elif kind == "stderr":
            chunk = _chunk(evt.get("data", ""))
            stderr_parts.append(chunk)
            await dispatch(on_stderr, chunk)
        elif kind == "end":
            exit_code = int(evt.get("exit_code", 0))
            if evt.get("duration_ms") is not None:
                duration_ms = int(evt["duration_ms"])
            timed_out = bool(evt.get("timed_out", False))
            finished = True
            await dispatch(on_exit, exit_code)
            break
        elif kind == "error":
            message = str(evt.get("message", ""))
            if detached:
                raise GravixLayerConnectionError(message)
            stderr_parts.append(message)
            await dispatch(on_stderr, message)
            exit_code = 1
            finished = True
            await dispatch(on_exit, exit_code)
            break

    if not finished:
        raise GravixLayerConnectionError("command stream ended before the command finished")
    if duration_ms is None:
        duration_ms = int((time.monotonic() - start) * 1000)
    return CommandRunResponse(
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
        exit_code=exit_code,
        duration_ms=duration_ms,
        success=exit_code == 0,
        timed_out=timed_out,
    )


def _load_event(payload: str) -> Optional[Dict[str, Any]]:
    try:
        evt = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return evt if isinstance(evt, dict) else None


class CommandHandle:
    """A command that was started in the background."""

    def __init__(self, runtimes: Any, runtime_id: str, pid: int) -> None:
        self._runtimes = runtimes
        self.runtime_id = runtime_id
        self.pid = pid
        self._responses: Set[httpx.Response] = set()
        self._disconnects = 0
        self._error: Optional[Exception] = None

    @property
    def error(self) -> Optional[Exception]:
        """What stopped the output follow ``run_cmd`` started, if it failed."""
        return self._error

    def wait(
        self,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
    ) -> CommandRunResponse:
        """Read the command's output until it exits."""
        response = self._runtimes._make_agents_request(
            "GET",
            f"runtime/{self.runtime_id}/commands/{self.pid}/stream",
            stream=True,
            headers=_STREAM_HEADERS,
            **stream_timeout(self._runtimes.client.timeout),
        )
        self._responses.add(response)
        try:
            return fold_command_sse(
                iter_sse_payloads(response.iter_lines()),
                on_stdout,
                on_stderr,
                on_exit,
                detached=True,
            )
        finally:
            response.close()
            self._responses.discard(response)

    def _follow(
        self,
        on_stdout: Optional[Callable[[str], None]],
        on_stderr: Optional[Callable[[str], None]],
        on_exit: Optional[Callable[[int], None]],
        on_error: Optional[Callable[[Exception], None]],
    ) -> Optional[CommandRunResponse]:
        """Thread target for ``run_cmd`` callbacks. A failure is kept on
        :attr:`error` and passed to ``on_error``; :meth:`disconnect` stops the
        follow without one."""
        disconnects = self._disconnects
        try:
            return self.wait(on_stdout, on_stderr, on_exit)
        except Exception as exc:
            if self._disconnects == disconnects:
                self._error = exc
                if on_error is not None:
                    on_error(exc)
            return None

    def kill(self, signal: Optional[str] = None) -> CommandInfo:
        """Signal the command. The default signal is ``KILL``."""
        return self._runtimes.command.kill(self.runtime_id, self.pid, signal)

    def refresh(self) -> CommandInfo:
        """Read the command's current state."""
        return self._runtimes.command.get(self.runtime_id, self.pid)

    def disconnect(self) -> None:
        """Stop reading output on every open ``wait``. The command keeps running."""
        self._disconnects += 1
        for response in list(self._responses):
            response.close()


class AsyncCommandHandle:
    """Async handle for a background command."""

    def __init__(self, runtimes: Any, runtime_id: str, pid: int) -> None:
        self._runtimes = runtimes
        self.runtime_id = runtime_id
        self.pid = pid
        self._responses: Set[httpx.Response] = set()
        self._disconnects = 0
        self._error: Optional[Exception] = None
        self._wait_task: Optional[Any] = None

    @property
    def error(self) -> Optional[Exception]:
        """What stopped the output follow ``run_cmd`` started, if it failed."""
        return self._error

    async def wait(
        self,
        on_stdout: Optional[Any] = None,
        on_stderr: Optional[Any] = None,
        on_exit: Optional[Any] = None,
    ) -> CommandRunResponse:
        """Read the command's output until it exits."""
        response = await self._runtimes._make_agents_request(
            "GET",
            f"runtime/{self.runtime_id}/commands/{self.pid}/stream",
            stream=True,
            headers=_STREAM_HEADERS,
            **stream_timeout(self._runtimes.client.timeout),
        )
        self._responses.add(response)
        try:
            return await afold_command_sse(
                aiter_sse_payloads(response.aiter_lines()),
                on_stdout,
                on_stderr,
                on_exit,
                detached=True,
            )
        finally:
            await response.aclose()
            self._responses.discard(response)

    async def _follow(
        self,
        on_stdout: Optional[Any],
        on_stderr: Optional[Any],
        on_exit: Optional[Any],
        on_error: Optional[Any],
    ) -> Optional[CommandRunResponse]:
        """Task body for ``run_cmd`` callbacks. A failure is kept on
        :attr:`error` and passed to ``on_error``; :meth:`disconnect` stops the
        follow without one."""
        disconnects = self._disconnects
        try:
            return await self.wait(on_stdout, on_stderr, on_exit)
        except Exception as exc:
            if self._disconnects == disconnects:
                self._error = exc
                if on_error is not None:
                    maybe = on_error(exc)
                    if inspect.isawaitable(maybe):
                        await maybe
            return None

    async def kill(self, signal: Optional[str] = None) -> CommandInfo:
        """Signal the command. The default signal is ``KILL``."""
        return await self._runtimes.command.kill(self.runtime_id, self.pid, signal)

    async def refresh(self) -> CommandInfo:
        """Read the command's current state."""
        return await self._runtimes.command.get(self.runtime_id, self.pid)

    async def disconnect(self) -> None:
        """Stop reading output on every open ``wait``. The command keeps running."""
        self._disconnects += 1
        for response in list(self._responses):
            await response.aclose()


class RuntimeCommandResource:
    """``client.runtime.command`` for the synchronous client."""

    def __init__(self, runtimes: Any) -> None:
        self._runtimes = runtimes

    def list(self, runtime_id: str) -> List[CommandInfo]:
        _validate_runtime_id(runtime_id)
        response = self._runtimes._make_agents_request("GET", f"runtime/{runtime_id}/commands")
        return _parse_list(response.json())

    def get(self, runtime_id: str, pid: int) -> CommandInfo:
        _validate_runtime_id(runtime_id)
        response = self._runtimes._make_agents_request(
            "GET", f"runtime/{runtime_id}/commands/{pid}"
        )
        return CommandInfo.from_api(response.json())

    def connect(
        self,
        runtime_id: str,
        pid: int,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
    ) -> CommandRunResponse:
        return CommandHandle(self._runtimes, runtime_id, pid).wait(on_stdout, on_stderr, on_exit)

    def kill(self, runtime_id: str, pid: int, signal: Optional[str] = None) -> CommandInfo:
        _validate_runtime_id(runtime_id)
        response = self._runtimes._make_agents_request(
            "DELETE",
            f"runtime/{runtime_id}/commands/{pid}",
            params=_signal_params(signal),
        )
        return CommandInfo.from_api(response.json())


class AsyncRuntimeCommandResource:
    """``client.runtime.command`` for the asynchronous client."""

    def __init__(self, runtimes: Any) -> None:
        self._runtimes = runtimes

    async def list(self, runtime_id: str) -> List[CommandInfo]:
        _validate_runtime_id(runtime_id)
        response = await self._runtimes._make_agents_request(
            "GET", f"runtime/{runtime_id}/commands"
        )
        return _parse_list(response.json())

    async def get(self, runtime_id: str, pid: int) -> CommandInfo:
        _validate_runtime_id(runtime_id)
        response = await self._runtimes._make_agents_request(
            "GET", f"runtime/{runtime_id}/commands/{pid}"
        )
        return CommandInfo.from_api(response.json())

    async def connect(
        self,
        runtime_id: str,
        pid: int,
        on_stdout: Optional[Any] = None,
        on_stderr: Optional[Any] = None,
        on_exit: Optional[Any] = None,
    ) -> CommandRunResponse:
        return await AsyncCommandHandle(self._runtimes, runtime_id, pid).wait(
            on_stdout, on_stderr, on_exit
        )

    async def kill(self, runtime_id: str, pid: int, signal: Optional[str] = None) -> CommandInfo:
        _validate_runtime_id(runtime_id)
        response = await self._runtimes._make_agents_request(
            "DELETE",
            f"runtime/{runtime_id}/commands/{pid}",
            params=_signal_params(signal),
        )
        return CommandInfo.from_api(response.json())


def _parse_list(data: Any) -> List[CommandInfo]:
    items = data.get("commands") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [CommandInfo.from_api(item) for item in items if isinstance(item, dict)]
