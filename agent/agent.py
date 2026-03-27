from __future__ import annotations
from typing import Any, AsyncGenerator
from agent.events import AgentEvent
from agent.events import AgentEventType
from client.llm_client import LLMClient
from client.response import StreamEventType
from context.manager import ContextManager


class Agent:
    def __init__(self):
        # Configurator
        self.client = LLMClient()
        self.context_manager = ContextManager()

    async def run(self, message:str):
        yield AgentEvent.agent_start(message=message)

        self.context_manager.add_user_message(content=message)
        final_response = ""
        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")

            # elif event.type == AgentEventType.AGENT_ERROR:
            #     yield event

        yield AgentEvent.agent_end(final_response,usage=None)       

     
    async def _agentic_loop(self)->AsyncGenerator[AgentEvent]:
        # Therw will be context managr which will handle user nd assistant messages

        response = ""
        async for event in self.client.chat_completion(messages=self.context_manager.get_messages(), stream=True):
            if event.type == StreamEventType.TEXT_DELTA:
                if event.text_delta:
                    response+=event.text_delta.content
                    yield AgentEvent.text_delta(content=response)

            elif event.type == StreamEventType.ERROR:
                print("Till now working fine")
                yield AgentEvent.agent_error(error=event.error or "Unknown error")

        # Recording the assistant message 
        self.context_manager.add_assistant_message(content=response or None)
        
        print(self.context_manager.get_messages())
        if response:
            yield AgentEvent.text_complete(response)

    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        if self.client:
            await self.client.close()
            self.client = None
