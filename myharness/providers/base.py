from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]

class ChatMessage(BaseModel):
    role: str
    content: list[dict[str, Any]]
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    token_usage: dict[str, Any] | None = None

class ChatResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall] = []
    finish_reason: str
    reasoning: str | None = None
    token_usage: dict[str, Any] | None = None

class BaseProvider(ABC):

    @abstractmethod
    def invoke(self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None, **kwargs) -> ChatResponse:
        pass

    @abstractmethod
    def stream(self):
        pass