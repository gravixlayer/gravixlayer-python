"""Parallel HTTP/2 lane transport.

``httpx`` multiplexes every request for an origin over a single HTTP/2
connection. Whatever the peer serialises per connection — request
dispatch, response parsing, socket I/O — then applies to every request in
a burst. This transport keeps up to :data:`H2_LANES` connections instead,
each inside its own pool: the first request to find every live lane
already carrying :data:`H2_LANE_DEPTH` in-flight requests fills the pool
at once, so a burst lands on fresh connections whose handshakes run in
parallel, while sequential callers reuse the first lane forever.

A lane whose connection fails is dropped and redialled; a request that was
never sent (the dial itself failed) is safe to put on another lane, but a
request that may have reached the server is never replayed. When an origin
answers every lane over HTTP/1.1 the pool routes through a shared plain
HTTP/1.1 transport instead of forcing single-stream lanes.
"""

from __future__ import annotations

import os
import socket
import ssl
import threading
from operator import attrgetter
from typing import AsyncIterator, Callable, Dict, Iterator, List, Optional, Tuple

import httpx

# Connection budget per origin. Four lanes is enough to spread a burst over
# the server's connection-bound work without paying four handshakes for
# callers that never need them.
H2_LANES = 4

# In-flight depth on the least-loaded live lane that proves a burst and
# fills the pool at once.
H2_LANE_DEPTH = 4

# One connection per lane — the lane is the unit of parallelism, so a lane's
# own pool never grows past the single connection it exists to hold.
_LANE_LIMITS = httpx.Limits(
    max_connections=1,
    max_keepalive_connections=1,
    keepalive_expiry=30.0,
)

_H2_VERSION = b"HTTP/2"

_BY_INFLIGHT = attrgetter("inflight")

LaneFactory = Callable[[], httpx.BaseTransport]
AsyncLaneFactory = Callable[[], httpx.AsyncBaseTransport]


def _origin_key(url: httpx.URL) -> Tuple[str, str, int]:
    """Origin triple in the form httpcore keys connections on."""
    port = url.port
    if port is None:
        port = 443 if url.scheme == "https" else 80
    return (url.scheme, url.host, port)


_shared_ssl_lock = threading.Lock()
_ssl_store: Optional[ssl.SSLContext] = None


_PROXY_ENV_VARS = (
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
)


def env_proxy_configured() -> bool:
    """A proxy is set in the environment.

    Lane transports connect directly to the origin; when a proxy is
    configured the plain ``httpx`` client construction keeps honouring it
    (a proxy already owns the upstream connections, so lanes would only add
    extra tunnels to the same place).
    """
    return any(os.environ.get(name) for name in _PROXY_ENV_VARS)


def warm_dns(host: str, port: int = 443) -> None:
    """Resolve ``host`` on a daemon thread so the first connection's lookup
    is already warm in the resolver cache.

    ``getaddrinfo`` walks nsswitch on a cold process; firing it during client
    construction overlaps that walk with whatever the caller does between
    building the client and its first request. A failed answer is discarded —
    the real lookup simply runs again.
    """

    def _resolve() -> None:
        try:
            socket.getaddrinfo(host, port, family=socket.AF_INET)
        except OSError:
            pass

    threading.Thread(target=_resolve, daemon=True).start()


def _shared_ssl_context() -> ssl.SSLContext:
    """One trust store for every lane and client in the process.

    Built on first use and shared thereafter, so the certificate bundle is
    loaded once instead of inside each connection's handshake — and OpenSSL
    can resume TLS sessions across lanes, letting connections after the
    first skip most of the handshake.
    """
    global _ssl_store
    if _ssl_store is None:
        with _shared_ssl_lock:
            if _ssl_store is None:
                _ssl_store = httpx.create_ssl_context()
    return _ssl_store


