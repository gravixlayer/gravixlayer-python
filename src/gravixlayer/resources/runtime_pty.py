"""
Programmatic PTY sessions: ``client.runtime.pty.create(...)``, ``.send_input``, ``.stream``.

A PTY session is a real pseudo-terminal allocated inside the runtime and owned by the
execution plane rather than by the connection that created it. It therefore survives
client disconnects: create a session, stream its output, drop the connection, and
re-attach later to the same shell with its scrollback intact.

This is the programmatic counterpart to the interactive websocket terminal. It is
designed for agents that need to drive an interactive process (a REPL, an installer
prompt, a TUI) rather than run one-shot commands.
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import threading
import time
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Dict, Iterator, List, Optional

from .. import telemetry
from .._resource_utils import aiter_sse_payloads, iter_sse_payloads
from ..types.runtime import PtyInputResponse, PtySession, _validate_runtime_id

if TYPE_CHECKING:
    from .runtime import Runtimes
    from .async_runtime import AsyncRuntimes


# PTY output stream event kinds.
PTY_EVENT_DATA = "data"
PTY_EVENT_EXIT = "exit"
PTY_EVENT_ERROR = "error"

# Session lifecycle states reported by the execution plane.
PTY_STATUS_RUNNING = "running"
PTY_STATUS_EXITED = "exited"

# Upper bound on the terminal output a handle retains in memory. Older bytes are
# discarded so a long lived session cannot grow the client's heap without bound.
PTY_HANDLE_BUFFER_BYTES = 1 << 20

# How long a handle waits on its exit event before re-checking session state.
PTY_HANDLE_POLL_SECONDS = 0.5

# How long ``disconnect`` waits for the reader to unwind after the stream is closed.
PTY_HANDLE_JOIN_SECONDS = 5.0


def _validate_session_id(session_id: str) -> None:
    if not session_id or not str(session_id).strip():
        raise ValueError("session_id must be a non-empty string")


def _validate_size(cols: int, rows: int) -> None:
    if int(cols) <= 0 or int(rows) <= 0:
        raise ValueError("cols and rows must be positive integers")


def _create_payload(
    shell: Optional[str],
    args: Optional[List[str]],
    working_dir: Optional[str],
    environment: Optional[Dict[str, str]],
    cols: Optional[int],
    rows: Optional[int],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if shell is not None:
        payload["shell"] = shell
    if args is not None:
        payload["args"] = list(args)
    if working_dir is not None:
        payload["working_dir"] = working_dir
    if environment is not None:
        payload["environment"] = environment
    if cols is not None:
        payload["cols"] = int(cols)
    if rows is not None:
        payload["rows"] = int(rows)
    return payload


def _input_payload(data: Any) -> Dict[str, Any]:
    """Build the write payload, base64 encoding raw bytes so binary input survives JSON."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        return {"data_base64": base64.b64encode(bytes(data)).decode("ascii")}
    if isinstance(data, str):
        return {"data": data}
    raise TypeError(f"Expected str or bytes for PTY input, got {type(data).__name__}")


def _decode_event(payload: str) -> Optional[Dict[str, Any]]:
    """Parse one SSE JSON frame, decoding base64 terminal data into bytes."""
    try:
        evt = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if evt.get("type") == PTY_EVENT_DATA:
        raw = evt.get("data") or ""
        try:
            evt["data"] = base64.b64decode(raw)
        except (ValueError, TypeError):
            evt["data"] = b""
    return evt


def _deadline(timeout: Optional[float]) -> Optional[float]:
    """Convert a relative timeout into a monotonic deadline."""
    if timeout is None:
        return None
    if timeout < 0:
        raise ValueError("timeout must not be negative")
    return time.monotonic() + float(timeout)


def _time_left(deadline: Optional[float]) -> Optional[float]:
    """Seconds remaining until ``deadline``; ``None`` when there is no deadline."""
    if deadline is None:
        return None
    return deadline - time.monotonic()


def _has_exited(session: PtySession) -> bool:
    return bool(session.status) and session.status != PTY_STATUS_RUNNING


