from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from alembic.ddl.impl import DefaultImpl
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure alembic_version table uses VARCHAR(128) for version_num to support descriptive migration tags
_orig_version_table_impl = DefaultImpl.version_table_impl


def _custom_version_table_impl(
    self,
    *,
    version_table: str,
    version_table_schema: str | None,
    version_table_pk: bool,
    **kw,
) -> Table:
    vt = Table(
        version_table,
        MetaData(),
        Column("version_num", String(128), nullable=False),
        schema=version_table_schema,
    )
    if version_table_pk:
        vt.append_constraint(
            PrimaryKeyConstraint("version_num", name=f"{version_table}_pkc")
        )
    return vt


DefaultImpl.version_table_impl = _custom_version_table_impl

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from database.core.base import Base
from database.core.db_url import prepare_async_database_url
from database.models import (  # noqa: F401
    JobRecord,
    JobSource,
    NotificationDelivery,
    NotificationRecord,
    User,
    UserPreferences,
)

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata

_raw_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/freelance",
)
_db_url, _db_connect_args = prepare_async_database_url(_raw_url)
config.set_main_option("sqlalchemy.url", _db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    try:
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("ALTER TABLE IF EXISTS alembic_version ALTER COLUMN version_num TYPE VARCHAR(128);")
            )
    except Exception:
        pass

    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        try:
            if connection.dialect.name == "postgresql":
                connection.execute(
                    text("ALTER TABLE IF EXISTS alembic_version ALTER COLUMN version_num TYPE VARCHAR(128);")
                )
        except Exception:
            pass
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
        connect_args=_db_connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
