"""
Internal runtime module for GravixLayer A2A server.

The public helpers in this module expose GravixLayer-managed agents through the
A2A protocol without requiring users to write custom AgentExecutor wrappers.
User-supplied executors are still supported as an escape hatch.
"""

from __future__ import annotations

import copy
import inspect
import json
import logging
import os
import uuid
from importlib.metadata import PackageNotFoundError, version as pkg_version
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from a2a.server.agent_execution import AgentExecutor
    from a2a.server.tasks import TaskStore
    from starlette.applications import Starlette
    from starlette.routing import Route

logger = logging.getLogger("gravixlayer.a2a")

_MIN_A2A_SDK_VERSION = "1.0.0"
_A2A_PROTOCOL_VERSION = "1.0"
_DEFAULT_A2A_PORT = 8000
_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_A2A_PATH = "/a2a"
_AGENT_CARD_WELL_KNOWN_PATH = "/.well-known/agent-card.json"
_AGENT_METADATA_PATH = "/var/run/gravixlayer/agent-id"
_AGENT_DOMAIN = "agents.gravixlayer.ai"


class GravixLayerA2AError(Exception):
    """Raised when the A2A runtime encounters a configuration error."""


def _check_a2a_sdk_available() -> None:
    try:
        import a2a  # noqa: F401
    except ImportError:
        raise GravixLayerA2AError(
            "a2a-sdk is required for A2A protocol support. " 'Install it with: pip install "gravixlayer[a2a]"'
        ) from None

    try:
        from packaging.version import Version
    except ImportError:
        return

    try:
        installed = pkg_version("a2a-sdk")
    except PackageNotFoundError:
        return

    if Version(installed) < Version(_MIN_A2A_SDK_VERSION):
        raise GravixLayerA2AError(
            f"a2a-sdk>={_MIN_A2A_SDK_VERSION} required, found {installed}. "
            f'Upgrade with: pip install "a2a-sdk>={_MIN_A2A_SDK_VERSION}"'
        )


def _read_agent_id() -> Optional[str]:
    try:
        with open(_AGENT_METADATA_PATH, encoding="utf-8") as f:
            value = f.read().strip()
            return value if value else None
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _platform_agent_url() -> Optional[str]:
    explicit_url = os.environ.get("GRAVIXLAYER_AGENT_URL")
    if explicit_url:
        return explicit_url.rstrip("/")

    agent_id = os.environ.get("GRAVIXLAYER_AGENT_ID") or _read_agent_id()
    if agent_id:
        return f"https://{agent_id}.{_AGENT_DOMAIN}"
    return None


def _platform_a2a_url(rpc_path: str = _DEFAULT_A2A_PATH) -> Optional[str]:
    base_url = _platform_agent_url()
    if not base_url:
        return None
    return f"{base_url}{rpc_path}"


def _normalize_modes(values: Any, default: list[str]) -> list[str]:
    if not values:
        return list(default)
    aliases = {
        "text": "text/plain",
        "json": "application/json",
    }
    modes: list[str] = []
    for value in values:
        mode = aliases.get(str(value).strip().lower(), str(value).strip())
        if mode and mode not in modes:
            modes.append(mode)
    return modes or list(default)


def _make_capabilities(
    streaming: bool = True,
    push_notifications: bool = False,
    extended_agent_card: bool = False,
) -> Any:
    from a2a.types import AgentCapabilities

    try:
        return AgentCapabilities(
            streaming=streaming,
            push_notifications=push_notifications,
            extended_agent_card=extended_agent_card,
        )
    except (TypeError, ValueError):
        try:
            return AgentCapabilities(
                streaming=streaming,
                pushNotifications=push_notifications,
                extendedAgentCard=extended_agent_card,
            )
        except (TypeError, ValueError):
            return AgentCapabilities(
                streaming=streaming,
                pushNotifications=push_notifications,
            )


def _make_agent_interface(url: str) -> Any:
    try:
        from a2a.types import AgentInterface
    except ImportError:
        return None

    try:
        return AgentInterface(
            url=url,
            protocol_binding="JSONRPC",
            protocol_version=_A2A_PROTOCOL_VERSION,
        )
    except (TypeError, ValueError) as exc:
        raise GravixLayerA2AError("a2a-sdk>=1.0.0 is required for A2A v1 AgentInterface support") from exc


