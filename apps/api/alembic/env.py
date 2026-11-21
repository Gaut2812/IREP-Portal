from logging.config import fileConfig
import os
import sys
from pathlib import Path

# Ensure api directory is on sys.path
api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from sqlalchemy import engine_from_config, pool
from alembic import context
from core.database import Base, db_url
import models.schema

config = context.config

if config.config_file_name is not None:
    # keep the app's loggers alive when migrations run in-process (tests, startup)
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

def get_url():
    return db_url

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def _run(connection) -> None:
    """SQLite batch mode rebuilds a table (copy, drop, rename); with foreign keys
    on, dropping a table that other rows reference fails. Switch enforcement off
    for the run, verify every reference, commit, then switch it back on (SQLite
    ignores the pragma inside an open transaction). Call with no transaction open."""
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            bad = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if bad:
                raise RuntimeError(f"Migration left {len(bad)} foreign-key violations, e.g. {bad[:3]}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def run_migrations_online() -> None:
    # Callers (tests, tooling) may pass an open connection via config.attributes
    given = config.attributes.get("connection")
    if given is not None:
        _run(given)
        return

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

