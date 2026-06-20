import logging
import ssl

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from api.db.models import Base, Role, Tool, AgentProfile, ProfileTool
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
            # Idempotent per-row upsert: only insert roles that don't exist yet.
            # The old one-shot check (if any role exists → skip all) was wrong —
            # it would silently skip seeding if a custom role was manually added.
            result = await session.execute(select(Role.name))
            existing_role_names = {row[0] for row in result.all()}

            new_roles = [r for r in DEFAULT_ROLES if r["name"] not in existing_role_names]
            if new_roles:
                for role_data in new_roles:
                    session.add(Role(**role_data))
                await session.commit()
                logger.info("Seeded %d default roles: %s", len(new_roles), [r["name"] for r in new_roles])
            else:
                logger.debug("All default roles already present")

        await self._seed_tools()
        await self._seed_default_profile()

    async def _seed_tools(self):
        """Seed the tools table with all builtin tool names.

        These names are the canonical reference for profile_tools. They must
        match exactly what create_default_registry() registers.
        Idempotent: skips tools that already exist by name.
        """
        try:
            from tools.builtins import get_all_builtin_tools
            from tools.subagents import get_default_subagent_definitions, SubagentTool
            from config.config import Config, ModelConfig, ApprovalPolicy
            from pathlib import Path
        except ImportError as e:
            logger.warning(f"Cannot seed tools — import failed: {e}")
            return

        dummy_config = Config(
            model=ModelConfig(name="gpt-4.1-mini"),
            cwd=Path.cwd(),
            approval=ApprovalPolicy.AUTO,
        )

        # Collect tool name → description
        tools_to_seed: dict[str, str] = {}

        for tool_cls in get_all_builtin_tools():
            try:
                tool_instance = tool_cls(dummy_config)
                tools_to_seed[tool_instance.name] = tool_instance.description or ""
            except Exception as e:
                logger.warning(f"Skipping tool {tool_cls.__name__}: {e}")

        for subagent_def in get_default_subagent_definitions():
            try:
                sub = SubagentTool(dummy_config, subagent_def)
                tools_to_seed[sub.name] = sub.description or ""
            except Exception as e:
                logger.warning(f"Skipping subagent: {e}")

        if not tools_to_seed:
            logger.warning("No tools found to seed")
            return

        async with self.session_factory() as session:
            # Check which tools already exist
            result = await session.execute(select(Tool.name))
            existing_names = {row[0] for row in result.all()}

            new_tools = {
                name: desc for name, desc in tools_to_seed.items()
                if name not in existing_names
            }

            if not new_tools:
                logger.debug("All tools already seeded")
                return

            for name, description in new_tools.items():
                session.add(Tool(name=name, description=description))

            await session.commit()
            logger.info(f"Seeded {len(new_tools)} tools into tools table: {sorted(new_tools.keys())}")

    # Safe tool subset given to every new user by default.
    # Read + search only — no shell, no write, no apply_patch.
    DEFAULT_USER_TOOLS = [
        "read_file",
        "list_dir",
        "grep",
        "glob",
        "web_search",
        "web_fetch",
    ]

    async def _seed_default_profile(self):
        """Seed the 'default_user' agent profile with a safe read-only tool set.

        This profile is auto-assigned to every new user in AuthService.create_user().
        Idempotent — skips if already seeded.
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(AgentProfile).where(AgentProfile.name == "default_user")
            )
            if result.scalar_one_or_none():
                logger.debug("Default user profile already seeded")
                return

            # Create the profile
            profile = AgentProfile(
                name="default_user",
                description="Default profile for new users. Read/search access only.",
                model_name="gpt-4.1-mini",
                temperature=0.7,
                max_turns=50,
                version=1,
                is_active=True,
            )
            session.add(profile)
            await session.flush()  # get profile.id before committing

            # Look up the safe tool subset and assign them
            result = await session.execute(
                select(Tool).where(Tool.name.in_(self.DEFAULT_USER_TOOLS))
            )
            found_tools = result.scalars().all()

            for tool in found_tools:
                session.add(ProfileTool(profile_id=profile.id, tool_id=tool.id))

            await session.commit()

            found_names = [t.name for t in found_tools]
            missing = set(self.DEFAULT_USER_TOOLS) - set(found_names)
            if missing:
                logger.warning(f"Default profile: some tools not found in DB: {missing}")

            logger.info(
                f"Seeded default_user profile with tools: {sorted(found_names)}"
            )
