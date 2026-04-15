"""
Internal runtime module for GravixLayer A2A server.

Wraps the ``a2a-sdk`` to provide ``run_a2a()`` and ``create_a2a_app()``
functions that expose any agent as an A2A-compliant JSON-RPC server.

All a2a-sdk imports are lazy — this module only imports when called,
so users without the ``[a2a]`` extra do not hit ImportErrors at
SDK import time.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from a2a.server.agent_execution import AgentExecutor
    from a2a.server.tasks import TaskStore
    from starlette.applications import Starlette

logger = logging.getLogger("gravixlayer.a2a")

# Minimum required a2a-sdk version (must support A2AStarletteApplication)
_MIN_A2A_SDK_VERSION = "0.2.7"

# Default port for A2A protocol server.
# Aligned with GravixApp RuntimeConfig.port (8000) and the platform's
# default port detection so that auto-generated ready_cmd health checks
# connect to the correct port without explicit user configuration.
_DEFAULT_A2A_PORT = 8000

# Default host binding — 0.0.0.0 to accept connections from the platform.
_DEFAULT_HOST = "0.0.0.0"


class GravixLayerA2AError(Exception):
    """Raised when the A2A runtime encounters a configuration error."""


def _check_a2a_sdk_available() -> None:
    """Verify that a2a-sdk is installed with required extras.

    Raises:
        GravixLayerA2AError: If a2a-sdk is not installed or version is too old.
    """
    try:
        import a2a  # noqa: F401
    except ImportError:
        raise GravixLayerA2AError(
            "a2a-sdk is required for A2A protocol support. "
            'Install it with: pip install "gravixlayer[a2a]"'
        ) from None

    try:
        from importlib.metadata import version as pkg_version
        installed = pkg_version("a2a-sdk")
        # Simple version comparison (major.minor.patch)
        from packaging.version import Version
        if Version(installed) < Version(_MIN_A2A_SDK_VERSION):
            raise GravixLayerA2AError(
                f"a2a-sdk>={_MIN_A2A_SDK_VERSION} required, "
                f"found {installed}. Upgrade with: "
                f'pip install "a2a-sdk>={_MIN_A2A_SDK_VERSION}"'
            )
    except ImportError:
        # packaging not available — skip version check, best-effort
        pass
    except Exception:
        # importlib.metadata not available on very old Python — skip
        pass


def _convert_agent_card(
    card: Any,
    *,
    url: str = "",
) -> Any:
    """Convert a GravixLayer AgentCard to an a2a-sdk AgentCard.

    Handles both GravixLayer ``AgentCard`` dataclass and raw ``dict``
    representations. If the input is already an a2a-sdk ``AgentCard``,
    passes it through unchanged.

    Args:
        card: A GravixLayer AgentCard, dict, or a2a-sdk AgentCard.
        url: The base URL for the agent card.

    Returns:
        An a2a-sdk AgentCard instance.
    """
    from a2a.types import AgentCard as A2AAgentCard, AgentSkill as A2ASkill
    from a2a.types import AgentCapabilities

    # Already an a2a-sdk AgentCard — pass through
    if isinstance(card, A2AAgentCard):
        return card

    # Convert from dict
    if isinstance(card, dict):
        card_dict = card
    elif hasattr(card, "to_dict"):
        card_dict = card.to_dict()
    else:
        raise GravixLayerA2AError(
            f"agent_card must be a GravixLayer AgentCard, dict, or "
            f"a2a-sdk AgentCard. Got: {type(card).__name__}"
        )

    skills = []
    for s in card_dict.get("skills", []):
        if isinstance(s, dict):
            skills.append(A2ASkill(
                id=s.get("id", ""),
                name=s.get("name", ""),
                description=s.get("description", ""),
                tags=s.get("tags", []),
                examples=s.get("examples", []),
            ))
        elif hasattr(s, "id"):
            skills.append(A2ASkill(
                id=s.id,
                name=s.name,
                description=getattr(s, "description", ""),
                tags=getattr(s, "tags", []),
                examples=getattr(s, "examples", []),
            ))

    capabilities = AgentCapabilities(
        streaming=card_dict.get("streaming", False),
        pushNotifications=card_dict.get("push_notifications", False),
    )

    return A2AAgentCard(
        name=card_dict.get("name", "GravixLayer Agent"),
        description=card_dict.get("description", ""),
        url=url,
        version=card_dict.get("version", "1.0.0"),
        skills=skills,
        capabilities=capabilities,
        defaultInputModes=card_dict.get("default_input_modes", ["text"]),
        defaultOutputModes=card_dict.get("default_output_modes", ["text"]),
    )


def create_a2a_app(
    executor: "AgentExecutor",
    agent_card: Any,
    *,
    task_store: Optional["TaskStore"] = None,
) -> "Starlette":
    """Build a Starlette ASGI application serving the A2A protocol.

    This returns an ASGI app that can be mounted into an existing server
    or run standalone with uvicorn. Use this when you need fine-grained
    control over the server lifecycle (e.g., mounting A2A alongside
    existing HTTP endpoints).

    For the common case of running A2A as the primary server, use
    ``run_a2a()`` instead.

    Args:
        executor: An ``AgentExecutor`` implementation that handles
            ``message/send`` and ``message/stream`` JSON-RPC calls.
            This is framework-agnostic — wrap your LangGraph, CrewAI,
            Google ADK, OpenAI, or plain Python agent in an executor.
        agent_card: Agent Card metadata. Accepts a GravixLayer
            ``AgentCard``, a raw ``dict``, or an a2a-sdk ``AgentCard``.
        task_store: Optional task persistence backend. Defaults to
            ``InMemoryTaskStore`` which is sufficient for single-VM
            deployments (GravixLayer's model).

    Returns:
        A configured Starlette application.

    Raises:
        GravixLayerA2AError: If a2a-sdk is not installed.

    Example::

        from gravixlayer.a2a import create_a2a_app

        app = create_a2a_app(executor=MyExecutor(), agent_card=card)
        # Mount into existing FastAPI/Starlette app or run with uvicorn
    """
    _check_a2a_sdk_available()

    from a2a.server.apps import A2AStarletteApplication
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.tasks import InMemoryTaskStore
    from a2a.server.events import InMemoryQueueManager
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    a2a_card = _convert_agent_card(agent_card)

    if task_store is None:
        task_store = InMemoryTaskStore()

    queue_manager = InMemoryQueueManager()

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
        queue_manager=queue_manager,
    )

    a2a_app = A2AStarletteApplication(
        agent_card=a2a_card,
        http_handler=request_handler,
    )

    # Build the Starlette app with A2A routes + health endpoint.
    async def health(request):
        return JSONResponse(
            {"status": "healthy", "protocol": "a2a"},
            status_code=200,
        )

    routes = [
        Route("/health", health, methods=["GET"]),
    ]

    app = a2a_app.build(routes=routes)
    return app


def run_a2a(
    executor: "AgentExecutor",
    agent_card: Any,
    *,
    port: int = _DEFAULT_A2A_PORT,
    host: str = _DEFAULT_HOST,
    task_store: Optional["TaskStore"] = None,
    log_level: str = "info",
) -> None:
    """Start an A2A-compliant JSON-RPC server using uvicorn.

    This is the primary entrypoint for running an agent as an A2A server
    on GravixLayer. It handles:

    - Building the Starlette ASGI app with A2A protocol routes
    - Starting uvicorn with production-grade settings
    - Signal handling for graceful shutdown
    - Health endpoint at ``/health`` for platform health checks

    The server listens on ``port`` (default 8000). The platform
    routes A2A requests from the public endpoint to this port.

    Args:
        executor: An ``AgentExecutor`` implementation. Framework-agnostic.
        agent_card: Agent Card metadata (GravixLayer AgentCard, dict,
            or a2a-sdk AgentCard).
        port: Port to listen on. Default: 8000. Override if you need
            a different port and set ``a2a_port`` in your deploy config
            to match.
        host: Host to bind to. Default: ``0.0.0.0``.
        task_store: Optional custom task store. Default: in-memory.
        log_level: Uvicorn log level. Default: ``info``.

    Raises:
        GravixLayerA2AError: If a2a-sdk or uvicorn is not installed.

    Example::

        from gravixlayer.a2a import run_a2a
        from a2a.server.agent_execution import AgentExecutor
        from a2a.server.events import EventQueue
        from a2a.server.agent_execution import RequestContext

        class MyExecutor(AgentExecutor):
            async def execute(
                self,
                context: RequestContext,
                event_queue: EventQueue,
            ) -> None:
                user_input = context.get_user_input()
                result = await my_agent.run(user_input)
                await event_queue.enqueue_event(
                    context.new_agent_message(parts=[{"text": result}])
                )

        run_a2a(
            executor=MyExecutor(),
            agent_card=AgentCard(name="My Agent", description="..."),
        )
    """
    _check_a2a_sdk_available()

    try:
        import uvicorn
    except ImportError:
        raise GravixLayerA2AError(
            "uvicorn is required for run_a2a(). "
            'Install it with: pip install "gravixlayer[a2a]"'
        ) from None

    app = create_a2a_app(
        executor=executor,
        agent_card=agent_card,
        task_store=task_store,
    )

    logger.info(
        "Starting GravixLayer A2A server on %s:%d",
        host,
        port,
    )

    # Configure uvicorn with production settings.
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level=log_level,
        # Single worker — one agent instance per runtime.
        workers=1,
        # Disable reload in production.
        reload=False,
        # Access log for observability.
        access_log=True,
        # Timeout for graceful shutdown on SIGTERM.
        timeout_graceful_shutdown=10,
    )

    server = uvicorn.Server(config)

    # uvicorn.Server.run() handles SIGTERM/SIGINT internally.
    server.run()
