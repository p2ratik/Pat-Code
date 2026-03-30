from __future__ import annotations
from typing import Any
from enum import Enum
from client.response import TokenUsage
from dataclasses import dataclass

from tools.base import ToolResult


class AgentEventType(str, Enum):
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    AGENT_ERROR = "agent_error"

    TEXT_DELTA = "text_delta"
    TEXT_COMPLETE = "text_complete"

    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_COMPLETE = "tool_call_complete"  
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
    
    @classmethod
    def tool_call_start(cls, call_id: str, name: str, arguments: dict[str, Any]):
        return cls(
            type=AgentEventType.TOOL_CALL_START,
            data={
                "call_id": call_id,
                "name": name,
                "arguments": arguments,
            },
        )

    @classmethod
    def tool_call_complete(
        cls,
        call_id: str,
        name: str,
        result: ToolResult,
    ):
        return cls(
            type=AgentEventType.TOOL_CALL_COMPLETE,
            data={
                "call_id": call_id,
                "name": name,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "metadata": result.metadata,
                #"diff": result.diff.to_diff() if result.diff else None,
                #"truncated": result.truncated,
                #"exit_code": result.exit_code,
            },
        )