def _make_skill(skill: Any) -> Any:
    from a2a.types import AgentSkill

    if isinstance(skill, dict):
        data = skill
    else:
        data = {
            "id": getattr(skill, "id", ""),
            "name": getattr(skill, "name", ""),
            "description": getattr(skill, "description", ""),
            "tags": getattr(skill, "tags", []),
            "examples": getattr(skill, "examples", []),
            "input_modes": getattr(skill, "input_modes", []),
            "output_modes": getattr(skill, "output_modes", []),
            "security_requirements": getattr(skill, "security_requirements", []),
        }

    tags = list(data.get("tags") or [])
    if not tags:
        tags = ["general"]

    kwargs = {
        "id": str(data.get("id") or "default"),
        "name": str(data.get("name") or "Agent"),
        "description": str(data.get("description") or data.get("name") or "Agent capability"),
        "tags": tags,
        "examples": list(data.get("examples") or []),
    }
    input_modes = data.get("input_modes") or data.get("inputModes")
    output_modes = data.get("output_modes") or data.get("outputModes")
    security_requirements = data.get("security_requirements") or data.get("securityRequirements")
    if input_modes:
        kwargs["input_modes"] = list(input_modes)
    if output_modes:
        kwargs["output_modes"] = list(output_modes)
    if security_requirements:
        kwargs["security_requirements"] = list(security_requirements)

    try:
        return AgentSkill(**kwargs)
    except TypeError:
        kwargs.pop("input_modes", None)
        kwargs.pop("output_modes", None)
        kwargs.pop("security_requirements", None)
        return AgentSkill(**kwargs)


def _default_agent_card(name: str = "GravixLayer Agent", description: str = "") -> dict[str, Any]:
    return {
        "name": name or "GravixLayer Agent",
        "description": description or f"Managed GravixLayer agent {name or 'agent'}",
        "version": "1.0.0",
        "skills": [
            {
                "id": "default",
                "name": "Agent",
                "description": description or "General agent capability",
                "tags": ["general"],
            }
        ],
        "capabilities": {"streaming": True, "push_notifications": False},
        "default_input_modes": ["text/plain", "application/json"],
        "default_output_modes": ["text/plain"],
    }


def _dict_from_card(card: Any) -> dict[str, Any]:
    if isinstance(card, dict):
        return dict(card)
    if hasattr(card, "to_dict"):
        return card.to_dict()
    if hasattr(card, "model_dump"):
        return card.model_dump(exclude_none=True)
    if hasattr(card, "dict"):
        return card.dict(exclude_none=True)
    raise GravixLayerA2AError(
        "agent_card must be a GravixLayer AgentCard, dict, or a2a-sdk AgentCard. " f"Got: {type(card).__name__}"
    )


def _convert_agent_card(card: Any, *, url: str = "") -> Any:
    from a2a.types import AgentCard as A2AAgentCard

    if isinstance(card, A2AAgentCard):
        return _with_agent_card_url(card, url or _platform_a2a_url() or "")

    card_dict = _dict_from_card(card)
    caps = card_dict.get("capabilities") or {}
    streaming = bool(caps.get("streaming", card_dict.get("streaming", True)))
    push_notifications = bool(
        caps.get("push_notifications", caps.get("pushNotifications", card_dict.get("push_notifications", False)))
    )
    extended_agent_card = bool(
        caps.get("extended_agent_card", caps.get("extendedAgentCard", card_dict.get("extended_agent_card", False)))
    )
    public_url = url or card_dict.get("url") or _platform_a2a_url() or ""
    skills = [_make_skill(skill) for skill in card_dict.get("skills", [])]
    if not skills:
        skills = [_make_skill({"id": "default", "name": "Agent", "description": card_dict.get("description", "")})]

    common = {
        "name": card_dict.get("name", "GravixLayer Agent"),
        "description": card_dict.get("description", ""),
        "version": card_dict.get("version", "1.0.0"),
        "skills": skills,
        "capabilities": _make_capabilities(
            streaming=streaming,
            push_notifications=push_notifications,
            extended_agent_card=extended_agent_card,
        ),
    }
    input_modes = _normalize_modes(
        card_dict.get("default_input_modes") or card_dict.get("defaultInputModes"), ["text/plain", "application/json"]
    )
    output_modes = _normalize_modes(
        card_dict.get("default_output_modes") or card_dict.get("defaultOutputModes"), ["text/plain"]
    )

    agent_interface = _make_agent_interface(public_url) if public_url else None

    try:
        return A2AAgentCard(
            **common,
            supported_interfaces=[agent_interface] if agent_interface is not None else [],
            default_input_modes=input_modes,
            default_output_modes=output_modes,
        )
    except (TypeError, ValueError) as exc:
        raise GravixLayerA2AError("a2a-sdk>=1.0.0 is required for A2A v1 AgentCard support") from exc


