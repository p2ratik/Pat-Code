import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from sqlalchemy import select

from agent.agent import Agent
from agent.events import AgentEvent, AgentEventType
from api.cloud_runtime import CloudAgentRuntime
from config.config import Config, ModelConfig, ApprovalPolicy
from api.db.database import CloudDatabase
from api.db.models import Conversation, Message, AgentRun
from utils.text import count_tokens
from api.cache.conv_context import ConversationContextRepository

logger = logging.getLogger(__name__)

class PATService:
    def __init__(
        self,
        db: CloudDatabase,
        conversation_context_repo: ConversationContextRepository,
        auth_service=None,
        base_tool_registry=None,
        # Phase 4: event_bus: EventBus | None = None,
        # Phase 5: qdrant: AsyncQdrantClient | None = None,
    ):
        self.db = db
        self.conversation_context_repo = conversation_context_repo
        self.auth_service = auth_service  # Phase 2: delegates profile/tool resolution
        self.base_tool_registry = base_tool_registry  # shared singleton, never rebuilt per-request

    async def chat(self, user_id: str, message: str, conversation_id: str | None = None) -> dict:
        # Build config from DB + env
        config = await self._build_config(user_id)

        # Validate existing conversation or create a new one
        conversation_id = await self._resolve_conversation(user_id, conversation_id)

        # Create agent_run BEFORE agent starts (status=running)
        run_id = await self._create_agent_run(user_id, conversation_id, message)

        try:
            # Rehydrate prior conversation state before adding the new user turn.
            # Agent.run() appends the current user message into its own context.
            final_response = ""
            events: list[AgentEvent] = []

            async with Agent(config, runtime=CloudAgentRuntime.build(config, base_registry=self.base_tool_registry)) as agent:
                await self._rehydrate_context(agent, conversation_id)

                # Snapshot: if rehydration loaded a previous summary, it sets
                # _compacted_summary. We record this so post-run we can detect
                # if a NEW compaction happened (summary changed).
                pre_run_summary = agent.runtime.context_manager._compacted_summary

                # Save user message after rehydration so it is not injected twice.
                await self._save_message(conversation_id, "user", message)
                await self.conversation_context_repo.append_message(
                    conversation_id,
                    role="user",
                    content=message,
                )

                async for event in agent.run(message):
                    events.append(event)

                    if event.type == AgentEventType.TEXT_COMPLETE:
                        final_response = event.data.get("content", "")

                # Read BEFORE async with exits — __aexit__ sets runtime = None
                post_run_summary = agent.runtime.context_manager._compacted_summary

            # Save assistant response
            await self._save_message(conversation_id, "assistant", final_response)
            await self.conversation_context_repo.append_message(
                conversation_id,
                role="assistant",
                content=final_response,
            )

            # Persist compaction summary if compression happened during the run.
            # The agentic loop calls context_manager.replace_with_summary() when
            # context overflows 80% of the model's context window. That wipes the
            # in-memory messages but never persists — we must catch it here.
            if post_run_summary and post_run_summary != pre_run_summary:
                await self._persist_summary(conversation_id, post_run_summary)

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
        """Build a per-request Config from DB.

        Delegates to AuthService for profile + tool resolution.
        AuthService handles admin bypass (admins see all tools).
        """
        profile = None
        allowed_tools = None

        if self.auth_service:
            profile = await self.auth_service.get_user_profile(user_id)
            allowed_tools = await self.auth_service.get_allowed_tools(user_id)

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
        context = await self.conversation_context_repo.get_context(conversation_id)
        if context["summary"]:
            agent.runtime.context_manager.replace_with_summary(context["summary"])
        self._inject_messages(agent, context["messages"])


    def _inject_messages(self, agent: Agent, messages: list[dict[str, Any] | Message]):
        for msg in messages:
            role = msg["role"] if isinstance(msg, dict) else msg.role
            content = msg["content"] if isinstance(msg, dict) else msg.content
            tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else msg.tool_calls
            tool_call_id = msg.get("tool_call_id") if isinstance(msg, dict) else msg.tool_call_id

            if role == "user":
                agent.runtime.context_manager.add_user_message(content or "")
            elif role == "assistant":
                agent.runtime.context_manager.add_assistant_message(
                    content,
                    tool_calls,
                )
            elif role == "tool":
                agent.runtime.context_manager.add_tool_result(
                    tool_call_id or "",
                    content or "",
                )

    async def _persist_summary(self, conversation_id: str, summary: str):
        """Write compaction summary to PostgreSQL + Redis cache.

        Called after a run where the agentic loop compressed context.
        Without this, the summary is lost and the next request starts fresh.
        """
        # PostgreSQL — conversations.summary
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
            )
            conv = result.scalar_one_or_none()
            if conv:
                conv.summary = summary
                await session.commit()
                logger.info(f"Persisted compaction summary for conversation {conversation_id}")

        # Redis cache
        await self.conversation_context_repo.update_summary(conversation_id, summary)

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
