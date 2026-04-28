import asyncio

import pytest

from gravixlayer.frameworks.google_adk import _text_part
from gravixlayer.frameworks.langchain import LangChainAdapter


class ClassicInputRunnable:
    def __init__(self):
        self.calls = []

    def invoke(self, payload, config=None):
        self.calls.append(payload)
        if "input" not in payload:
            raise ValueError("Missing some input keys: {'input'}")
        return {"output": payload["input"].upper()}


def test_langchain_adapter_falls_back_to_classic_input_key():
    runnable = ClassicInputRunnable()
    adapter = LangChainAdapter(runnable)

    result = asyncio.run(adapter.handle_invoke("hello", {}))

    assert result == "HELLO"
    assert runnable.calls == [
        {"messages": [{"role": "user", "content": "hello"}]},
        {"input": "hello"},
    ]


def test_langchain_adapter_does_not_retry_runtime_failures():
    class FailingRunnable:
        def __init__(self):
            self.calls = []

        def invoke(self, payload, config=None):
            self.calls.append(payload)
            raise RuntimeError("model provider rejected request")

    runnable = FailingRunnable()
    adapter = LangChainAdapter(runnable)

    with pytest.raises(RuntimeError, match="model provider rejected"):
        asyncio.run(adapter.handle_invoke("hello", {}))

    assert runnable.calls == [{"messages": [{"role": "user", "content": "hello"}]}]


def test_google_adk_text_part_prefers_from_text_constructor():
    class Part:
        @classmethod
        def from_text(cls, *, text):
            return {"text": text, "constructor": "from_text"}

    assert _text_part(Part, "hello") == {"text": "hello", "constructor": "from_text"}