def _interface_binding(interface: Any) -> str:
    value = getattr(interface, "protocol_binding", None)
    if value is None:
        value = getattr(interface, "protocolBinding", None)
    if value is None:
        value = getattr(interface, "transport", None)
    return str(value or "").upper()


def _configure_agent_interface(interface: Any, url: str) -> None:
    if hasattr(interface, "url"):
        setattr(interface, "url", url)
    if hasattr(interface, "protocol_binding") and not getattr(interface, "protocol_binding", None):
        setattr(interface, "protocol_binding", "JSONRPC")
    if hasattr(interface, "protocol_version"):
        setattr(interface, "protocol_version", _A2A_PROTOCOL_VERSION)


def _with_agent_card_url(card: Any, url: str) -> Any:
    if not url:
        return card
    result = copy.deepcopy(card)
    if hasattr(result, "supported_interfaces"):
        interfaces = list(getattr(result, "supported_interfaces", []) or [])
        for interface in interfaces:
            if _interface_binding(interface) in ("", "JSONRPC"):
                _configure_agent_interface(interface, url)
                return result
        agent_interface = _make_agent_interface(url)
        if agent_interface is not None:
            result.supported_interfaces.extend([agent_interface])
    return result


def _make_card_modifier(async_modifier: bool = False, rpc_path: str = _DEFAULT_A2A_PATH):
    def modifier(card: Any) -> Any:
        return _with_agent_card_url(card, _platform_a2a_url(rpc_path) or "")

    if not async_modifier:
        return modifier

    async def async_modifier_fn(card: Any) -> Any:
        return modifier(card)

    return async_modifier_fn


def _message_to_input(message: Any, text: str) -> Any:
    if message is None:
        return {"message": text} if text else {}

    parts: list[dict[str, Any]] = []
    data_parts: list[Any] = []
    try:
        from google.protobuf.json_format import MessageToDict
    except ImportError:
        MessageToDict = None  # type: ignore[assignment]

    for part in getattr(message, "parts", []) or []:
        if part.HasField("text"):
            parts.append({"type": "text", "text": part.text})
            continue
        if part.HasField("data"):
            value = MessageToDict(part.data) if MessageToDict else str(part.data)
            data_parts.append(value)
            parts.append({"type": "data", "data": value})
            continue
        if part.HasField("url"):
            parts.append({"type": "url", "url": part.url})
        elif part.HasField("raw"):
            parts.append({"type": "raw", "raw": part.raw})

    if data_parts and not text and len(data_parts) == 1:
        return data_parts[0]
    if len(parts) == 1 and parts[0].get("type") == "text":
        return {"message": parts[0]["text"]}
    return {"message": text, "parts": parts}


def _request_body_from_context(context: Any, input_payload: Any) -> dict[str, Any]:
    thread_id = context.context_id or context.task_id or str(uuid.uuid4())
    metadata = dict(getattr(context, "metadata", {}) or {})
    config = metadata.get("config") if isinstance(metadata.get("config"), dict) else {}
    if _is_resume_context(context):
        return {
            "resume": input_payload,
            "thread_id": thread_id,
            "session_id": thread_id,
            "config": config,
            "metadata": metadata,
        }
    return {
        "input": input_payload,
        "thread_id": thread_id,
        "session_id": thread_id,
        "config": config,
        "metadata": metadata,
    }


