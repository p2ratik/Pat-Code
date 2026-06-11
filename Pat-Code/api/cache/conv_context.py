import json
import uuid

from sqlalchemy import select, desc
from redis.asyncio import Redis

from api.db.database import CloudDatabase
from api.db.models import Conversation, Message

REHYDRATION_RECENT_LIMIT = 20
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7


class ConversationContextRepository:
    def __init__(
        self,
        db: CloudDatabase,
        redis: Redis,
    ):
        self.db = db
        self.redis = redis

    def _cache_key(self, conversation_id: str) -> str:
        return f"ctx:{conversation_id}"

    async def get_context(self, conversation_id: str) -> dict:
        key = self._cache_key(conversation_id)

        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)

        context = await self._load_from_postgres(conversation_id)

        await self.redis.setex(
            key,
            CACHE_TTL_SECONDS,
            json.dumps(context),
        )

        return context

    async def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_call_id: str | None = None,
        tool_calls: list | None = None,
    ) -> None:
        key = self._cache_key(conversation_id)

        cached = await self.redis.get(key)
        if not cached:
            return

        context = json.loads(cached)

        context["messages"].append(
            {
                "role": role,
                "content": content,
                "tool_call_id": tool_call_id,
                "tool_calls": tool_calls,
            }
        )

        context["messages"] = context["messages"][-REHYDRATION_RECENT_LIMIT:]

        await self.redis.setex(
            key,
            CACHE_TTL_SECONDS,
            json.dumps(context),
        )

    async def update_summary(
        self,
        conversation_id: str,
        summary: str,
    ) -> None:
        key = self._cache_key(conversation_id)

        cached = await self.redis.get(key)
        if not cached:
            return

        context = json.loads(cached)
        context["summary"] = summary

        await self.redis.setex(
            key,
            CACHE_TTL_SECONDS,
            json.dumps(context),
        )

    async def invalidate(
        self,
        conversation_id: str,
    ) -> None:
        await self.redis.delete(
            self._cache_key(conversation_id)
        )

    async def warm(
        self,
        conversation_id: str,
    ) -> None:
        context = await self._load_from_postgres(
            conversation_id
        )

        await self.redis.setex(
            self._cache_key(conversation_id),
            CACHE_TTL_SECONDS,
            json.dumps(context),
        )

    async def _load_from_postgres(
        self,
        conversation_id: str,
    ) -> dict:
        conversation_uuid = uuid.UUID(conversation_id)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(Conversation.summary)
                .where(
                    Conversation.id == conversation_uuid
                )
            )

            row = result.first()
            summary = row[0] if row else None

            if summary:
                result = await session.execute(
                    select(Message)
                    .where(
                        Message.conversation_id == conversation_uuid
                    )
                    .order_by(desc(Message.created_at))
                    .limit(REHYDRATION_RECENT_LIMIT)
                )

                messages = list(
                    reversed(result.scalars().all())
                )

            else:
                result = await session.execute(
                    select(Message)
                    .where(
                        Message.conversation_id == conversation_uuid
                    )
                    .order_by(Message.created_at)
                )

                messages = result.scalars().all()

        return {
            "summary": summary,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id,
                    "tool_calls": msg.tool_calls,
                }
                for msg in messages
            ],
        }