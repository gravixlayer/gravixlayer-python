from typing import Dict, Any, List, Optional, Union, Iterator
import json
from ...types.chat import ChatCompletion, ChatCompletionChoice, ChatCompletionMessage, ChatCompletionUsage

class ChatCompletions:
    """Chat completions resource"""

    def __init__(self, client):
        self.client = client

    def create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[Union[str, List[str]]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[ChatCompletion, Iterator[ChatCompletion]]:
        data = {
            "model": model,
            "messages": messages,
            "stream": stream
        }
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        if top_p is not None:
            data["top_p"] = top_p
        if frequency_penalty is not None:
            data["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            data["presence_penalty"] = presence_penalty
        if stop is not None:
            data["stop"] = stop
        data.update(kwargs)
        return self._create_stream(data) if stream else self._create_non_stream(data)

    def _create_non_stream(self, data: Dict[str, Any]) -> ChatCompletion:
        resp = self.client._make_request("POST", "chat/completions", data)
        return self._parse_response(resp.json())

    def _create_stream(self, data: Dict[str, Any]) -> Iterator[ChatCompletion]:
        resp = self.client._make_request("POST", "chat/completions", data, stream=True)
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                line = line[len("data: "):]
            if line.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(line)
                yield self._parse_response(chunk, is_stream=True)
            except json.JSONDecodeError:
                continue

    def _parse_response(self, resp_data: Dict[str, Any], is_stream: bool = False) -> ChatCompletion:
        if "choices" in resp_data:
            choices = []
            for choice in resp_data["choices"]:
                msg = ChatCompletionMessage(
                    role=choice.get("message", {}).get("role", "assistant"),
                    content=choice.get("message", {}).get("content", "")
                )
                choices.append(ChatCompletionChoice(
                    index=choice.get("index", 0),
                    message=msg,
                    finish_reason=choice.get("finish_reason")
                ))
        else:
            content = resp_data.get("content", "")
            if isinstance(resp_data, str):
                content = resp_data
            msg = ChatCompletionMessage(role="assistant", content=content)
            choices = [ChatCompletionChoice(index=0, message=msg, finish_reason="stop")]

        usage = None
        if "usage" in resp_data:
            usage = ChatCompletionUsage(
                prompt_tokens=resp_data["usage"].get("prompt_tokens", 0),
                completion_tokens=resp_data["usage"].get("completion_tokens", 0),
                total_tokens=resp_data["usage"].get("total_tokens", 0),
            )
        import time
        return ChatCompletion(
            id=resp_data.get("id", "chatcmpl-" + str(hash(str(resp_data)))),
            object="chat.completion" if not is_stream else "chat.completion.chunk",
            created=resp_data.get("created", int(time.time())),
            model=resp_data.get("model", "unknown"),
            choices=choices,
            usage=usage,
        )
