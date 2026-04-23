import asyncio
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from typing import Any, AsyncGenerator
from client.response import TextDelta, ToolCall, ToolCallDelta, parse_tool_call_arguments
from client.response import TokenUsage
from client.response import StreamEventType
from client.response import StreamEvent
from config.config import Config
import os

class LLMClient():

    def __init__(self, config:Config):
        self._client : AsyncOpenAI | None = None
        self.config = config
        self._max_retries = 3


    def get_client(self)->AsyncOpenAI:
        """This function creates and returns an async Open AI client if not existing"""

        
        if self._client is None:
            try:
                self._client = AsyncOpenAI(
                    api_key = self.config.api_key ,
                    base_url = self.config.base_url   #'https://openrouter.ai/api/v1',
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
            "model":self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "stream":stream
        }

        if tools:
            kwargs['tools'] = self._build_tools(tools=tools)
            kwargs['tool_choice'] = "auto"

        for attempt in range(self._max_retries + 1):
            try:
                if stream:
                    async for event in self._stream_response(client, kwargs):
                        yield event
                else:
                    event = await self._non_stream_response(client, kwargs)
                    yield event
                return
            except RateLimitError as e:
                # Exponential backoff
                if attempt < self._max_retries:
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Rate limit exceeded: {e}",
                    )
                    return
            except APIConnectionError as e:
                if attempt < self._max_retries:
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Connection error: {e}",
                    )
                    return
            except APIError as e:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    error=f"API error: {e}",
                )
                return     

    async def _stream_response(self, client, kwargs)->AsyncGenerator[StreamEvent]:
        """Stream Response"""
        # when ever stream = True its gonna return a AsyncGenerator not a normal Coroutine object

        response = await client.chat.completions.create(**kwargs)

        usage : TokenUsage | None = None
        finish_reason : str | None = None

        tool_calls : dict[int, dict[str, Any]] = {} # Dict to track tool calls {index : tool_call_details}

        async for chunk in response:

            if hasattr(chunk, "usage") and chunk.usage:
                cached_tokens = 0
                prompt_details = getattr(chunk.usage, "prompt_tokens_details", None)
                if prompt_details and getattr(prompt_details, "cached_tokens", None) is not None:
                    cached_tokens = prompt_details.cached_tokens

                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                    cached_tokens=cached_tokens,
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
            cached_tokens = 0
            prompt_details = getattr(response.usage, "prompt_tokens_details", None)
            if prompt_details and getattr(prompt_details, "cached_tokens", None) is not None:
                cached_tokens = prompt_details.cached_tokens

            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=cached_tokens,
            )

        return StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            text_delta=text_delta,
            usage=usage,            
            finish_reason=choice.finish_reason
        )

