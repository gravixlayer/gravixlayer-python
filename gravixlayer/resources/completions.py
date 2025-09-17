"""
Completions resource for GravixLayer SDK
"""
from typing import Dict, Any, List, Optional, Union, Iterator
import json
from ..types.completions import Completion, CompletionChoice, CompletionUsage


class Completions:
    """Completions resource for prompt-based completions"""

    def __init__(self, client):
        self.client = client

    def create(
        self,
        model: str,
        prompt: Union[str, List[str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = None,
        stream: bool = False,
        logprobs: Optional[int] = None,
        echo: bool = False,
        stop: Optional[Union[str, List[str]]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        best_of: Optional[int] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        user: Optional[str] = None,
        **kwargs
    ) -> Union[Completion, Iterator[Completion]]:
        """
        Create a completion for the provided prompt and parameters.
        
        Args:
            model: ID of the model to use
            prompt: The prompt(s) to generate completions for
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0 to 2)
            top_p: Nucleus sampling parameter
            n: Number of completions to generate
            stream: Whether to stream back partial progress
            logprobs: Include the log probabilities on the logprobs most likely tokens
            echo: Echo back the prompt in addition to the completion
            stop: Up to 4 sequences where the API will stop generating further tokens
            presence_penalty: Penalty for new tokens based on whether they appear in the text so far
            frequency_penalty: Penalty for new tokens based on their existing frequency in the text so far
            best_of: Generates best_of completions server-side and returns the "best"
            logit_bias: Modify the likelihood of specified tokens appearing in the completion
            user: A unique identifier representing your end-user
            **kwargs: Additional parameters
            
        Returns:
            Completion or Iterator[Completion]: The completion response
        """
        data = {
            "model": model,
            "prompt": prompt,
            "stream": stream
        }
        
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        if temperature is not None:
            data["temperature"] = temperature
        if top_p is not None:
            data["top_p"] = top_p
        if n is not None:
            data["n"] = n
        if logprobs is not None:
            data["logprobs"] = logprobs
        if echo is not None:
            data["echo"] = echo
        if stop is not None:
            data["stop"] = stop
        if presence_penalty is not None:
            data["presence_penalty"] = presence_penalty
        if frequency_penalty is not None:
            data["frequency_penalty"] = frequency_penalty
        if best_of is not None:
            data["best_of"] = best_of
        if logit_bias is not None:
            data["logit_bias"] = logit_bias
        if user is not None:
            data["user"] = user
        
        data.update(kwargs)
        
        return self._create_stream(data) if stream else self._create_non_stream(data)

    def _create_non_stream(self, data: Dict[str, Any]) -> Completion:
        """Create non-streaming completion"""
        resp = self.client._make_request("POST", "completions", data)
        return self._parse_response(resp.json())

    def _create_stream(self, data: Dict[str, Any]) -> Iterator[Completion]:
        """Create streaming completion"""
        resp = self.client._make_request("POST", "completions", data, stream=True)
        
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
                
                # Skip if chunk_data is None or empty
                if not chunk_data:
                    continue
                
                # Debug: Print the chunk structure for deployed models
                # print(f"DEBUG: chunk_data = {chunk_data}")
                    
                parsed_chunk = self._parse_response(chunk_data, is_stream=True)
                
                # Only yield if we have valid choices
                if parsed_chunk and parsed_chunk.choices:
                    yield parsed_chunk
                    
            except json.JSONDecodeError as e:
                # Log the problematic line for debugging
                print(f"Failed to parse JSON: {line[:100]}...")
                continue
            except Exception as e:
                # Skip malformed chunks silently
                continue

    def _parse_response(self, resp_data: Dict[str, Any], is_stream: bool = False) -> Completion:
        """Parse API response into Completion object"""
        # Handle None or empty response data
        if not resp_data:
            return None
            
        choices = []
        
        # Handle different response formats
        if "choices" in resp_data and resp_data["choices"]:
            for choice_data in resp_data["choices"]:
                # Skip if choice_data is None
                if not choice_data:
                    continue
                    
                text = ""
                
                if is_stream:
                    # For streaming, get text from delta or text field
                    # Deployed models often return text directly in choice_data
                    if "text" in choice_data:
                        text = choice_data.get("text", "")
                    elif "delta" in choice_data and choice_data["delta"] is not None:
                        delta = choice_data["delta"]
                        text = delta.get("content", "") or delta.get("text", "")
                    # Handle direct content field for some deployed models
                    elif "content" in choice_data:
                        text = choice_data.get("content", "")
                else:
                    # For non-streaming, get text directly
                    text = choice_data.get("text", "") or choice_data.get("content", "")
                
                choice = CompletionChoice(
                    text=text,
                    index=choice_data.get("index", 0),
                    logprobs=choice_data.get("logprobs"),
                    finish_reason=choice_data.get("finish_reason")
                )
                choices.append(choice)
        
        # Fallback: create a single choice if no choices found
        if not choices:
            text = ""
            if isinstance(resp_data, str):
                text = resp_data
            elif "text" in resp_data:
                text = resp_data["text"]
            elif "content" in resp_data:
                text = resp_data["content"]
            
            choices = [CompletionChoice(
                text=text,
                index=0,
                finish_reason="stop" if not is_stream else None
            )]

        # Parse usage if available
        usage = None
        if "usage" in resp_data and resp_data["usage"] is not None:
            usage_data = resp_data["usage"]
            usage = CompletionUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0) if usage_data else 0,
                completion_tokens=usage_data.get("completion_tokens", 0) if usage_data else 0,
                total_tokens=usage_data.get("total_tokens", 0) if usage_data else 0,
            )
        
        import time
        
        # Safely get values with null checking
        completion_id = resp_data.get("id", f"cmpl-{hash(str(resp_data))}") if resp_data else f"cmpl-{hash('empty')}"
        created_time = resp_data.get("created", int(time.time())) if resp_data else int(time.time())
        model_name = resp_data.get("model", "unknown") if resp_data else "unknown"
        
        return Completion(
            id=completion_id,
            object="text_completion" if not is_stream else "text_completion.chunk",
            created=created_time,
            model=model_name,
            choices=choices,
            usage=usage,
        )