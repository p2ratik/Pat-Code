import logging
import ssl

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from api.db.models import Base, Role, Tool
from api.db.table_validator import ensure_tables

logger = logging.getLogger(__name__)

# Have to create a table for role and permission  
DEFAULT_ROLES = [
    {"name": "super_admin", "description": "Full system access"},
    {"name": "admin", "description": "Administrative access"},
    {"name": "user", "description": "Standard user access"},
    {"name": "premium", "description": "Premium user access"},
]


class CloudDatabase:
    def __init__(self, database_url: str):
        url = make_url(database_url)
        query = dict(url.query)

        ssl_context = None
        if query.get("sslmode") == "require":
            ssl_context = ssl.create_default_context()

        connect_args = {}
        if ssl_context is not None:
            connect_args["ssl"] = ssl_context

        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=5,
            connect_args=connect_args,
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self):
        await ensure_tables(self.engine)
        await self._seed_defaults()
        logger.info("CloudDatabase initialized")

    async def shutdown(self):
        await self.engine.dispose()
        logger.info("CloudDatabase shutdown")

    def get_session(self) -> AsyncSession:
        return self.session_factory()

    async def _seed_defaults(self):
        async with self.session_factory() as session:
            # Seed roles
            result = await session.execute(select(Role).limit(1))
            if not result.scalar():
                for role_data in DEFAULT_ROLES:
                    session.add(Role(**role_data))
                await session.commit()
                logger.info("Seeded default roles")

        await self._seed_tools()

    async def _seed_tools(self):
        """Seed the tools table with all builtin tool names.

        These names are the canonical reference for profile_tools. They must
        match exactly what create_default_registry() registers.
        """
        # Import here to avoid circular imports at module level
        from tools.builtins import get_all_builtin_tools
        from tools.subagents import get_default_subagent_definitions

        async with self.session_factory() as session:
            result = await session.execute(select(Tool).limit(1))
            if result.scalar():
                return  # already seeded

            # Builtin tools — instantiate with a dummy config to read .name
            from config.config import Config, ModelConfig, ApprovalPolicy
            from pathlib import Path

            dummy_config = Config(
                model=ModelConfig(name="gpt-4.1-mini"),
                cwd=Path.cwd(),
                approval=ApprovalPolicy.AUTO,
            )

            for tool_cls in get_all_builtin_tools():
                tool_instance = tool_cls(dummy_config)
                session.add(Tool(name=tool_instance.name, description=tool_instance.description))

            # Subagent tools
            from tools.subagents import SubagentTool
            for subagent_def in get_default_subagent_definitions():
                sub = SubagentTool(dummy_config, subagent_def)
                session.add(Tool(name=sub.name, description=sub.description))

            await session.commit()
            logger.info("Seeded builtin tools into tools table")
