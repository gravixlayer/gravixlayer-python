"""LangChain framework adapter."""

from __future__ import annotations

import inspect
import json
from typing import Any

from .base import BaseFrameworkAdapter


class LangChainAdapter(BaseFrameworkAdapter):
    """Adapter for LangChain agents, chains, and runnables."""

    @property
    def name(self) -> str:
        return "langchain"

    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        runnable = self._app
        first_error: Exception | None = None
        runnable_config = _build_runnable_config(config)

        payloads = _build_payload_candidates(input_data)
        for index, payload in enumerate(payloads):
            try:
                result = await _invoke_runnable(runnable, payload, runnable_config)
                return _extract_output(result)
            except Exception as exc:
                if first_error is None:
                    first_error = exc
                if index == len(payloads) - 1 or not _is_payload_shape_error(exc):
                    raise

        if first_error is not None:
            raise first_error
        raise TypeError("LangChain adapter requires an agent, chain, runnable, or callable")

    async def handle_stream(self, input_data: Any, config: Any):
        runnable = self._app
        payload = _build_payload_candidates(input_data)[0]
        runnable_config = _build_runnable_config(config)

        if hasattr(runnable, "astream"):
            async for chunk in runnable.astream(payload, config=runnable_config):
                yield _extract_output(chunk)
            return

        if hasattr(runnable, "stream"):
            for chunk in runnable.stream(payload, config=runnable_config):
                yield _extract_output(chunk)
            return

        yield await self.handle_invoke(input_data, config)

    def get_routes(self) -> list:
        from starlette.requests import Request
        from starlette.responses import StreamingResponse
        from starlette.routing import Route

        async def stream_endpoint(request: Request) -> StreamingResponse:
            body = await request.json()
            input_data = body.get("input", body)
            config_data = body.get("config", {})

            async def event_stream():
                async for event in self.handle_stream(input_data, config_data):
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        return [Route("/stream", stream_endpoint, methods=["POST"])]


async def _invoke_runnable(runnable: Any, payload: Any, config: Any) -> Any:
    if hasattr(runnable, "ainvoke"):
        return await runnable.ainvoke(payload, config=config or None)
    if hasattr(runnable, "invoke"):
        return runnable.invoke(payload, config=config or None)
    if callable(runnable):
        result = runnable(payload)
        if inspect.isawaitable(result):
            return await result
        return result
    raise TypeError("LangChain adapter requires an agent, chain, runnable, or callable")


def _build_runnable_config(config: Any) -> Any:
    if not isinstance(config, dict):
        return None

    from langchain_core.runnables.config import ensure_config  # type: ignore[import-not-found]

    runnable_config = dict(config)
    configurable = dict(runnable_config.get("configurable") or {})
    thread_id = (
        runnable_config.get("thread_id")
        or runnable_config.get("session_id")
        or configurable.get("thread_id")
    )
    if thread_id:
        configurable["thread_id"] = str(thread_id)
    if configurable:
        runnable_config["configurable"] = configurable
    return ensure_config(runnable_config)


def _build_payload_candidates(input_data: Any) -> list[Any]:
    if isinstance(input_data, str):
        return _dedupe_payloads(_text_payloads(input_data))
    if isinstance(input_data, dict):
        for key in ("message", "prompt", "text"):
            value = input_data.get(key)
            if isinstance(value, str):
                return _dedupe_payloads([input_data, *_text_payloads(value)])
        return [input_data]
    return _dedupe_payloads(_text_payloads(str(input_data)))


def _text_payloads(text: str) -> list[dict[str, Any]]:
    return [
        {"messages": [{"role": "user", "content": text}]},
        {"input": text},
        {"question": text},
    ]


def _dedupe_payloads(payloads: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[str] = set()
    for payload in payloads:
        marker = repr(payload)
        if marker in seen:
            continue
        deduped.append(payload)
        seen.add(marker)
    return deduped


def _is_payload_shape_error(exc: Exception) -> bool:
    if isinstance(exc, KeyError):
        return True
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "field required",
            "input key",
            "input_keys",
            "missing required",
            "missing some input keys",
            "validation error",
        )
    )


def _extract_output(result: Any) -> Any:
    if isinstance(result, dict):
        messages = result.get("messages")
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                return last_message.content
            if isinstance(last_message, dict):
                return last_message.get("content", last_message)
        for key in ("output", "response", "result"):
            if key in result:
                return result[key]
    if hasattr(result, "content"):
        return result.content
    return result