def _append_bounded(buffer: bytearray, chunk: bytes) -> None:
    """Append to a scrollback buffer, dropping the oldest bytes past the cap."""
    if not chunk:
        return
    buffer.extend(chunk)
    overflow = len(buffer) - PTY_HANDLE_BUFFER_BYTES
    if overflow > 0:
        del buffer[:overflow]


class PtyHandle:
    """A live client-side attachment to a PTY session.

    A handle owns one output stream. Attaching, detaching and re-attaching are all
    independent of the session's lifetime: the shell inside the runtime keeps running
    whether or not any handle is connected, so :meth:`disconnect` is not the same as
    :meth:`kill`.

    Obtain one with ``client.runtime.pty.handle(runtime_id, session_id)`` or, from a
    :class:`~gravixlayer.types.runtime.Runtime`, ``runtime.pty.handle(session_id)``.

    Example:
        >>> session = client.runtime.pty.create(rid)
        >>> with client.runtime.pty.handle(rid, session.session_id) as pty:
        ...     pty.connect(on_data=lambda b: print(b.decode("utf-8", "replace"), end=""))
        ...     pty.wait_for_connection(timeout=10)
        ...     pty.send_input("make build && exit\\n")
        ...     final = pty.wait_for_completion(timeout=600)
        ...     print("exit:", final.exit_code)
    """

    __slots__ = (
        "_resource",
        "_runtime_id",
        "_session_id",
        "_session",
        "_lock",
        "_thread",
        "_response",
        "_connected",
        "_opened",
        "_exited",
        "_stopping",
        "_buffer",
        "_error",
        "_on_data",
        "_on_exit",
    )

    def __init__(self, resource: "RuntimePtyResource", runtime_id: str, session_id: str) -> None:
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        self._resource = resource
        self._runtime_id = runtime_id
        self._session_id = session_id
        self._session: Optional[PtySession] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._response: Any = None
        self._connected = threading.Event()
        self._opened = False
        self._exited = threading.Event()
        self._stopping = False
        self._buffer = bytearray()
        self._error: Optional[str] = None
        self._on_data: Optional[Callable[[bytes], None]] = None
        self._on_exit: Optional[Callable[[int, str], None]] = None

    @property
    def runtime_id(self) -> str:
        return self._runtime_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def is_connected(self) -> bool:
        """``True`` while this handle holds an open output stream."""
        with self._lock:
            return self._response is not None

    @property
    def exit_code(self) -> Optional[int]:
        """Exit status of the session's process, or ``None`` while it is running."""
        session = self._session
        if session is not None and _has_exited(session):
            return session.exit_code
        return None

    @property
    def error(self) -> Optional[str]:
        """The last stream or transport error observed by this handle."""
        return self._error

    @property
    def output(self) -> bytes:
        """Terminal bytes received since :meth:`connect`, capped at the buffer size."""
        with self._lock:
            return bytes(self._buffer)

    @property
    def session(self) -> Optional[PtySession]:
        """The most recently observed session state, without issuing a request."""
        return self._session

    def connect(
        self,
        on_data: Optional[Callable[[bytes], None]] = None,
        on_exit: Optional[Callable[[int, str], None]] = None,
    ) -> "PtyHandle":
        """Attach to the session's output stream on a background reader thread.

        Returns immediately; use :meth:`wait_for_connection` to block until the
        stream is actually open. Calling ``connect`` on an already connected handle
        is a no-op. Callbacks run on the reader thread, so keep them short.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self
            self._on_data = on_data
            self._on_exit = on_exit
            self._stopping = False
            self._opened = False
            self._error = None
            self._connected.clear()
            self._exited.clear()
            thread = threading.Thread(
                target=self._read_stream,
                name=f"gravixlayer-pty-{self._session_id}",
                daemon=True,
            )
            self._thread = thread
        thread.start()
        return self

    def _read_stream(self) -> None:
        try:
            response = self._resource._req(
                "GET", f"runtime/{self._runtime_id}/pty/{self._session_id}/stream", stream=True
            )
        except Exception as exc:  # transport or HTTP failure before the stream opened
            self._error = str(exc)
            self._connected.set()
            return
        with self._lock:
            self._response = response
            self._opened = True
        self._connected.set()
        try:
            for body in iter_sse_payloads(response.iter_lines()):
                if not self._dispatch(body):
                    break
        except Exception as exc:  # closed by disconnect(), or the stream broke
            if not self._stopping:
                self._error = str(exc)
        finally:
            with self._lock:
                # Only retract our own stream: disconnect() may already have cleared it
                # and a later connect() may have installed a new one.
                if self._response is response:
                    self._response = None
            try:
                response.close()
            except Exception:  # already closed by disconnect()
                pass

    def _dispatch(self, body: str) -> bool:
        """Handle one SSE frame. Returns ``False`` when the stream should stop."""
        evt = _decode_event(body)
        if evt is None:
            return True
        kind = evt.get("type")
        if kind == PTY_EVENT_DATA:
            chunk = evt.get("data") or b""
            with self._lock:
                _append_bounded(self._buffer, chunk)
            if self._on_data is not None:
                self._on_data(chunk)
            return True
        if kind == PTY_EVENT_EXIT:
            exit_code = int(evt.get("exit_code") or 0)
            status = str(evt.get("status") or PTY_STATUS_EXITED)
            self._record_exit(exit_code)
            if self._on_exit is not None:
                self._on_exit(exit_code, status)
            return False
        if kind == PTY_EVENT_ERROR:
            self._error = str(evt.get("message") or "PTY stream failed")
        return True

    def _record_exit(self, exit_code: int) -> None:
        session = self._session
        if session is None:
            session = PtySession(session_id=self._session_id, runtime_id=self._runtime_id)
        session.exit_code = exit_code
        # The exit frame's own status is the process outcome ("success"/"failed"), which
        # reaches callers through on_exit. PtySession.status stays the lifecycle value the
        # control plane reports, so it means the same thing however the session was fetched.
        session.status = PTY_STATUS_EXITED
        self._session = session
        self._exited.set()

    def wait_for_connection(self, timeout: Optional[float] = None) -> bool:
        """Block until the output stream has been opened.

        Connects first if the handle is not attached yet. Returns ``True`` once the
        stream has been established, and raises ``TimeoutError`` if it does not open
        in time or ``RuntimeError`` if the attempt failed outright. A stream that
        opened and has since finished still counts as connected: use
        :attr:`is_connected` to ask whether it is *currently* open.
        """
        with self._lock:
            needs_connect = self._thread is None and not self._opened
            on_data, on_exit = self._on_data, self._on_exit
        if needs_connect:
            self.connect(on_data, on_exit)
        if not self._connected.wait(timeout=timeout):
            raise TimeoutError(
                f"PTY session {self._session_id} did not connect within {timeout}s"
            )
        with self._lock:
            opened = self._opened
        if opened:
            return True
        raise RuntimeError(
            self._error or f"PTY session {self._session_id} stream could not be opened"
        )

    def wait_for_completion(self, timeout: Optional[float] = None) -> PtySession:
        """Block until the session's process exits and return its final state.

        Works whether or not the handle is connected. A connected handle reacts the
        moment the exit frame arrives and issues no requests while it waits; a
        detached one falls back to polling session state. Raises ``TimeoutError`` if
        the process is still running when time runs out.
        """
        deadline = _deadline(timeout)
        while True:
            if self._exited.is_set() and self._session is not None:
                return self._session
            # An attached stream delivers the exit frame, so polling the control
            # plane as well would be pure overhead. If the stream drops, this
            # turns false and the poll below takes over.
            if not self.is_connected:
                session = self._resource.get(self._runtime_id, self._session_id)
                self._session = session
                if _has_exited(session):
                    self._exited.set()
                    return session
            remaining = _time_left(deadline)
            if remaining is not None and remaining <= 0:
                raise TimeoutError(
                    f"PTY session {self._session_id} was still running after {timeout}s"
                )
            slice_seconds = (
                PTY_HANDLE_POLL_SECONDS
                if remaining is None
                else min(PTY_HANDLE_POLL_SECONDS, remaining)
            )
            if self._exited.wait(timeout=slice_seconds) and self._session is not None:
                return self._session

    def disconnect(self) -> None:
        """Detach from the output stream, leaving the session running.

        Safe to call repeatedly and from a thread other than the reader. Re-attach
        later with :meth:`connect`; the session replays its retained scrollback.
        """
        with self._lock:
            self._stopping = True
            response = self._response
            thread = self._thread
            self._response = None
            self._thread = None
            self._opened = False
        if response is not None:
            try:
                response.close()
            except Exception:  # the reader may have closed it first
                pass
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            # Best effort only: the reader can sit in a blocking read until the next
            # byte arrives, and is_connected must not depend on it unwinding.
            thread.join(timeout=PTY_HANDLE_JOIN_SECONDS)
        self._connected.clear()

    def refresh(self) -> PtySession:
        """Fetch and cache the session's current state."""
        session = self._resource.get(self._runtime_id, self._session_id)
        self._session = session
        if _has_exited(session):
            self._exited.set()
        return session

    def send_input(self, data: Any) -> PtyInputResponse:
        """Write ``str`` or ``bytes`` to the session's terminal."""
        return self._resource.send_input(self._runtime_id, self._session_id, data)

    def resize(self, cols: int, rows: int) -> bool:
        """Resize the terminal and deliver ``SIGWINCH``."""
        return self._resource.resize(self._runtime_id, self._session_id, cols, rows)

    def send_signal(self, signal: str) -> bool:
        """Send a POSIX signal to the session's process."""
        return self._resource.send_signal(self._runtime_id, self._session_id, signal)

    def kill(self) -> bool:
        """Terminate the session, then detach."""
        try:
            return self._resource.kill(self._runtime_id, self._session_id)
        finally:
            self.disconnect()

    def __enter__(self) -> "PtyHandle":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.disconnect()