def _is_resume_context(context: Any) -> bool:
    task = getattr(context, "current_task", None)
    if task is None or not getattr(task, "status", None):
        return False
    try:
        from a2a.types import TaskState

        return task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
    except Exception:
        return False


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _invoke_gravix_app(app: Any, body: dict[str, Any]) -> Any:
    adapter = getattr(app, "_adapter", None)
    if adapter is not None:
        if hasattr(adapter, "handle_request"):
            return await _maybe_await(adapter.handle_request(body))
        if hasattr(adapter, "handle_invoke"):
            return await _maybe_await(adapter.handle_invoke(body.get("input", {}), body.get("config", {})))

    handler = getattr(app, "_handler", None)
    if handler is not None and hasattr(app, "_call_handler"):
        return await _maybe_await(app._call_handler(handler, body.get("input", {}), body.get("config", {})))

    if callable(app):
        return await _maybe_await(app(body.get("input", body)))

    raise GravixLayerA2AError("No GravixLayer handler or framework adapter is available for A2A")


async def _emit_task_status(
    event_queue: Any,
    context: Any,
    task_id: str,
    context_id: str,
    state: Any,
    text: str,
) -> None:
    from a2a.helpers.proto_helpers import new_task, new_text_status_update_event
    from a2a.types import TaskState

    if getattr(context, "current_task", None) is None:
        history = [context.message] if getattr(context, "message", None) is not None else []
        await event_queue.enqueue_event(new_task(task_id, context_id, TaskState.TASK_STATE_WORKING, history=history))
    await event_queue.enqueue_event(new_text_status_update_event(task_id, context_id, state, text))


def _is_interrupted_result(result: Any) -> bool:
    return isinstance(result, dict) and result.get("status") == "interrupted"


def _interrupt_prompt(result: Any) -> str:
    if not isinstance(result, dict):
        return "Additional input is required."
    prompt = result.get("prompt") or result.get("interrupts") or "Additional input is required."
    return _stringify(prompt)


def _result_to_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, dict):
        for key in ("output", "result", "response", "text", "content", "message"):
            if key in result and result[key] is not None:
                return _stringify(result[key])
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            return _stringify(messages[-1])
    return _stringify(result)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "content"):
        return str(getattr(value, "content"))
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except TypeError:
        return str(value)


class GravixLayerA2AExecutor:
    """Generic A2A executor that delegates to a GravixApp or compatible object."""

    def __init__(self, app: Any) -> None:
        self._app = app

    async def execute(self, context: Any, event_queue: Any) -> None:
        from a2a.types import TaskState

        task_id = context.task_id or str(uuid.uuid4())
        context_id = context.context_id or task_id
        user_input = _message_to_input(context.message, context.get_user_input())
        body = _request_body_from_context(context, user_input)

        try:
            result = await _invoke_gravix_app(self._app, body)
        except Exception as exc:
            logger.exception("A2A agent invocation failed")
            await _emit_task_status(
                event_queue,
                context,
                task_id,
                context_id,
                TaskState.TASK_STATE_FAILED,
                f"Agent error: {exc}",
            )
            return

        if _is_interrupted_result(result):
            await _emit_task_status(
                event_queue,
                context,
                task_id,
                context_id,
                TaskState.TASK_STATE_INPUT_REQUIRED,
                _interrupt_prompt(result),
            )
            return

        await _emit_task_status(
            event_queue,
            context,
            task_id,
            context_id,
            TaskState.TASK_STATE_COMPLETED,
            _result_to_text(result),
        )

    async def cancel(self, context: Any, event_queue: Any) -> None:
        from a2a.types import TaskState

        task_id = context.task_id or str(uuid.uuid4())
        context_id = context.context_id or task_id
        await _emit_task_status(
            event_queue,
            context,
            task_id,
            context_id,
            TaskState.TASK_STATE_CANCELED,
            "Task canceled.",
        )


