import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from sqlalchemy import select

from agent.agent import Agent
from agent.events import AgentEvent, AgentEventType
from api.cloud_runtime import CloudAgentRuntime
from api.cache.profile_cache import ProfileCache, ProfileConfig
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
        profile_cache: ProfileCache,
        base_tool_registry=None,
        mcp_service=None,
        credential_manager=None,
    ):
        self.db = db
        self.conversation_context_repo = conversation_context_repo
        self.profile_cache = profile_cache
        self.base_tool_registry = base_tool_registry
        self.mcp_service = mcp_service
        self.credential_manager = credential_manager

    async def chat(self, user_id: str, message: str, conversation_id: str | None = None) -> dict:
        # One cached DB round-trip: profile + prompt + tools
        profile_config = await self.profile_cache.get_profile_config(user_id)

        # Load connected MCP servers for this user; empty dict if none connected
        mcp_configs = {}
        if self.mcp_service:
            mcp_configs = await self.mcp_service.build_mcp_configs(user_id)

        config = self._build_config(profile_config, mcp_configs)

        # Validate existing conversation or create a new one
        conversation_id = await self._resolve_conversation(user_id, conversation_id)

        # Create agent_run BEFORE agent starts (status=running)
        run_id = await self._create_agent_run(
            user_id, conversation_id, message,
            profile_id=profile_config.profile_id,   # Bug 5 fix: always captured
        )

        try:
            final_response = ""
            events: list[AgentEvent] = []

            async with Agent(config, runtime=CloudAgentRuntime.build(
            config,
            base_registry=self.base_tool_registry,
            user_id=user_id,
            credential_manager=self.credential_manager,
        )) as agent:
                await self._rehydrate_context(agent, conversation_id)

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

                # Must be read INSIDE the async-with block; __aexit__ sets runtime=None.
                post_run_summary = agent.runtime.context_manager._compacted_summary

            # Save assistant response
            await self._save_message(conversation_id, "assistant", final_response)
            await self.conversation_context_repo.append_message(
                conversation_id,
                role="assistant",
                content=final_response,
            )

            # Persist compaction summary if compression happened during the run.
            if post_run_summary and post_run_summary != pre_run_summary:
                await self._persist_summary(conversation_id, post_run_summary)

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

    # ------------------------------------------------------------------
    # Config assembly  (Bug 3 fix: prompt_content is now used)
    # ------------------------------------------------------------------

    def _build_config(self, profile_config: ProfileConfig, mcp_configs: dict | None = None) -> Config:
        """Build a per-request Config from the cached ProfileConfig.

        mcp_configs is the dict[name, MCPServerConfig] produced by
        CloudMCPService.build_mcp_configs(). Passed straight into Config
        so MCPManager picks them up unchanged.
        """
        return Config(
            model=ModelConfig(
                name=profile_config.model_name,
                temperature=profile_config.temperature,
            ),
            cwd=Path.cwd(),
            max_turns=profile_config.max_turns,
            allowed_tools=profile_config.allowed_tools,
            system_prompt_override=profile_config.prompt_content,
            mcp_servers=mcp_configs or {},
            approval=ApprovalPolicy.AUTO,
        )

    async def _resolve_conversation(self, user_id: str, conversation_id: str | None) -> str:
        """Return a valid conversation_id owned by user_id.

        - None → create a new conversation.
        - Provided → verify it exists AND belongs to this user.
        """
        if not conversation_id or not conversation_id.strip():
            return await self._create_conversation(user_id)

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
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
            )
            conv = result.scalar_one_or_none()
            if conv:
                conv.summary = summary
                await session.commit()
                logger.info(f"Persisted compaction summary for conversation {conversation_id}")

        await self.conversation_context_repo.update_summary(conversation_id, summary)


    async def _create_agent_run(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        profile_id: str | None = None,
    ) -> str:
        async with self.db.get_session() as session:
            run = AgentRun(
                user_id=uuid.UUID(user_id),
                conversation_id=uuid.UUID(conversation_id),
                profile_id=uuid.UUID(profile_id) if profile_id else None,  # Bug 5 fix
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
