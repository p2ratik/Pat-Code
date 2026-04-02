import asyncio
from openai import AsyncOpenAI
from typing import Any, AsyncGenerator
from client.response import TextDelta, ToolCall, ToolCallDelta, parse_tool_call_arguments
from client.response import TokenUsage
from client.response import StreamEventType
from client.response import StreamEvent
import os

API_KEY = os.getenv('API_KEY')
class LLMClient():

    def __init__(self):
        self._client : AsyncOpenAI | None = None

    def get_client(self)->AsyncOpenAI:
        """This function creates and returns an async Open AI client if not existing"""

        if self._client is None:
            try:
                self._client = AsyncOpenAI(
                    api_key = '',
                    base_url = 'https://openrouter.ai/api/v1',
                )
            except Exception as e :
                print(f"LLM client not created : {e}")

        return self._client
    
    async def close(self)->None:
        """LLM client close er jonno"""
        pass

    def _build_tools(self, tools: list[dict[str, Any]]):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get(
                        "parameters",
                        {
                            "type": "object",
                            "properties": {},
                        },
                    ),
                },
            }
            for tool in tools
        ]

    async def chat_completion(self, messages: list[dict[str, Any]], tools:list[dict[str, Any]], stream:bool=True)->AsyncGenerator[StreamEvent]:

        client = self.get_client()

        kwargs = {
            "model":'nvidia/nemotron-3-super-120b-a12b:free',
            "messages": messages,
            "stream":stream
        }

        if tools:
            kwargs['tools'] = self._build_tools(tools=tools)
            kwargs['tool_choice'] = "auto"
        # Have to add Exception handeling and exponential backoff
        try:
            if stream:
                async for event in self._stream_response(client=client, kwargs=kwargs):
                    yield event

            else:
                event = await self._non_stream_response(client=client, kwargs=kwargs)
                yield event
        except Exception as e:
            yield StreamEvent(
                type = StreamEventType.ERROR,
                finish_reason= "Error",
                error = e
            )        

    async def _stream_response(self, client, kwargs)->AsyncGenerator[StreamEvent]:
        """Stream Response"""
        # when ever stream = True its gonna return a AsyncGenerator not a normal Coroutine object

        response = await client.chat.completions.create(**kwargs)

        usage : TokenUsage | None = None
        finish_reason : str | None = None

        tool_calls : dict[int, dict[str, Any]] = {} # Dict to track tool calls {index : tool_call_details}

        async for chunk in response:

            if hasattr(chunk, "usage") and chunk.usage:
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                    cached_tokens=chunk.usage.prompt_tokens_details.cached_tokens,
                )

            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            if choice.finish_reason:
                finish_reason = choice.finish_reason

            if delta.content:
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    text_delta=TextDelta(delta.content),
                )

            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    idx = tool_call_delta.index

                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id" : tool_call_delta.id or "",
                            "name" : "",
                            "arguments" : "",
                        }   

                    if tool_call_delta.function:
                        if tool_call_delta.function.name:
                            if not tool_calls[idx]["name"]:
                                tool_calls[idx]["name"] = tool_call_delta.function.name

                                yield StreamEvent(
                                    type = StreamEventType.TOOL_CALL_START,
                                    tool_call_delta=ToolCallDelta(
                                        call_id = tool_calls[idx]["id"],
                                        name = tool_calls[idx]["name"]
                                    )
                                )

                        # The arguments will come in streaming so we must append the arguments 
                        if tool_call_delta.function.arguments:
                            tool_calls[idx]["arguments"] += tool_call_delta.function.arguments

                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_DELTA,
                                tool_call_delta=ToolCallDelta(
                                    call_id=tool_calls[idx]["id"],
                                    name=tool_call_delta.function.name,
                                    arguments_delta=tool_call_delta.function.arguments,
                                ),
                            ) # Tutta futa arguments !!

        for idx, tc in tool_calls.items():
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(
                    call_id=tc["id"],
                    name=tc["name"],
                    arguments=parse_tool_call_arguments(tc["arguments"]),
                ),
            )


        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            finish_reason=finish_reason,
            usage=usage,
        )   


    async def _non_stream_response(self, client , kwargs)->StreamEvent:
        """Non stream Response"""

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        text_delta = None

        usage = None

        if message.content:
            text_delta = TextDelta(content=message.content)

        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_token=response.usage.completion_tokens,
                total_tokens=response.usage.prompt_tokens_details.cached_tokens,
            )

        return StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            text_delta=text_delta,
            usage=usage,            
            finish_reason=choice.finish_reason
        )