class AsyncPtyHandle:
    """Async counterpart of :class:`PtyHandle`, driven by an asyncio reader task.

    Example:
        >>> session = await client.runtime.pty.create(rid)
        >>> async with client.runtime.pty.handle(rid, session.session_id) as pty:
        ...     await pty.connect()
        ...     await pty.wait_for_connection(timeout=10)
        ...     await pty.send_input("make build && exit\\n")
        ...     final = await pty.wait_for_completion(timeout=600)
    """

    __slots__ = (
        "_resource",
        "_runtime_id",
        "_session_id",
        "_session",
        "_task",
        "_response",
        "_connected",
        "_opened",
        "_exited",
        "_stopping",
        "_buffer",
        "_error",
        "_on_data",
        "_on_exit",
    )

    def __init__(self, resource: "AsyncRuntimePtyResource", runtime_id: str, session_id: str) -> None:
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        self._resource = resource
        self._runtime_id = runtime_id
        self._session_id = session_id
        self._session: Optional[PtySession] = None
        self._task: Optional["asyncio.Task[None]"] = None
        self._response: Any = None
        self._connected = asyncio.Event()
        self._opened = False
        self._exited = asyncio.Event()
        self._stopping = False
        self._buffer = bytearray()
        self._error: Optional[str] = None
        self._on_data: Optional[Callable[[bytes], Any]] = None
        self._on_exit: Optional[Callable[[int, str], Any]] = None

    @property
    def runtime_id(self) -> str:
        return self._runtime_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def is_connected(self) -> bool:
        """``True`` while this handle holds an open output stream."""
        return self._response is not None

    @property
    def exit_code(self) -> Optional[int]:
        """Exit status of the session's process, or ``None`` while it is running."""
        session = self._session
        if session is not None and _has_exited(session):
            return session.exit_code
        return None

    @property
    def error(self) -> Optional[str]:
        """The last stream or transport error observed by this handle."""
        return self._error

    @property
    def output(self) -> bytes:
        """Terminal bytes received since :meth:`connect`, capped at the buffer size."""
        return bytes(self._buffer)

    @property
    def session(self) -> Optional[PtySession]:
        """The most recently observed session state, without issuing a request."""
        return self._session

    async def connect(
        self,
        on_data: Optional[Callable[[bytes], Any]] = None,
        on_exit: Optional[Callable[[int, str], Any]] = None,
    ) -> "AsyncPtyHandle":
        """Attach to the session's output stream on a background task."""
        if self._task is not None and not self._task.done():
            return self
        self._on_data = on_data
        self._on_exit = on_exit
        self._stopping = False
        self._opened = False
        self._error = None
        self._connected.clear()
        self._exited.clear()
        self._task = asyncio.ensure_future(self._read_stream())
        return self

    async def _read_stream(self) -> None:
        try:
            response = await self._resource._req(
                "GET", f"runtime/{self._runtime_id}/pty/{self._session_id}/stream", stream=True
            )
        except Exception as exc:  # transport or HTTP failure before the stream opened
            self._error = str(exc)
            self._connected.set()
            return
        self._response = response
        self._opened = True
        self._connected.set()
        try:
            async for body in aiter_sse_payloads(response.aiter_lines()):
                if not await self._dispatch(body):
                    break
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # closed by disconnect(), or the stream broke
            if not self._stopping:
                self._error = str(exc)
        finally:
            # Only retract our own stream: disconnect() may already have cleared it
            # and a later connect() may have installed a new one.
            if self._response is response:
                self._response = None
            try:
                await response.aclose()
            except Exception:  # already closed by disconnect()
                pass

    async def _dispatch(self, body: str) -> bool:
        """Handle one SSE frame. Returns ``False`` when the stream should stop."""
        evt = _decode_event(body)
        if evt is None:
            return True
        kind = evt.get("type")
        if kind == PTY_EVENT_DATA:
            chunk = evt.get("data") or b""
            _append_bounded(self._buffer, chunk)
            if self._on_data is not None:
                maybe = self._on_data(chunk)
                if inspect.isawaitable(maybe):
                    await maybe
            return True
        if kind == PTY_EVENT_EXIT:
            exit_code = int(evt.get("exit_code") or 0)
            status = str(evt.get("status") or PTY_STATUS_EXITED)
            self._record_exit(exit_code)
            if self._on_exit is not None:
                maybe = self._on_exit(exit_code, status)
                if inspect.isawaitable(maybe):
                    await maybe
            return False
        if kind == PTY_EVENT_ERROR:
            self._error = str(evt.get("message") or "PTY stream failed")
        return True

    def _record_exit(self, exit_code: int) -> None:
        session = self._session
        if session is None:
            session = PtySession(session_id=self._session_id, runtime_id=self._runtime_id)
        session.exit_code = exit_code
        # See PtyHandle._record_exit: status stays the lifecycle value, not the outcome.
        session.status = PTY_STATUS_EXITED
        self._session = session
        self._exited.set()

    async def wait_for_connection(self, timeout: Optional[float] = None) -> bool:
        """Await the output stream being opened, connecting first if needed.

        A stream that opened and has since finished still counts as connected: use
        :attr:`is_connected` to ask whether it is *currently* open.
        """
        if self._task is None and not self._opened:
            await self.connect(self._on_data, self._on_exit)
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"PTY session {self._session_id} did not connect within {timeout}s"
            ) from exc
        if self._opened:
            return True
        raise RuntimeError(
            self._error or f"PTY session {self._session_id} stream could not be opened"
        )

    async def wait_for_completion(self, timeout: Optional[float] = None) -> PtySession:
        """Await the session's process exiting and return its final state.

        A connected handle issues no requests while it waits: the exit frame
        arrives on the stream. A detached one falls back to polling.
        """
        deadline = _deadline(timeout)
        while True:
            if self._exited.is_set() and self._session is not None:
                return self._session
            if not self.is_connected:
                session = await self._resource.get(self._runtime_id, self._session_id)
                self._session = session
                if _has_exited(session):
                    self._exited.set()
                    return session
            remaining = _time_left(deadline)
            if remaining is not None and remaining <= 0:
                raise TimeoutError(
                    f"PTY session {self._session_id} was still running after {timeout}s"
                )
            slice_seconds = (
                PTY_HANDLE_POLL_SECONDS
                if remaining is None
                else min(PTY_HANDLE_POLL_SECONDS, remaining)
            )
            try:
                await asyncio.wait_for(self._exited.wait(), timeout=slice_seconds)
            except asyncio.TimeoutError:
                continue
            if self._session is not None:
                return self._session

    async def disconnect(self) -> None:
        """Detach from the output stream, leaving the session running."""
        self._stopping = True
        task = self._task
        self._task = None
        self._opened = False
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        response = self._response
        self._response = None
        if response is not None:
            try:
                await response.aclose()
            except Exception:  # the reader task may have closed it first
                pass
        self._connected.clear()

    async def refresh(self) -> PtySession:
        """Fetch and cache the session's current state."""
        session = await self._resource.get(self._runtime_id, self._session_id)
        self._session = session
        if _has_exited(session):
            self._exited.set()
        return session

    async def send_input(self, data: Any) -> PtyInputResponse:
        """Write ``str`` or ``bytes`` to the session's terminal."""
        return await self._resource.send_input(self._runtime_id, self._session_id, data)

    async def resize(self, cols: int, rows: int) -> bool:
        """Resize the terminal and deliver ``SIGWINCH``."""
        return await self._resource.resize(self._runtime_id, self._session_id, cols, rows)

    async def send_signal(self, signal: str) -> bool:
        """Send a POSIX signal to the session's process."""
        return await self._resource.send_signal(self._runtime_id, self._session_id, signal)

    async def kill(self) -> bool:
        """Terminate the session, then detach."""
        try:
            return await self._resource.kill(self._runtime_id, self._session_id)
        finally:
            await self.disconnect()

    async def __aenter__(self) -> "AsyncPtyHandle":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.disconnect()


