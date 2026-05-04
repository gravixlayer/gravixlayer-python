"""GravixApp — unified wrapper that normalizes any agent framework to a
consistent HTTP interface.

Every agent deployed on GravixLayer runs through this wrapper, regardless
of the underlying framework (LangGraph, CrewAI, OpenAI Agents, Google ADK,
or plain Python).  The entrypoint is always ``python -m main``.

Standard routes:
    POST /invoke   — invoke the agent
    GET  /health   — JSON health report
    GET  /ws       — WebSocket for streaming (optional)

Usage::

    from gravixlayer.runtime import GravixApp

    app = GravixApp(name="my-agent")

    # Option A: simple function handler
    @app.entrypoint
    async def handle(input_data):
        return {"result": "hello"}

    # Option B: mount a framework
    app.mount_framework("langgraph", compiled_graph)

    app.run()
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, Callable

from .config import RuntimeConfig
from .health import HealthManager, HealthStatus
from .middleware import CORSMiddleware, RequestMiddleware
from .server import RuntimeServer

logger = logging.getLogger("gravixlayer.runtime")


class GravixApp:
    """Unified agent wrapper — the single entry point for all agents."""

    def __init__(
        self,
        name: str = "gravix-agent",
        config: RuntimeConfig | None = None,
        framework: str | None = None,
    ) -> None:
        self.name = name
        self.config = config or RuntimeConfig.from_env()
        self.health = HealthManager()
        self._handler: Callable | None = None
        self._adapter: Any = None
        self._tools: dict[str, Callable] = {}
        self._framework_name = framework
        self._starlette_app: Any = None
        self._a2a_enabled = False
        self._a2a_agent_card: Any = None

    # ------------------------------------------------------------------
    # Decorators
    # ------------------------------------------------------------------

    def entrypoint(self, fn: Callable | None = None) -> Callable:
        """Register a function as the agent's invoke handler.

        Supports sync, async, generator, and async generator functions.

        Example::

            @app.entrypoint
            async def handle(input_data: dict) -> dict:
                return {"output": "hello"}
        """
        if fn is None:
            # Called with parens: @app.entrypoint()
            return self.entrypoint

        self._handler = fn
        return fn

    def tool(self, fn: Callable | None = None, *, name: str | None = None) -> Callable:
        """Register a tool function."""
        def decorator(f: Callable) -> Callable:
            tool_name = name or f.__name__
            self._tools[tool_name] = f
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

    # ------------------------------------------------------------------
    # Framework mounting
    # ------------------------------------------------------------------

    def mount_framework(
        self, framework_name: str, framework_app: Any, **kwargs: Any
    ) -> None:
        """Mount a framework-specific adapter.

        Args:
            framework_name: One of "langgraph", "crewai", "openai_agents",
                "google_adk".
            framework_app: The framework's app/graph/crew/agent object.
            **kwargs: Framework-specific options.
        """
        from gravixlayer.frameworks import get_adapter_class

        adapter_cls = get_adapter_class(framework_name)
        self._adapter = adapter_cls(framework_app, **kwargs)
        self._framework_name = framework_name
        logger.info("Mounted framework adapter: %s", framework_name)

    def enable_a2a(self, agent_card: Any | None = None) -> None:
        """Expose this app through the platform-managed A2A protocol."""
        self._a2a_enabled = True
        self._a2a_agent_card = agent_card
        self._starlette_app = None

    # ------------------------------------------------------------------
    # ASGI app construction
    # ------------------------------------------------------------------

    def _build_app(self) -> Any:
        """Build the Starlette ASGI application."""
        try:
            from starlette.applications import Starlette
            from starlette.responses import JSONResponse
            from starlette.routing import Route, WebSocketRoute
        except ImportError:
            raise ImportError(
                "starlette is required: pip install 'gravixlayer[runtime]'"
            )

        routes = [
            Route(self.config.health_check_path, self._health_endpoint, methods=["GET"]),
            Route(self.config.invoke_path, self._invoke_endpoint, methods=["POST"]),
            WebSocketRoute(self.config.ws_path, self._ws_endpoint),
        ]

        # Add framework-specific routes
        if self._adapter is not None:
            adapter_routes = self._adapter.get_routes()
            routes.extend(adapter_routes)

        if self._a2a_enabled:
            from gravixlayer.a2a import create_gravix_app_a2a_routes

            routes.extend(
                create_gravix_app_a2a_routes(
                    self,
                    agent_card=self._a2a_agent_card,
                )
            )

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def lifespan(_app: Any):
            # Startup
            if self._adapter is not None:
                await self._adapter.setup()
            self.health.status = HealthStatus.READY
            logger.info("GravixApp '%s' ready", self.name)
            try:
                yield
            finally:
                # Shutdown
                self.health.status = HealthStatus.DRAINING
                if self._adapter is not None:
                    await self._adapter.cleanup()

        app = Starlette(
            routes=routes,
            lifespan=lifespan,
        )

        # Apply middleware
        app = RequestMiddleware(app)
        app = CORSMiddleware(
            app,
            allow_origins=self.config.cors_origins,
            allow_methods=self.config.cors_allow_methods,
            allow_headers=self.config.cors_allow_headers,
        )

        return app

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    async def _health_endpoint(self, request: Any) -> Any:
        from starlette.responses import JSONResponse

        report = self.health.get_report()
        report["name"] = self.name
        if self._framework_name:
            report["framework"] = self._framework_name
        status_code = 200 if self.health.status == HealthStatus.READY else 503
        return JSONResponse(report, status_code=status_code)

    async def _invoke_endpoint(self, request: Any) -> Any:
        from starlette.responses import JSONResponse

        self.health.record_invocation()

        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "Invalid JSON body"}, status_code=400
            )

        input_data = body.get("input", body)
        config_data = body.get("config", {})

        try:
            # Framework adapter takes priority
            if self._adapter is not None:
                if hasattr(self._adapter, "handle_request"):
                    result = await self._adapter.handle_request(body)
                    return JSONResponse(result)
                else:
                    result = await self._adapter.handle_invoke(input_data, config_data)
            elif self._handler is not None:
                result = await self._call_handler(self._handler, input_data, config_data)
            else:
                return JSONResponse(
                    {"error": "No handler registered. Use @app.entrypoint or app.mount_framework()"},
                    status_code=500,
                )

            return JSONResponse({"output": result})

        except Exception as exc:
            self.health.record_error()
            logger.exception("Invoke error")
            return JSONResponse(
                {"error": str(exc)}, status_code=500
            )

    async def _ws_endpoint(self, websocket: Any) -> None:
        await websocket.accept()

        try:
            data = await websocket.receive_json()
            input_data = data.get("input", data)
            config_data = data.get("config", {})

            # Stream from adapter if available
            if self._adapter is not None and hasattr(self._adapter, "handle_stream"):
                async for chunk in self._adapter.handle_stream(input_data, config_data):
                    await websocket.send_json({"chunk": chunk})
            elif self._handler is not None:
                result = await self._call_handler(self._handler, input_data, config_data)
                # If handler is a generator, stream chunks
                if inspect.isasyncgen(result):
                    async for chunk in result:
                        await websocket.send_json({"chunk": chunk})
                elif inspect.isgenerator(result):
                    for chunk in result:
                        await websocket.send_json({"chunk": chunk})
                else:
                    await websocket.send_json({"output": result})
            else:
                await websocket.send_json({"error": "No handler registered"})

            await websocket.send_json({"done": True})
        except Exception as exc:
            self.health.record_error()
            logger.exception("WebSocket error")
            try:
                await websocket.send_json({"error": str(exc)})
            except Exception:
                pass
        finally:
            await websocket.close()

    # ------------------------------------------------------------------
    # Handler invocation
    # ------------------------------------------------------------------

    async def _call_handler(
        self, handler: Callable, input_data: Any, config_data: Any
    ) -> Any:
        """Call a handler function, handling sync/async/generator variants."""
        sig = inspect.signature(handler)
        params = list(sig.parameters)

        # Build args based on handler signature
        if len(params) >= 2:
            args = (input_data, config_data)
        elif len(params) == 1:
            args = (input_data,)
        else:
            args = ()

        if inspect.iscoroutinefunction(handler):
            return await handler(*args)
        elif inspect.isasyncgenfunction(handler):
            # Return the async generator itself — caller handles iteration
            return handler(*args)
        elif inspect.isgeneratorfunction(handler):
            return handler(*args)
        else:
            # Sync function — run in executor
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: handler(*args))

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Build the ASGI app and start the server."""
        self._starlette_app = self._build_app()
        server = RuntimeServer(self.config)
        server.start(self._starlette_app)

    @property
    def asgi_app(self) -> Any:
        """Get the ASGI app (for external servers like gunicorn)."""
        if self._starlette_app is None:
            self._starlette_app = self._build_app()
        return self._starlette_app
