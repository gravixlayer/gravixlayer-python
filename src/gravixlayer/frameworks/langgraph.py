"""LangGraph framework adapter.

Wraps a compiled LangGraph StateGraph and exposes it via standard routes.
"""

from __future__ import annotations

import json
import logging
import importlib
import inspect
import uuid
from typing import Any, AsyncIterator

from .base import BaseFrameworkAdapter

logger = logging.getLogger("gravixlayer.frameworks.langgraph")


class LangGraphAdapter(BaseFrameworkAdapter):
    """Adapter for LangGraph compiled graphs."""

    @property
    def name(self) -> str:
        return "langgraph"

    async def handle_request(self, body: dict[str, Any]) -> Any:
        input_data = body.get("input", {})
        config_data = body.get("config", {})
        thread_id, runnable_config = _build_runnable_config(body, config_data)
        version = _langgraph_version(body, runnable_config)
        graph_input = _build_graph_input(input_data, body)

        try:
            result = await _invoke_graph(self._app, graph_input, runnable_config, version=version)
        except Exception as exc:
            interrupts = _interrupts_from_exception(exc)
            if interrupts:
                return _interrupted_response(
                    thread_id,
                    interrupts,
                    state=await _get_state(self._app, runnable_config),
                )
            raise

        interrupts = _find_interrupts(result)
        if interrupts:
            return _interrupted_response(
                thread_id,
                interrupts,
                state=await _get_state(self._app, runnable_config),
            )

        return {
            "status": "completed",
            "thread_id": thread_id,
            "output": _jsonable(_graph_output_value(result)),
            "state": await _get_state(self._app, runnable_config),
        }

    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        body = {"input": input_data, "config": config or {}}
        return await self.handle_request(body)

    async def handle_stream(self, input_data: Any, config: Any) -> AsyncIterator[Any]:
        graph = self._app
        body = input_data if isinstance(input_data, dict) else {"input": input_data}
        thread_id, runnable_config = _build_runnable_config(body, config or {})
        graph_input = _build_graph_input(body.get("input", input_data), body)
        yield {"type": "thread", "thread_id": thread_id}

        try:
            async for event in _stream_graph(graph, graph_input, runnable_config, body):
                interrupts = _find_interrupts(event)
                if interrupts:
                    yield {
                        "type": "interrupt",
                        **_interrupted_response(
                            thread_id,
                            interrupts,
                            state=await _get_state(graph, runnable_config),
                        ),
                    }
                    return
                yield {"type": "event", "event": _jsonable(event)}
        except Exception as exc:
            interrupts = _interrupts_from_exception(exc)
            if interrupts:
                yield {
                    "type": "interrupt",
                    **_interrupted_response(
                        thread_id,
                        interrupts,
                        state=await _get_state(graph, runnable_config),
                    ),
                }
                return
            raise

        yield {
            "type": "completed",
            "thread_id": thread_id,
            "state": await _get_state(graph, runnable_config),
        }

    def get_routes(self) -> list:
        from starlette.requests import Request
        from starlette.responses import JSONResponse, StreamingResponse
        from starlette.routing import Route

        async def stream_endpoint(request: Request) -> StreamingResponse:
            body = await request.json()
            input_data = body
            config_data = body.get("config", {})

            async def event_stream():
                async for event in self.handle_stream(input_data, config_data):
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        return [Route("/stream", stream_endpoint, methods=["POST"])]


def _build_payload(input_data: Any) -> Any:
    if isinstance(input_data, str):
        return {"messages": [{"role": "user", "content": input_data}]}
    if isinstance(input_data, dict):
        for key in ("message", "prompt", "text"):
            value = input_data.get(key)
            if isinstance(value, str):
                return {"messages": [{"role": "user", "content": value}]}
    return input_data


_MISSING = object()


def _build_graph_input(input_data: Any, body: dict[str, Any]) -> Any:
    resume = _extract_resume(input_data, body)
    if resume is not _MISSING:
        return _resume_command(resume)
    return _build_payload(input_data)


def _extract_resume(input_data: Any, body: dict[str, Any]) -> Any:
    if "resume" in body:
        return body["resume"]
    if isinstance(input_data, dict) and "resume" in input_data:
        return input_data["resume"]
    return _MISSING


def _resume_command(value: Any) -> Any:
    try:
        Command = getattr(importlib.import_module("langgraph.types"), "Command")
    except (ImportError, AttributeError) as exc:
        raise RuntimeError(
            "LangGraph resume requires langgraph.types.Command from the official langgraph package. "
            "Install or upgrade with: pip install 'langgraph>=1.0.0'"
        ) from exc
    return Command(resume=value)


def _build_runnable_config(body: dict[str, Any], config_data: Any) -> tuple[str, dict[str, Any]]:
    config = dict(config_data) if isinstance(config_data, dict) else {}
    configurable = dict(config.get("configurable") or {})
    thread_id = (
        body.get("thread_id")
        or body.get("session_id")
        or configurable.get("thread_id")
        or str(uuid.uuid4())
    )
    thread_id = str(thread_id)
    configurable["thread_id"] = thread_id
    config["configurable"] = configurable
    return thread_id, config


def _langgraph_version(body: dict[str, Any], config: dict[str, Any]) -> str | None:
    configurable = config.get("configurable") if isinstance(config.get("configurable"), dict) else {}
    version = (
        body.get("version")
        or body.get("langgraph_version")
        or config.get("version")
        or config.get("langgraph_version")
        or configurable.get("langgraph_version")
        or "v2"
    )
    version = str(version).strip()
    if version.lower() in {"", "default", "none", "off", "false", "0"}:
        return None
    return version


