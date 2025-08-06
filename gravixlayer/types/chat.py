from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class ChatCompletionMessage:
    role: str
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None

@dataclass
class ChatCompletionChoice:
    index: int
    message: ChatCompletionMessage
    finish_reason: Optional[str] = None

@dataclass
class ChatCompletionUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class ChatCompletion:
    id: str
    object: str
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[ChatCompletionUsage] = None
