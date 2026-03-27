import asyncio
from openai import AsyncOpenAI
from typing import Any, AsyncGenerator
from client.response import TextDelta
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
                    api_key = API_KEY,
                    base_url = 'https://openrouter.ai/api/v1',
                )
            except Exception as e :
                print(f"LLM client not created : {e}")

        return self._client
    
    async def close(self)->None:
        """LLM client close er jonno"""
        pass

    async def chat_completion(self, messages: list[dict[str, Any]], stream:bool=True)->AsyncGenerator[StreamEvent]:

        client = self.get_client()

        kwargs = {
            "model":'nvidia/nemotron-3-super-120b-a12b:free',
            "messages": messages,
            "stream":stream
        }
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

        async for chunk in response:

            if hasattr(chunk, "usage") and chunk.usage:
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_token=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.prompt_tokens_details.cached_tokens,
                )

            if not chunk.choices[0].delta.content and not usage:
                continue

            choice = chunk.choices[0]
            delta = TextDelta(content=choice.delta.content)

            if choice.finish_reason:
                finish_reason = choice.finish_reason

            yield StreamEvent(
                type = StreamEventType.TEXT_DELTA,
                text_delta= delta,
                usage=usage,
                finish_reason=finish_reason
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

