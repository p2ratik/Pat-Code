import logging

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from api.db.models import Base

logger = logging.getLogger(__name__)


async def ensure_tables(engine: AsyncEngine) -> None:
    expected_tables = set(Base.metadata.tables.keys())

    async with engine.begin() as conn:
        existing_tables = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )

        missing_tables = sorted(expected_tables - existing_tables)
        if not missing_tables:
            logger.info("Database tables already exist (%s)", len(existing_tables))
            return

        logger.info("Creating missing tables: %s", ", ".join(missing_tables))
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables validated and synchronized")