class RuntimePtyResource:
    """PTY session operations under ``client.runtime.pty``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "Runtimes"):
        self._rt = runtimes

    def _req(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any):
        return self._rt._make_agents_request(method, endpoint, data, **kwargs)

    def create(
        self,
        runtime_id: str,
        shell: Optional[str] = None,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
    ) -> PtySession:
        """Create a PTY session inside the runtime.

        Every argument is optional; omitted values use the execution plane defaults
        (``/bin/bash`` in ``/workspace`` at 80x24). The session keeps running after
        this call returns and after the client disconnects.

        Args:
            runtime_id: Target runtime ID.
            shell: Shell to launch. Must be one of the runtime's permitted shells.
            args: Arguments passed to the shell.
            working_dir: Initial working directory.
            environment: Extra environment variables, merged over the runtime's own.
            cols: Terminal width in columns.
            rows: Terminal height in rows.
        """
        _validate_runtime_id(runtime_id)
        payload = _create_payload(shell, args, working_dir, environment, cols, rows)
        with telemetry.runtime_span("pty.create", runtime_id) as span:
            response = self._req("POST", f"runtime/{runtime_id}/pty", payload)
            session = PtySession.from_api(response.json())
            if span is not None:
                telemetry.record_outputs(span, {"session_id": session.session_id, "pid": session.pid})
            return session

    def list(self, runtime_id: str) -> List[PtySession]:
        """List the PTY sessions belonging to the runtime."""
        _validate_runtime_id(runtime_id)
        response = self._req("GET", f"runtime/{runtime_id}/pty")
        sessions = response.json().get("sessions") or []
        return [PtySession.from_api(item) for item in sessions]

    def get(self, runtime_id: str, session_id: str) -> PtySession:
        """Describe a single PTY session."""
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        response = self._req("GET", f"runtime/{runtime_id}/pty/{session_id}")
        return PtySession.from_api(response.json())

    def send_input(self, runtime_id: str, session_id: str, data: Any) -> PtyInputResponse:
        """Write to the session's terminal.

        ``data`` may be ``str`` (sent as UTF-8) or ``bytes`` (sent verbatim, which is
        what you want for control characters and escape sequences). Remember that a
        shell only acts on a line once it sees a newline, so send ``"ls\\n"`` rather
        than ``"ls"``.
        """
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        payload = _input_payload(data)
        response = self._req("POST", f"runtime/{runtime_id}/pty/{session_id}/input", payload)
        result = response.json()
        return PtyInputResponse(
            success=bool(result.get("success", True)),
            bytes_written=int(result.get("bytes_written") or 0),
        )

    def resize(self, runtime_id: str, session_id: str, cols: int, rows: int) -> bool:
        """Resize the session's terminal and deliver ``SIGWINCH`` to the foreground job."""
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        _validate_size(cols, rows)
        payload = {"cols": int(cols), "rows": int(rows)}
        response = self._req("POST", f"runtime/{runtime_id}/pty/{session_id}/resize", payload)
        return bool(response.json().get("success", True))

    def send_signal(self, runtime_id: str, session_id: str, signal: str) -> bool:
        """Send a POSIX signal to the session's process.

        Accepts ``INT``, ``TERM``, ``KILL`` or ``HUP``, with or without the ``SIG``
        prefix. Use ``INT`` to interrupt a running foreground job the way Ctrl-C would.
        """
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        if not signal or not str(signal).strip():
            raise ValueError("signal must be a non-empty string")
        payload = {"signal": str(signal).strip()}
        response = self._req("POST", f"runtime/{runtime_id}/pty/{session_id}/signal", payload)
        return bool(response.json().get("success", True))

    def stream(
        self,
        runtime_id: str,
        session_id: str,
        on_data: Optional[Callable[[bytes], None]] = None,
        on_exit: Optional[Callable[[int, str], None]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Stream the session's output, starting with its retained scrollback.

        Yields dicts of the form ``{"type": "data", "data": b"..."}``,
        ``{"type": "exit", "exit_code": int, "status": str}`` or
        ``{"type": "error", "message": str}``. Terminal bytes are returned raw, since
        they contain escape sequences and may split multi-byte UTF-8 characters at
        chunk boundaries; decode with ``errors="replace"`` if you need text.

        The iterator ends when the session exits or when the caller stops consuming it.

        Example:
            >>> session = client.runtime.pty.create(rid)
            >>> client.runtime.pty.send_input(rid, session.session_id, "ls -la\\n")
            >>> for event in client.runtime.pty.stream(rid, session.session_id):
            ...     if event["type"] == "data":
            ...         print(event["data"].decode("utf-8", "replace"), end="")
        """
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        return self._stream_events(runtime_id, session_id, on_data, on_exit)

    def _stream_events(
        self,
        runtime_id: str,
        session_id: str,
        on_data: Optional[Callable[[bytes], None]],
        on_exit: Optional[Callable[[int, str], None]],
    ) -> Iterator[Dict[str, Any]]:
        response = self._req(
            "GET", f"runtime/{runtime_id}/pty/{session_id}/stream", stream=True
        )
        try:
            for body in iter_sse_payloads(response.iter_lines()):
                evt = _decode_event(body)
                if evt is None:
                    continue
                kind = evt.get("type")
                if kind == PTY_EVENT_DATA and on_data is not None:
                    on_data(evt.get("data") or b"")
                elif kind == PTY_EVENT_EXIT and on_exit is not None:
                    on_exit(int(evt.get("exit_code") or 0), str(evt.get("status") or ""))
                yield evt
                if kind == PTY_EVENT_EXIT:
                    break
        finally:
            response.close()

    def kill(self, runtime_id: str, session_id: str) -> bool:
        """Terminate the session and release its resources."""
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        response = self._req("DELETE", f"runtime/{runtime_id}/pty/{session_id}")
        return bool(response.json().get("success", True))

    def handle(self, runtime_id: str, session_id: str) -> PtyHandle:
        """Return a :class:`PtyHandle` for an existing session.

        The handle adds connection management on top of the stateless calls above:
        background streaming, :meth:`PtyHandle.wait_for_connection`,
        :meth:`PtyHandle.wait_for_completion` and :meth:`PtyHandle.disconnect`.
        Creating a handle performs no I/O.
        """
        return PtyHandle(self, runtime_id, session_id)


class AsyncRuntimePtyResource:
    """Async PTY session operations under ``client.runtime.pty``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "AsyncRuntimes"):
        self._rt = runtimes

    async def _req(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any):
        return await self._rt._make_agents_request(method, endpoint, data, **kwargs)

    async def create(
        self,
        runtime_id: str,
        shell: Optional[str] = None,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
    ) -> PtySession:
        """Create a PTY session inside the runtime."""
        _validate_runtime_id(runtime_id)
        payload = _create_payload(shell, args, working_dir, environment, cols, rows)
        with telemetry.runtime_span("pty.create", runtime_id) as span:
            response = await self._req("POST", f"runtime/{runtime_id}/pty", payload)
            session = PtySession.from_api(response.json())
            if span is not None:
                telemetry.record_outputs(span, {"session_id": session.session_id, "pid": session.pid})
            return session

    async def list(self, runtime_id: str) -> List[PtySession]:
        """List the PTY sessions belonging to the runtime."""
        _validate_runtime_id(runtime_id)
        response = await self._req("GET", f"runtime/{runtime_id}/pty")
        sessions = response.json().get("sessions") or []
        return [PtySession.from_api(item) for item in sessions]

    async def get(self, runtime_id: str, session_id: str) -> PtySession:
        """Describe a single PTY session."""
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        response = await self._req("GET", f"runtime/{runtime_id}/pty/{session_id}")
        return PtySession.from_api(response.json())

    async def send_input(self, runtime_id: str, session_id: str, data: Any) -> PtyInputResponse:
        """Write to the session's terminal."""
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        payload = _input_payload(data)
        response = await self._req("POST", f"runtime/{runtime_id}/pty/{session_id}/input", payload)
        result = response.json()
        return PtyInputResponse(
            success=bool(result.get("success", True)),
            bytes_written=int(result.get("bytes_written") or 0),
        )

    async def resize(self, runtime_id: str, session_id: str, cols: int, rows: int) -> bool:
        """Resize the session's terminal and deliver ``SIGWINCH``."""
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        _validate_size(cols, rows)
        payload = {"cols": int(cols), "rows": int(rows)}
        response = await self._req("POST", f"runtime/{runtime_id}/pty/{session_id}/resize", payload)
        return bool(response.json().get("success", True))

    async def send_signal(self, runtime_id: str, session_id: str, signal: str) -> bool:
        """Send a POSIX signal (``INT``, ``TERM``, ``KILL`` or ``HUP``) to the session."""
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        if not signal or not str(signal).strip():
            raise ValueError("signal must be a non-empty string")
        payload = {"signal": str(signal).strip()}
        response = await self._req("POST", f"runtime/{runtime_id}/pty/{session_id}/signal", payload)
        return bool(response.json().get("success", True))

    async def stream(
        self,
        runtime_id: str,
        session_id: str,
        on_data: Optional[Callable[[bytes], Any]] = None,
        on_exit: Optional[Callable[[int, str], Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream the session's output, starting with its retained scrollback.

        Async generator yielding the same event dicts as the sync ``stream``.
        ``on_data`` and ``on_exit`` may be coroutine functions.
        """
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)

        response = await self._req(
            "GET", f"runtime/{runtime_id}/pty/{session_id}/stream", stream=True
        )
        try:
            async for body in aiter_sse_payloads(response.aiter_lines()):
                evt = _decode_event(body)
                if evt is None:
                    continue
                kind = evt.get("type")
                if kind == PTY_EVENT_DATA and on_data is not None:
                    maybe = on_data(evt.get("data") or b"")
                    if inspect.isawaitable(maybe):
                        await maybe
                elif kind == PTY_EVENT_EXIT and on_exit is not None:
                    maybe = on_exit(int(evt.get("exit_code") or 0), str(evt.get("status") or ""))
                    if inspect.isawaitable(maybe):
                        await maybe
                yield evt
                if kind == PTY_EVENT_EXIT:
                    break
        finally:
            await response.aclose()

    async def kill(self, runtime_id: str, session_id: str) -> bool:
        """Terminate the session and release its resources."""
        _validate_runtime_id(runtime_id)
        _validate_session_id(session_id)
        response = await self._req("DELETE", f"runtime/{runtime_id}/pty/{session_id}")
        return bool(response.json().get("success", True))

    def handle(self, runtime_id: str, session_id: str) -> AsyncPtyHandle:
        """Return an :class:`AsyncPtyHandle` for an existing session.

        Creating a handle performs no I/O, so this is a plain (non-awaitable) call.
        """
        return AsyncPtyHandle(self, runtime_id, session_id)
