from __future__ import annotations
from typing import Any
from enum import Enum
from client.response import TokenUsage
from dataclasses import dataclass


class AgentEventType(str, Enum):
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    AGENT_ERROR = "agent_error"

    TEXT_DELTA = "text_delta"
    TEXT_COMPLETE = "text_complete"

@dataclass
class AgentEvent:
    type : AgentEventType
    data : dict[str, Any] 

    @classmethod
    def agent_start(cls, message:str)->AgentEvent:
        return cls(
            type = AgentEventType.AGENT_START,
            data = {"message": message}
        )
    @classmethod
    def agent_end(cls, response:str, usage: TokenUsage)->AgentEvent:
        return cls(
            type = AgentEventType.AGENT_START,
            data = {"response":response, "usage":usage.__dict__ if usage else None}
        )
    @classmethod
    def agent_error(cls, error:str)->AgentEvent:
        return cls(
            type = AgentEventType.AGENT_ERROR,
            data = {"error": error if error else "Unknown error"}
        )

    @classmethod
    def text_delta(cls, content:str):
        return cls(
            type = AgentEventType.TEXT_DELTA,
            data = {"content":content}
        )
    
    @classmethod
    def text_complete(cls, content:str):
        return cls(
            type = AgentEventType.TEXT_COMPLETE,
            data = {"content":content}
        )