import logging
import ssl

import asyncpg
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from api.db.models import Base, Role

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

        self._connect_kwargs = {
            "user": url.username,
            "password": url.password,
            "host": url.host,
            "port": url.port or 5432,
            "database": url.database,
            "ssl": ssl_context,
        }

        # The ORM/session layer remains SQLAlchemy, but actual driver connections
        # are created directly by asyncpg.
        self.engine = create_async_engine(
            "postgresql+asyncpg://",
            async_creator=self._connect_asyncpg,
            echo=False,
            pool_size=10,
            max_overflow=5,
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def _connect_asyncpg(self):
        return await asyncpg.connect(**self._connect_kwargs)

    async def initialize(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

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
