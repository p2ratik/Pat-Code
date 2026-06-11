import logging
import ssl

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from api.db.models import Base, Role
from api.db.table_validator import ensure_tables

logger = logging.getLogger(__name__)

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
            result = await session.execute(select(Role).limit(1))
            if result.scalar():
                return

            for role_data in DEFAULT_ROLES:
                session.add(Role(**role_data))

            await session.commit()
            logger.info("Seeded default roles")
