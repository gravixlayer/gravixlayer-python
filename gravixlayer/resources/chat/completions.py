from typing import Dict, Any, List, Optional, Union, Iterator
import json
from ...types.chat import ChatCompletion, ChatCompletionChoice, ChatCompletionMessage, ChatCompletionUsage, ChatCompletionDelta

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
            line = line.decode("utf-8").strip()
            
            # Handle SSE format
            if line.startswith("data: "):
                line = line[6:]  # Remove "data: " prefix
            
            # Skip empty lines and [DONE] marker
            if not line or line == "[DONE]":
                continue
            
            try:
                chunk_data = json.loads(line)
                parsed_chunk = self._parse_response(chunk_data, is_stream=True)
                
                # Only yield if we have valid choices
                if parsed_chunk.choices:
                    yield parsed_chunk
                    
            except json.JSONDecodeError as e:
                # Log the problematic line for debugging
                print(f"Failed to parse JSON: {line[:100]}...")
                continue
            except Exception as e:
                print(f"Error processing chunk: {e}")
                continue

    def _parse_response(self, resp_data: Dict[str, Any], is_stream: bool = False) -> ChatCompletion:
        choices = []
        
        # Handle different response formats
        if "choices" in resp_data and resp_data["choices"]:
            for choice_data in resp_data["choices"]:
                if is_stream:
                    # For streaming, create delta object
                    delta_content = None
                    delta_role = None
                    
                    if "delta" in choice_data:
                        delta = choice_data["delta"]
                        delta_content = delta.get("content")
                        delta_role = delta.get("role")
                    elif "message" in choice_data:
                        # Fallback: treat message as delta
                        message = choice_data["message"]
                        delta_content = message.get("content")
                        delta_role = message.get("role")
                    
                    # Create delta object
                    delta_obj = ChatCompletionDelta(
                        role=delta_role,
                        content=delta_content
                    )
                    
                    # Create message object (for compatibility)
                    msg = ChatCompletionMessage(
                        role=delta_role or "assistant",
                        content=delta_content or ""
                    )
                    
                    choices.append(ChatCompletionChoice(
                        index=choice_data.get("index", 0),
                        message=msg,
                        delta=delta_obj,
                        finish_reason=choice_data.get("finish_reason")
                    ))
                else:
                    # For non-streaming, use message object
                    message_data = choice_data.get("message", {})
                    msg = ChatCompletionMessage(
                        role=message_data.get("role", "assistant"),
                        content=message_data.get("content", "")
                    )
                    choices.append(ChatCompletionChoice(
                        index=choice_data.get("index", 0),
                        message=msg,
                        finish_reason=choice_data.get("finish_reason")
                    ))
        
        # Fallback: create a single choice if no choices found
        if not choices:
            content = ""
            if isinstance(resp_data, str):
                content = resp_data
            elif "content" in resp_data:
                content = resp_data["content"]
            
            if is_stream:
                delta_obj = ChatCompletionDelta(content=content)
                msg = ChatCompletionMessage(role="assistant", content=content)
                choices = [ChatCompletionChoice(
                    index=0, 
                    message=msg, 
                    delta=delta_obj,
                    finish_reason=None
                )]
            else:
                msg = ChatCompletionMessage(role="assistant", content=content)
                choices = [ChatCompletionChoice(
                    index=0, 
                    message=msg, 
                    finish_reason="stop"
                )]

        # Parse usage if available
        usage = None
        if "usage" in resp_data:
            usage = ChatCompletionUsage(
                prompt_tokens=resp_data["usage"].get("prompt_tokens", 0),
                completion_tokens=resp_data["usage"].get("completion_tokens", 0),
                total_tokens=resp_data["usage"].get("total_tokens", 0),
            )
        
        import time
        return ChatCompletion(
            id=resp_data.get("id", f"chatcmpl-{hash(str(resp_data))}"),
            object="chat.completion" if not is_stream else "chat.completion.chunk",
            created=resp_data.get("created", int(time.time())),
            model=resp_data.get("model", "unknown"),
            choices=choices,
            usage=usage,
        )