async def _invoke_graph(
    graph: Any,
    graph_input: Any,
    config: dict[str, Any],
    *,
    version: str | None = None,
) -> Any:
    if hasattr(graph, "ainvoke"):
        return await _call_graph_method(graph.ainvoke, graph_input, config, version)
    if hasattr(graph, "invoke"):
        return await _call_graph_method(graph.invoke, graph_input, config, version)
    raise TypeError("LangGraph adapter requires a compiled graph with invoke or ainvoke")


async def _call_graph_method(
    method: Any,
    graph_input: Any,
    config: dict[str, Any],
    version: str | None,
) -> Any:
    kwargs: dict[str, Any] = {"config": config}
    if version:
        kwargs["version"] = version

    while True:
        try:
            result = method(graph_input, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        except TypeError as exc:
            message = str(exc)
            if "version" in kwargs and "version" in message:
                kwargs.pop("version")
                continue
            if "config" in kwargs and "config" in message:
                kwargs.pop("config")
                continue
            raise


async def _stream_graph(
    graph: Any,
    graph_input: Any,
    config: dict[str, Any],
    body: dict[str, Any],
) -> AsyncIterator[Any]:
    if not hasattr(graph, "astream"):
        yield await _invoke_graph(graph, graph_input, config, version=_langgraph_version(body, config))
        return

    stream_mode = body.get("stream_mode") or config.get("stream_mode") or "updates"
    kwargs: dict[str, Any] = {"config": config, "stream_mode": stream_mode}
    version = _langgraph_version(body, config)
    if version:
        kwargs["version"] = version

    while True:
        try:
            async for event in graph.astream(graph_input, **kwargs):
                yield event
            return
        except TypeError as exc:
            message = str(exc)
            if "version" in kwargs and "version" in message:
                kwargs.pop("version")
                continue
            if "stream_mode" in kwargs and "stream_mode" in message:
                kwargs.pop("stream_mode")
                continue
            if "config" in kwargs and "config" in message:
                kwargs.pop("config")
                continue
            raise


async def _get_state(graph: Any, config: dict[str, Any]) -> Any:
    get_state = getattr(graph, "get_state", None)
    if not callable(get_state):
        return None
    try:
        state = get_state(config)
    except Exception as exc:
        logger.debug("LangGraph state lookup failed: %s", exc)
        return None
    if inspect.isawaitable(state):
        state = await state
    return _jsonable(_state_to_dict(state))


def _state_to_dict(state: Any) -> Any:
    if state is None:
        return None
    if isinstance(state, dict):
        return state
    result: dict[str, Any] = {}
    for attr in ("values", "next", "tasks", "metadata", "created_at", "parent_config"):
        if hasattr(state, attr):
            result[attr] = getattr(state, attr)
    return result or state


def _find_interrupts(value: Any) -> list[Any]:
    attr_interrupts = getattr(value, "interrupts", None)
    if attr_interrupts:
        return _as_list(attr_interrupts)
    if isinstance(value, dict):
        if value.get("interrupts"):
            return _as_list(value["interrupts"])
        if "__interrupt__" in value:
            return _as_list(value["__interrupt__"])
        interrupts: list[Any] = []
        for child in value.values():
            interrupts.extend(_find_interrupts(child))
        return interrupts
    if isinstance(value, (list, tuple)):
        interrupts: list[Any] = []
        for child in value:
            interrupts.extend(_find_interrupts(child))
        return interrupts
    return []


def _interrupts_from_exception(exc: Exception) -> list[Any]:
    class_name = exc.__class__.__name__.lower()
    module_name = exc.__class__.__module__.lower()
    if "interrupt" not in class_name and "interrupt" not in module_name:
        return []
    for attr in ("interrupts", "interrupt"):
        value = getattr(exc, attr, None)
        if value:
            return _as_list(value)
    if exc.args:
        return list(exc.args)
    return [str(exc)]


def _interrupted_response(thread_id: str, interrupts: list[Any], *, state: Any = None) -> dict[str, Any]:
    payloads = [_interrupt_payload(interrupt) for interrupt in interrupts]
    prompt = _first_interrupt_prompt(payloads)
    response = {
        "status": "interrupted",
        "thread_id": thread_id,
        "prompt": prompt,
        "interrupts": payloads,
    }
    if state is not None:
        response["state"] = state
    return response


def _interrupt_payload(interrupt: Any) -> Any:
    if isinstance(interrupt, dict):
        return _jsonable(interrupt)
    if hasattr(interrupt, "value"):
        payload = {"value": _jsonable(getattr(interrupt, "value"))}
        if hasattr(interrupt, "id"):
            payload["id"] = _jsonable(getattr(interrupt, "id"))
        return payload
    return _jsonable(interrupt)


def _first_interrupt_prompt(payloads: list[Any]) -> Any:
    if not payloads:
        return None
    first = payloads[0]
    if isinstance(first, dict) and "value" in first:
        return first["value"]
    return first


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _jsonable(value: Any) -> Any:
    if _is_graph_output(value):
        return _jsonable(value.value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return _jsonable(value.dict())
    if hasattr(value, "content"):
        return getattr(value, "content")
    return str(value)


def _graph_output_value(value: Any) -> Any:
    if _is_graph_output(value):
        return value.value
    return value


def _is_graph_output(value: Any) -> bool:
    return hasattr(value, "value") and hasattr(value, "interrupts")
