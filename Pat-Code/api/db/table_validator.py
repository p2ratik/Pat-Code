import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from api.db.models import Base

logger = logging.getLogger(__name__)


async def ensure_tables(engine: AsyncEngine) -> None:
    """Ensure all ORM-defined tables and columns exist in the DB.

    Two-phase sync:
    1. Create any missing tables in bulk via metadata.create_all.
    2. For tables that already exist, add any missing columns via
       ALTER TABLE … ADD COLUMN IF NOT EXISTS …
       This handles schema drift when new columns are added to existing models
       without requiring a full Alembic migration setup.
    """
    expected_tables = set(Base.metadata.tables.keys())

    async with engine.begin() as conn:
        existing_tables = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )

        missing_tables = sorted(expected_tables - existing_tables)
        if missing_tables:
            logger.info("Creating missing tables: %s", ", ".join(missing_tables))
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created: %s", ", ".join(missing_tables))
        else:
            logger.info("All expected tables present (%s total)", len(existing_tables))

        # Phase 2: column-level drift — add missing columns on existing tables.
        added_columns: list[str] = []
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue  # just created — all columns already there

            existing_cols = await conn.run_sync(
                lambda sync_conn, tn=table_name: {
                    col["name"] for col in inspect(sync_conn).get_columns(tn)
                }
            )

            for col in table.columns:
                if col.name in existing_cols:
                    continue

                # Build a minimal SQL type string from the SQLAlchemy type.
                try:
                    col_type_str = col.type.compile(dialect=engine.dialect)
                except Exception:
                    col_type_str = str(col.type)

                nullable_clause = "" if col.nullable else " NOT NULL"
                sql = (
                    f'ALTER TABLE "{table_name}" '
                    f'ADD COLUMN IF NOT EXISTS "{col.name}" {col_type_str}{nullable_clause};'
                )
                logger.info("Adding missing column: %s.%s (%s)", table_name, col.name, col_type_str)
                await conn.execute(text(sql))
                added_columns.append(f"{table_name}.{col.name}")

        if added_columns:
            logger.info("Added missing columns: %s", ", ".join(added_columns))
        else:
            logger.debug("No column drift detected")