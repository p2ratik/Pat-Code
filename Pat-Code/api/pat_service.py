import uuid
import logging
from datetime import datetime
from pathlib import Path
from sqlalchemy import select, desc

from agent.agent import Agent
from agent.events import AgentEvent, AgentEventType
from config.config import Config, ModelConfig, ApprovalPolicy
from api.db.database import CloudDatabase
from api.db.models import (
    Conversation, Message, AgentRun, AgentProfile, 
    UserAgentProfile, ProfileTool, Tool
)
from utils.text import count_tokens

logger = logging.getLogger(__name__)

REHYDRATION_RECENT_LIMIT = 20


class PATService:
    def __init__(self, db: CloudDatabase):
        self.db = db

    async def chat(self, user_id: str, message: str, conversation_id: str | None = None) -> dict:
        # Build config from DB + env
        config = await self._build_config(user_id)

        # Validate existing conversation or create a new one
        conversation_id = await self._resolve_conversation(user_id, conversation_id)

        # Create agent_run BEFORE agent starts (status=running)
        run_id = await self._create_agent_run(user_id, conversation_id, message)

        try:
            # Save user message
            await self._save_message(conversation_id, "user", message)

            # Run agent
            final_response = ""
            events: list[AgentEvent] = []

            async with Agent(config) as agent:
                # Rehydrate conversation context
                await self._rehydrate_context(agent, conversation_id)

                async for event in agent.run(message):
                    events.append(event)

                    if event.type == AgentEventType.TEXT_COMPLETE:
                        final_response = event.data.get("content", "")

            # Save assistant response
            await self._save_message(conversation_id, "assistant", final_response)

            # Update agent_run to completed
            step_count = sum(
                1 for e in events 
                if e.type in (AgentEventType.TOOL_CALL_START, AgentEventType.TOOL_CALL_COMPLETE)
            )
            await self._update_agent_run(run_id, "completed", final_response, step_count=step_count)

            return {
                "conversation_id": conversation_id,
                "response": final_response,
            }

        except Exception as e:
            await self._update_agent_run(run_id, "failed", error_message=str(e))
            logger.exception(f"Agent run failed: {e}")
            raise

    async def _build_config(self, user_id: str) -> Config:
        profile = await self._get_user_profile(user_id)
        allowed_tools = await self._get_allowed_tools(user_id)

        model_name = profile["model_name"] if profile else "gpt-4.1-mini"
        temperature = profile["temperature"] if profile else 0.7
        max_turns = profile["max_turns"] if profile else 100

        config = Config(
            model=ModelConfig(name=model_name, temperature=temperature),
            cwd=Path.cwd(),
            max_turns=max_turns,
            allowed_tools=allowed_tools,
            approval=ApprovalPolicy.AUTO,
        )

        return config

    async def _get_user_profile(self, user_id: str) -> dict | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentProfile)
                .join(UserAgentProfile, UserAgentProfile.profile_id == AgentProfile.id)
                .where(UserAgentProfile.user_id == uuid.UUID(user_id))
                .where(AgentProfile.is_active == True)
                .limit(1)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return None

            return {
                "id": str(profile.id),
                "model_name": profile.model_name,
                "temperature": profile.temperature,
                "max_turns": profile.max_turns,
            }

    async def _get_allowed_tools(self, user_id: str) -> list[str] | None:
        async with self.db.get_session() as session:
            # Get profile for user
            result = await session.execute(
                select(AgentProfile.id)
                .join(UserAgentProfile, UserAgentProfile.profile_id == AgentProfile.id)
                .where(UserAgentProfile.user_id == uuid.UUID(user_id))
                .where(AgentProfile.is_active == True)
                .limit(1)
            )
            profile_row = result.first()
            if not profile_row:
                return None  # No profile = all tools (default)

            profile_id = profile_row[0]

            # Get tool names from profile_tools
            result = await session.execute(
                select(Tool.name)
                .join(ProfileTool, ProfileTool.tool_id == Tool.id)
                .where(ProfileTool.profile_id == profile_id)
            )
            tool_names = [row[0] for row in result.all()]

            # Empty list means no tools configured for this profile — allow all
            return tool_names if tool_names else None

    async def _resolve_conversation(self, user_id: str, conversation_id: str | None) -> str:
        """Return a valid conversation_id owned by user_id.

        - If conversation_id is None → create a new one.
        - If conversation_id is provided → verify it exists AND belongs to this user.
          If not found or wrong owner → raise ValueError (surfaces as 400 in the route).
        """
        if not conversation_id or not conversation_id.strip():
            return await self._create_conversation(user_id)

        # Validate UUID format first to give a clean error
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise ValueError(f"Invalid conversation_id format: {conversation_id!r}")

        async with self.db.get_session() as session:
            result = await session.execute(
                select(Conversation.id).where(
                    Conversation.id == conv_uuid,
                    Conversation.user_id == uuid.UUID(user_id),
                )
            )
            row = result.first()

        if not row:
            raise ValueError(
                f"Conversation {conversation_id} not found or does not belong to this user."
            )

        return conversation_id

    async def _create_conversation(self, user_id: str) -> str:
        async with self.db.get_session() as session:
            conversation = Conversation(
                user_id=uuid.UUID(user_id),
                channel="api",
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            return str(conversation.id)

    async def _save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_call_id: str | None = None,
        tool_calls: list | None = None,
    ):
        async with self.db.get_session() as session:
            msg = Message(
                conversation_id=uuid.UUID(conversation_id),
                role=role,
                content=content,
                token_count=count_tokens(content or "", "gpt-4.1-mini"),
                tool_call_id=tool_call_id,
                tool_calls=tool_calls,
            )
            session.add(msg)
            await session.commit()

    async def _rehydrate_context(self, agent: Agent, conversation_id: str):
        async with self.db.get_session() as session:
            # Check for summary
            result = await session.execute(
                select(Conversation.summary).where(
                    Conversation.id == uuid.UUID(conversation_id)
                )
            )
            row = result.first()
            summary = row[0] if row else None

            if summary:
                # Load summary as base context
                agent.session.context_manager.replace_with_summary(summary)

                # Also load last N messages so recent context is not lost
                result = await session.execute(
                    select(Message)
                    .where(Message.conversation_id == uuid.UUID(conversation_id))
                    .order_by(desc(Message.created_at))
                    .limit(REHYDRATION_RECENT_LIMIT)
                )
                recent = list(reversed(result.scalars().all()))
                self._inject_messages(agent, recent)
                return

            # No summary — load full message history
            result = await session.execute(
                select(Message)
                .where(Message.conversation_id == uuid.UUID(conversation_id))
                .order_by(Message.created_at)
            )
            messages = result.scalars().all()
            self._inject_messages(agent, messages)

    def _inject_messages(self, agent: Agent, messages: list):
        for msg in messages:
            if msg.role == "user":
                agent.session.context_manager.add_user_message(msg.content or "")
            elif msg.role == "assistant":
                agent.session.context_manager.add_assistant_message(
                    msg.content, msg.tool_calls
                )
            elif msg.role == "tool":
                agent.session.context_manager.add_tool_result(
                    msg.tool_call_id or "", msg.content or ""
                )

    async def _create_agent_run(self, user_id: str, conversation_id: str, message: str) -> str:
        async with self.db.get_session() as session:
            run = AgentRun(
                user_id=uuid.UUID(user_id),
                conversation_id=uuid.UUID(conversation_id),
                status="running",
                input_message=message,
                started_at=datetime.utcnow(),
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return str(run.id)

    async def _update_agent_run(
        self,
        run_id: str,
        status: str,
        final_response: str | None = None,
        error_message: str | None = None,
        step_count: int | None = None,
    ):
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentRun).where(AgentRun.id == uuid.UUID(run_id))
            )
            run = result.scalar_one_or_none()
            if not run:
                return

            run.status = status
            run.completed_at = datetime.utcnow()

            if final_response:
                run.final_response = final_response
            if error_message:
                run.error_message = error_message
            if step_count is not None:
                run.total_steps = step_count

            await session.commit()