class _Lane:
    __slots__ = ("transport", "inflight", "saw_h2")

    def __init__(self, transport: httpx.BaseTransport) -> None:
        self.transport = transport
        # Requests whose stream has not fully closed. Counted to stream
        # close, not to headers, so a lane holding a long-lived body does
        # not report itself idle.
        self.inflight = 0
        # True once this lane answered HTTP/2: used to learn that an origin
        # only speaks HTTP/1.1 without demoting it on a single lane's ALPN.
        self.saw_h2 = False


class _Pool:
    __slots__ = ("lanes", "h1_only")

    def __init__(self) -> None:
        self.lanes: List[_Lane] = []
        self.h1_only = False


class _CountedSyncStream(httpx.SyncByteStream):
    """Releases the lane once the body is consumed or the response closes."""

    def __init__(self, stream: httpx.SyncByteStream, release: Callable[[], None]) -> None:
        self._stream = stream
        self._release = release

    def __iter__(self) -> Iterator[bytes]:
        try:
            for chunk in self._stream:
                yield chunk
        finally:
            self._release()

    def close(self) -> None:
        try:
            self._stream.close()
        finally:
            self._release()


class _CountedAsyncStream(httpx.AsyncByteStream):
    """Async form of :class:`_CountedSyncStream`."""

    def __init__(self, stream: httpx.AsyncByteStream, release: Callable[[], None]) -> None:
        self._stream = stream
        self._release = release

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            async for chunk in self._stream:
                yield chunk
        finally:
            self._release()

    async def aclose(self) -> None:
        try:
            await self._stream.aclose()
        finally:
            self._release()


