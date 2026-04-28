from __future__ import annotations
from typing import Any, AsyncGenerator
import json
from agent.events import AgentEvent
from agent.events import AgentEventType
from agent.session import Session
from client.llm_client import LLMClient
from client.response import StreamEventType, TokenUsage, ToolCall, ToolResultMessage
from config.config import Config
from tools.registry import create_default_registry
from pathlib import Path
from db.database import Columns
from utils.text import count_tokens

class Agent:
    def __init__(self, config:Config):
        self.config = config
        self.session =  Session(self.config)


    async def run(self, message:str):
        yield AgentEvent.agent_start(message=message)

        self.session.context_manager.add_user_message(content=message)
        self.session.db_manager.add_msg_to_db(Columns(session_id=self.session.session_id, 
                                                      role="user",
                                                      content=message,
                                                      token=count_tokens(message, self.session.config.model_name)))

        final_response = ""
        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")

            # elif event.type == AgentEventType.AGENT_ERROR:
            #     yield event

        yield AgentEvent.agent_end(final_response,usage=None)       

     
    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        # The context manager will handle user and assistant messages
        max_turns = self.config.max_turns

        for _ in range(max_turns):
            self.session.increment_turn()
            response = ""

            # check for context overflow
            if self.session.context_manager.needs_compression():
                summary, usage = await self.session.chat_compactor.compress(
                    self.session.context_manager
                )

                # Summarizing the previous conversation . Note that the context is already prunned from the prune tool result function 
                if summary:
                    self.session.context_manager.replace_with_summary(summary)
                    self.session.context_manager.set_latest_usage(usage)
                    self.session.context_manager.add_usage(usage)

            tool_schemas = self.session.tool_registry.get_schemas()

            tool_calls: list[ToolCall] = []
            usage: TokenUsage | None = None

            # If all tool calls are executed or no tool calls are left the agentic loop will break out
            async for event in self.session.client.chat_completion(
                self.session.context_manager.get_messages(),
                tools=tool_schemas if tool_schemas else None,
            ):
                if event.type == StreamEventType.TEXT_DELTA:
                    if event.text_delta:
                        content = event.text_delta.content
                        response += content
                        yield AgentEvent.text_delta(content)
                elif event.type == StreamEventType.TOOL_CALL_COMPLETE:
                    if event.tool_call:
                        tool_calls.append(event.tool_call)
                elif event.type == StreamEventType.ERROR:
                    yield AgentEvent.agent_error(
                        event.error or "Unknown error occurred.",
                    )
                elif event.type == StreamEventType.MESSAGE_COMPLETE:
                    usage = event.usage

            self.session.context_manager.add_assistant_message(
                response or None,
                (
                    [
                        {
                            "id": tc.call_id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": str(tc.arguments),
                            },
                        }
                        for tc in tool_calls
                    ]
                    if tool_calls
                    else None
                ),
            )
            if response:
                yield AgentEvent.text_complete(response)
                # self.session.loop_detector.record_action(
                #     "response",
                #     text=response,
                # )

            if not tool_calls:
                if usage:
                    self.session.context_manager.set_latest_usage(usage)
                    self.session.context_manager.add_usage(usage)

                self.session.context_manager.prune_tool_outputs()
                return

            tool_call_results: list[ToolResultMessage] = []

            for tool_call in tool_calls:
                yield AgentEvent.tool_call_start(
                    tool_call.call_id,
                    tool_call.name,
                    tool_call.arguments,
                )

                # self.session.loop_detector.record_action(
                #     "tool_call",
                #     tool_name=tool_call.name,
                #     args=tool_call.arguments,
                # )

                result = await self.session.tool_registry.invoke(
                    tool_call.name,
                    tool_call.arguments,
                    self.config.cwd,
                    self.session,
                    # self.session.hook_system,
                    self.session.approval_manager,
                )

                yield AgentEvent.tool_call_complete(
                    tool_call.call_id,
                    tool_call.name,
                    result, 
                )

                tool_call_results.append(
                    ToolResultMessage(
                        tool_call_id=tool_call.call_id,
                        content=result.to_model_output(),
                        is_error=not result.success,
                    )
                )

            for tool_result in tool_call_results:
                self.session.context_manager.add_tool_result(
                    tool_result.tool_call_id,
                    tool_result.content,
                )
                self.session.db_manager.add_msg_to_db(Columns(session_id = self.session.session_id,
                                                           role = "tool",
                                                           content = tool_result.content,
                                                           token = count_tokens(tool_result.content, self.session.config.model_name),
                                                           tool_call_id = tool_result.tool_call_id,
                                                           ))

            # loop_detection_error = self.session.loop_detector.check_for_loop()
            # if loop_detection_error:
            #     loop_prompt = create_loop_breaker_prompt(loop_detection_error)
            #     self.session.context_manager.add_user_message(loop_prompt)

            if usage:
                self.session.context_manager.set_latest_usage(usage)
                self.session.context_manager.add_usage(usage)

            self.session.context_manager.prune_tool_outputs()
        yield AgentEvent.agent_error(f"Maximum turns ({max_turns}) reached")


    async def __aenter__(self):
        await self.session.initialize()        
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        if self.session and self.session.client and self.session.mcp_manager:
            await self.session.client.close()
            await self.session.mcp_manager.shutdown()
            self.session = None
