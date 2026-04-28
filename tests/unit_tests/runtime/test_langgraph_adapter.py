import json

import pytest

from gravixlayer.runtime import GravixApp
from gravixlayer.frameworks.langgraph import LangGraphAdapter


class _State:
    values = {"location": "Kyoto"}
    next = ()
    tasks = ()


class _InterruptGraph:
    async def ainvoke(self, input_data, config=None):
        self.input_data = input_data
        self.config = config
        return {"__interrupt__": [{"value": "Where do you want to go?"}]}

    def get_state(self, config):
        return _State()


class _CompleteGraph:
    async def ainvoke(self, input_data, config=None):
        self.input_data = input_data
        self.config = config
        return {"agenda": "Day 1"}

    def get_state(self, config):
        return _State()


class _StreamingInterruptGraph:
    async def astream(self, input_data, config=None, stream_mode=None):
        self.input_data = input_data
        self.config = config
        self.stream_mode = stream_mode
        yield {"collect_trip_details_hitl": {"__interrupt__": [{"value": "Destination and dates?"}]}}

    def get_state(self, config):
        return _State()


class _GraphOutput:
    def __init__(self, value, interrupts=()):
        self.value = value
        self.interrupts = interrupts


class _Interrupt:
    value = {"action_requests": [{"name": "send_email"}]}
    id = "interrupt-1"


class _V2CompleteGraph:
    async def ainvoke(self, input_data, config=None, version=None):
        self.input_data = input_data
        self.config = config
        self.version = version
        return _GraphOutput({"agenda": "Day 1"})

    def get_state(self, config):
        return _State()


class _V2InterruptGraph:
    async def ainvoke(self, input_data, config=None, version=None):
        self.input_data = input_data
        self.config = config
        self.version = version
        return _GraphOutput({}, interrupts=(_Interrupt(),))

    def get_state(self, config):
        return _State()


class _V2StreamingInterruptGraph:
    async def astream(self, input_data, config=None, stream_mode=None, version=None):
        self.input_data = input_data
        self.config = config
        self.stream_mode = stream_mode
        self.version = version
        yield {"type": "updates", "data": {"__interrupt__": [_Interrupt()]}}

    def get_state(self, config):
        return _State()


class _Request:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


@pytest.mark.asyncio
async def test_langgraph_adapter_surfaces_interrupt_response():
    graph = _InterruptGraph()
    adapter = LangGraphAdapter(graph)

    result = await adapter.handle_request({"input": {}, "session_id": "thread-1"})

    assert result["status"] == "interrupted"
    assert result["thread_id"] == "thread-1"
    assert result["prompt"] == "Where do you want to go?"
    assert graph.config["configurable"]["thread_id"] == "thread-1"


@pytest.mark.asyncio
async def test_langgraph_adapter_supports_resume_payload():
    graph = _CompleteGraph()
    adapter = LangGraphAdapter(graph)

    result = await adapter.handle_request({"resume": "Kyoto, 2026-06-10 to 2026-06-17", "thread_id": "thread-2"})

    assert result["status"] == "completed"
    assert result["thread_id"] == "thread-2"
    assert result["output"] == {"agenda": "Day 1"}
    assert graph.config["configurable"]["thread_id"] == "thread-2"


@pytest.mark.asyncio
async def test_langgraph_adapter_supports_resume_decision_payload():
    graph = _CompleteGraph()
    adapter = LangGraphAdapter(graph)
    resume = {"decisions": [{"type": "approve"}]}

    result = await adapter.handle_request({"resume": resume, "thread_id": "thread-4"})

    assert result["status"] == "completed"
    assert result["thread_id"] == "thread-4"
    assert graph.input_data.resume == resume


@pytest.mark.asyncio
async def test_langgraph_adapter_streams_interrupt_event():
    graph = _StreamingInterruptGraph()
    adapter = LangGraphAdapter(graph)

    events = [event async for event in adapter.handle_stream({"input": {}, "session_id": "thread-3"}, {})]

    assert events[0] == {"type": "thread", "thread_id": "thread-3"}
    assert events[1]["type"] == "interrupt"
    assert events[1]["prompt"] == "Destination and dates?"
    assert graph.config["configurable"]["thread_id"] == "thread-3"
    assert graph.stream_mode == "updates"


@pytest.mark.asyncio
async def test_langgraph_adapter_uses_v2_graph_output_value():
    graph = _V2CompleteGraph()
    adapter = LangGraphAdapter(graph)

    result = await adapter.handle_request({"input": {}, "session_id": "thread-5"})

    assert result["status"] == "completed"
    assert result["output"] == {"agenda": "Day 1"}
    assert graph.version == "v2"


@pytest.mark.asyncio
async def test_langgraph_adapter_surfaces_v2_graph_output_interrupts():
    graph = _V2InterruptGraph()
    adapter = LangGraphAdapter(graph)

    result = await adapter.handle_request({"input": {}, "session_id": "thread-6"})

    assert result["status"] == "interrupted"
    assert result["interrupts"] == [
        {"value": {"action_requests": [{"name": "send_email"}]}, "id": "interrupt-1"}
    ]
    assert result["state"]["values"] == {"location": "Kyoto"}
    assert graph.version == "v2"


@pytest.mark.asyncio
async def test_langgraph_adapter_streams_v2_interrupt_event():
    graph = _V2StreamingInterruptGraph()
    adapter = LangGraphAdapter(graph)

    events = [event async for event in adapter.handle_stream({"input": {}, "session_id": "thread-7"}, {})]

    assert events[0] == {"type": "thread", "thread_id": "thread-7"}
    assert events[1]["type"] == "interrupt"
    assert events[1]["interrupts"][0]["id"] == "interrupt-1"
    assert graph.stream_mode == "updates"
    assert graph.version == "v2"


@pytest.mark.asyncio
async def test_gravix_app_returns_langgraph_request_payload_at_top_level():
    app = GravixApp()
    app.mount_framework("langgraph", _InterruptGraph())

    response = await app._invoke_endpoint(_Request({"input": {}, "session_id": "thread-http"}))
    payload = json.loads(response.body)

    assert payload["status"] == "interrupted"
    assert payload["thread_id"] == "thread-http"
    assert "output" not in payload