class LanesTransport(httpx.BaseTransport):
    """Sync transport: up to ``H2_LANES`` parallel connections per origin.

    A lane is one ``httpx.HTTPTransport`` whose pool holds a single
    connection, so each lane owns exactly one HTTP/2 session — or one
    HTTP/1.1 socket when the origin does not negotiate ``h2``.
    """

    def __init__(
        self,
        *,
        http2: bool = True,
        verify: ssl.SSLContext | str | bool = True,
        cert=None,
        trust_env: bool = True,
        fallback_limits: Optional[httpx.Limits] = None,
        lane_factory: Optional[LaneFactory] = None,
        fallback: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._http2 = http2
        self._cert = cert
        self._trust_env = trust_env
        # The trust store is built here — while the client constructs —
        # rather than inside the first request's handshake, and every lane
        # shares it so TLS session state resumes across lanes.
        self._ssl_context = _shared_ssl_context() if verify is True else verify
        self._fallback = fallback or httpx.HTTPTransport(
            verify=self._ssl_context,
            cert=cert,
            trust_env=trust_env,
            http1=True,
            http2=False,
            limits=fallback_limits if fallback_limits is not None else httpx.Limits(),
        )
        self._lane_factory = lane_factory
        self._pools: Dict[Tuple[str, str, int], _Pool] = {}
        self._lock = threading.Lock()
        self._closed = False

    def _new_lane(self) -> _Lane:
        factory = self._lane_factory or (
            lambda: httpx.HTTPTransport(
                verify=self._ssl_context,
                cert=self._cert,
                trust_env=self._trust_env,
                http1=True,
                http2=True,
                limits=_LANE_LIMITS,
            )
        )
        return _Lane(factory())

    def _open(self, pool: _Pool) -> _Lane:
        lane = self._new_lane()
        pool.lanes.append(lane)
        return lane

    def _drop(self, pool: _Pool, lane: _Lane) -> None:
        try:
            lane.transport.close()
        except Exception:
            pass
        with self._lock:
            try:
                pool.lanes.remove(lane)
            except ValueError:
                pass

    def _acquire(self, origin: Tuple[str, str, int]) -> Tuple[_Pool, _Lane]:
        """Pool lookup plus the least-loaded lane pick, under one lock.

        A live lane at :data:`H2_LANE_DEPTH` in-flight proves a burst and
        fills the rest of the pool at once — staggering the opens would hand
        each following request its own fresh handshake.
        """
        with self._lock:
            pool = self._pools.get(origin)
            if pool is None:
                pool = self._pools[origin] = _Pool()
            lane = min(pool.lanes, key=_BY_INFLIGHT, default=None)
            if lane is None:
                lane = self._open(pool)
            elif len(pool.lanes) < H2_LANES and lane.inflight >= H2_LANE_DEPTH:
                lane = self._open(pool)
                while len(pool.lanes) < H2_LANES:
                    self._open(pool)
            lane.inflight += 1
            return pool, lane

    def ensure_pool(self, url: httpx.URL) -> None:
        """Fill the lane pool for ``url``'s origin without sending a request."""
        if not self._http2 or url.scheme != "https" or self._closed:
            return
        origin = _origin_key(url)
        with self._lock:
            pool = self._pools.get(origin)
            if pool is None:
                pool = self._pools[origin] = _Pool()
            if not pool.h1_only:
                while len(pool.lanes) < H2_LANES:
                    self._open(pool)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._closed:
            raise RuntimeError("Cannot send a request, as the transport has been closed.")
        url = request.url
        if not self._http2 or url.scheme != "https":
            return self._fallback.handle_request(request)

        origin = _origin_key(url)
        pool = self._pools.get(origin)
        if pool is not None and pool.h1_only:
            return self._fallback.handle_request(request)

        attempts = 0
        while True:
            pool, lane = self._acquire(origin)
            released = False

            def release() -> None:
                nonlocal released
                if not released:
                    released = True
                    with self._lock:
                        lane.inflight -= 1

            try:
                response = lane.transport.handle_request(request)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                # Never reached the wire: any lane may safely take it. A live
                # lane gets the redial straight away; with none left the
                # origin is down, and one redial is enough — the caller's
                # retry policy, not the pool, decides what happens next.
                release()
                self._drop(pool, lane)
                attempts += 1
                if pool.lanes or attempts < 2:
                    continue
                raise
            except httpx.TimeoutException:
                # A timeout is not a dead connection — the lane stays.
                release()
                raise
            except httpx.TransportError:
                # Possibly sent: drop the dead lane but never replay.
                release()
                self._drop(pool, lane)
                raise
            except BaseException:
                release()
                raise

            version = response.extensions.get("http_version")
            if version == _H2_VERSION:
                lane.saw_h2 = True
            elif version is not None and not any(entry.saw_h2 for entry in pool.lanes):
                pool.h1_only = True

            # A fully buffered response (is_closed already) frees the lane at
            # once; a live stream holds it until the body is consumed or the
            # response closes.
            if response.is_closed:
                release()
            else:
                response.stream = _CountedSyncStream(response.stream, release)
            return response

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._lock:
            pools = list(self._pools.values())
            self._pools.clear()
        for pool in pools:
            for lane in pool.lanes:
                try:
                    lane.transport.close()
                except Exception:
                    pass
        self._fallback.close()


class AsyncLanesTransport(httpx.AsyncBaseTransport):
    """Async form of :class:`LanesTransport`."""

    def __init__(
        self,
        *,
        http2: bool = True,
        verify: ssl.SSLContext | str | bool = True,
        cert=None,
        trust_env: bool = True,
        fallback_limits: Optional[httpx.Limits] = None,
        lane_factory: Optional[AsyncLaneFactory] = None,
        fallback: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._http2 = http2
        self._cert = cert
        self._trust_env = trust_env
        self._ssl_context = _shared_ssl_context() if verify is True else verify
        self._fallback = fallback or httpx.AsyncHTTPTransport(
            verify=self._ssl_context,
            cert=cert,
            trust_env=trust_env,
            http1=True,
            http2=False,
            limits=fallback_limits if fallback_limits is not None else httpx.Limits(),
        )
        self._lane_factory = lane_factory
        self._pools: Dict[Tuple[str, str, int], _Pool] = {}
        # Picking and opening lanes are synchronous sections; coroutines
        # cannot interleave inside them, so no lock is needed.
        self._closed = False

    def _new_lane(self) -> _Lane:
        factory = self._lane_factory or (
            lambda: httpx.AsyncHTTPTransport(
                verify=self._ssl_context,
                cert=self._cert,
                trust_env=self._trust_env,
                http1=True,
                http2=True,
                limits=_LANE_LIMITS,
            )
        )
        return _Lane(factory())

    def _open(self, pool: _Pool) -> _Lane:
        lane = self._new_lane()
        pool.lanes.append(lane)
        return lane

    async def _drop(self, pool: _Pool, lane: _Lane) -> None:
        try:
            await lane.transport.aclose()
        except Exception:
            pass
        try:
            pool.lanes.remove(lane)
        except ValueError:
            pass

    def _acquire(self, origin: Tuple[str, str, int]) -> Tuple[_Pool, _Lane]:
        """Pool lookup plus the least-loaded lane pick — a synchronous
        section, so coroutines cannot interleave inside it and no lock is
        needed. A live lane at :data:`H2_LANE_DEPTH` in-flight proves a
        burst and fills the rest of the pool at once.
        """
        pool = self._pools.get(origin)
        if pool is None:
            pool = self._pools[origin] = _Pool()
        lane = min(pool.lanes, key=_BY_INFLIGHT, default=None)
        if lane is None:
            lane = self._open(pool)
        elif len(pool.lanes) < H2_LANES and lane.inflight >= H2_LANE_DEPTH:
            lane = self._open(pool)
            while len(pool.lanes) < H2_LANES:
                self._open(pool)
        lane.inflight += 1
        return pool, lane

    def ensure_pool(self, url: httpx.URL) -> None:
        """Fill the lane pool for ``url``'s origin without sending a request."""
        if not self._http2 or url.scheme != "https" or self._closed:
            return
        origin = _origin_key(url)
        pool = self._pools.get(origin)
        if pool is None:
            pool = self._pools[origin] = _Pool()
        if not pool.h1_only:
            while len(pool.lanes) < H2_LANES:
                self._open(pool)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self._closed:
            raise RuntimeError("Cannot send a request, as the transport has been closed.")
        url = request.url
        if not self._http2 or url.scheme != "https":
            return await self._fallback.handle_async_request(request)

        origin = _origin_key(url)
        pool = self._pools.get(origin)
        if pool is not None and pool.h1_only:
            return await self._fallback.handle_async_request(request)

        attempts = 0
        while True:
            pool, lane = self._acquire(origin)
            released = False

            def release() -> None:
                nonlocal released
                if not released:
                    released = True
                    lane.inflight -= 1

            try:
                response = await lane.transport.handle_async_request(request)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                # Never reached the wire: any lane may safely take it. A live
                # lane gets the redial straight away; with none left the
                # origin is down, and one redial is enough — the caller's
                # retry policy, not the pool, decides what happens next.
                release()
                await self._drop(pool, lane)
                attempts += 1
                if pool.lanes or attempts < 2:
                    continue
                raise
            except httpx.TimeoutException:
                # A timeout is not a dead connection — the lane stays.
                release()
                raise
            except httpx.TransportError:
                # Possibly sent: drop the dead lane but never replay.
                release()
                await self._drop(pool, lane)
                raise
            except BaseException:
                release()
                raise

            version = response.extensions.get("http_version")
            if version == _H2_VERSION:
                lane.saw_h2 = True
            elif version is not None and not any(entry.saw_h2 for entry in pool.lanes):
                pool.h1_only = True

            # A fully buffered response (is_closed already) frees the lane at
            # once; a live stream holds it until the body is consumed or the
            # response closes.
            if response.is_closed:
                release()
            else:
                response.stream = _CountedAsyncStream(response.stream, release)
            return response

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        pools = list(self._pools.values())
        self._pools.clear()
        for pool in pools:
            for lane in pool.lanes:
                try:
                    await lane.transport.aclose()
                except Exception:
                    pass
        await self._fallback.aclose()


# The certificate bundle takes ~10ms to load; start it while the module
# finishes importing so a first-ever request never waits on trust-store I/O.
threading.Thread(target=_shared_ssl_context, daemon=True).start()