def create_gravix_app_executor(app: Any) -> "AgentExecutor":
    _check_a2a_sdk_available()
    from a2a.server.agent_execution import AgentExecutor

    class _Executor(GravixLayerA2AExecutor, AgentExecutor):
        pass

    return _Executor(app)


def _make_request_handler(executor: "AgentExecutor", agent_card: Any, task_store: Optional["TaskStore"]) -> Any:
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.tasks import InMemoryTaskStore

    if task_store is None:
        task_store = InMemoryTaskStore()

    signature = inspect.signature(DefaultRequestHandler)
    kwargs: dict[str, Any] = {
        "agent_executor": executor,
        "task_store": task_store,
    }
    if "agent_card" in signature.parameters:
        kwargs["agent_card"] = agent_card
    if "queue_manager" in signature.parameters:
        try:
            from a2a.server.events import InMemoryQueueManager

            kwargs["queue_manager"] = InMemoryQueueManager()
        except Exception:
            pass
    return DefaultRequestHandler(**kwargs)


def create_a2a_routes(
    executor: "AgentExecutor",
    agent_card: Any,
    *,
    task_store: Optional["TaskStore"] = None,
    rpc_path: str = _DEFAULT_A2A_PATH,
    include_health: bool = True,
) -> list["Route"]:
    _check_a2a_sdk_available()

    from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    a2a_card = _convert_agent_card(agent_card, url=_platform_a2a_url(rpc_path) or "")
    request_handler = _make_request_handler(executor, a2a_card, task_store)
    card_modifier = _make_card_modifier(async_modifier=True, rpc_path=rpc_path)

    routes: list[Route] = []
    if include_health:

        async def health(request: Any) -> Any:
            return JSONResponse({"status": "healthy", "protocol": "a2a"}, status_code=200)

        routes.append(Route("/health", health, methods=["GET"]))

    routes.extend(
        create_agent_card_routes(
            a2a_card,
            card_modifier=card_modifier,
            card_url=_AGENT_CARD_WELL_KNOWN_PATH,
        )
    )
    routes.extend(create_jsonrpc_routes(request_handler, rpc_url=rpc_path, enable_v0_3_compat=False))
    return routes


def create_gravix_app_a2a_routes(
    app: Any,
    *,
    agent_card: Any | None = None,
    task_store: Optional["TaskStore"] = None,
    rpc_path: str = _DEFAULT_A2A_PATH,
) -> list["Route"]:
    card = agent_card or _default_agent_card(getattr(app, "name", "GravixLayer Agent"))
    executor = create_gravix_app_executor(app)
    return create_a2a_routes(
        executor,
        card,
        task_store=task_store,
        rpc_path=rpc_path,
        include_health=False,
    )


def create_a2a_app(
    executor: "AgentExecutor",
    agent_card: Any,
    *,
    task_store: Optional["TaskStore"] = None,
    rpc_path: str = _DEFAULT_A2A_PATH,
) -> "Starlette":
    _check_a2a_sdk_available()

    from starlette.applications import Starlette

    routes = create_a2a_routes(
        executor,
        agent_card,
        task_store=task_store,
        rpc_path=rpc_path,
        include_health=True,
    )
    return Starlette(routes=routes)


def run_a2a(
    executor: "AgentExecutor",
    agent_card: Any,
    *,
    port: int = _DEFAULT_A2A_PORT,
    host: str = _DEFAULT_HOST,
    task_store: Optional["TaskStore"] = None,
    log_level: str = "info",
    rpc_path: str = _DEFAULT_A2A_PATH,
) -> None:
    _check_a2a_sdk_available()

    try:
        import uvicorn
    except ImportError:
        raise GravixLayerA2AError(
            "uvicorn is required for run_a2a(). " 'Install it with: pip install "gravixlayer[a2a]"'
        ) from None

    app = create_a2a_app(
        executor=executor,
        agent_card=agent_card,
        task_store=task_store,
        rpc_path=rpc_path,
    )

    logger.info("Starting GravixLayer A2A server on %s:%d", host, port)
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level=log_level,
        workers=1,
        reload=False,
        access_log=True,
        timeout_graceful_shutdown=10,
    )
    uvicorn.Server(config).run()
