from __future__ import annotations
from typing import Any, AsyncGenerator
import json
from agent.events import AgentEvent
from agent.events import AgentEventType
from agent.session import Session
from client.llm_client import LLMClient
from client.response import StreamEventType, ToolCall, ToolResultMessage
from config.config import Config
from context.manager import ContextManager
from tools.registry import create_default_registry
from pathlib import Path

class Agent:
    def __init__(self, config:Config):
        self.config = config
        self.session =  Session(self.config)


    async def run(self, message:str):
        yield AgentEvent.agent_start(message=message)

        self.session.context_manager.add_user_message(content=message)
        final_response = ""
        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")

            # elif event.type == AgentEventType.AGENT_ERROR:
            #     yield event

        yield AgentEvent.agent_end(final_response,usage=None)       

     
    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent]:
        # The context manager will handle user and assistant messages
        max_turns = self.config.max_turns

        tool_schemas = self.session.tool_registry.get_schemas()

        for _ in range(max_turns):
            response = ""
            tool_calls: list[ToolCall] = []

            # If all tool calls are executed or no tool calls are left the agentic loop will break out
            async for event in self.session.client.chat_completion(
                messages=self.session.context_manager.get_messages(),
                tools=tool_schemas if tool_schemas else None,
                stream=True,
            ):
                if event.type == StreamEventType.TEXT_DELTA:
                    if event.text_delta:
                        response += event.text_delta.content
                        yield AgentEvent.text_delta(content=event.text_delta.content)

                elif event.type == StreamEventType.TOOL_CALL_COMPLETE:
                    if event.tool_call:
                        tool_calls.append(event.tool_call)  # ToolCall object

                elif event.type == StreamEventType.ERROR:
                    yield AgentEvent.agent_error(error=event.error or "Unknown error")

            # Record the assistant message, including tool_calls if any
            assistant_tool_calls: list[dict[str, Any]] = []
            for tool_call in tool_calls:
                assistant_tool_calls.append(
                    {
                        "id": tool_call.call_id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.arguments),
                        },
                    }
                )
            # storing tool calls on the assistant message so the model can link tool results correctly
            self.session.context_manager.add_assistant_message(
                content=response or None,
                tool_calls=assistant_tool_calls if assistant_tool_calls else None,
            )

            if response:
                yield AgentEvent.text_complete(response)

            if not tool_calls:
                break

            tool_call_result: list[ToolResultMessage] = []

            for tool_call in tool_calls:
                yield AgentEvent.tool_call_start(
                    tool_call.call_id,
                    tool_call.name,
                    tool_call.arguments,
                )

                result = await self.session.tool_registry.invoke(
                    tool_call.name,
                    tool_call.arguments,
                    Path.cwd(),
                )

                yield AgentEvent.tool_call_complete(
                    tool_call.call_id,
                    tool_call.name,
                    result,
                )

                tool_call_result.append(
                    ToolResultMessage(
                        tool_call_id=tool_call.call_id,
                        content=result.to_model_output(),
                        is_error=not result.success,
                    )
                )

            for tool_result in tool_call_result:
                self.session.context_manager.add_tool_result(
                    tool_result.tool_call_id,
                    tool_result.content,
                )


    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        if self.session and self.session.client:
            await self.session.client.close()
            self.session.client = None
