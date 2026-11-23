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

# The migration chain before S1 (master up to Nov 2026). It was replaced by 0001_baseline, so a database
# stamped with one of these cannot be upgraded in place: the tables differ. Refuse with what to do.
LEGACY_REVISIONS = {
    "0001_screen24_coding_foundation", "0002_foundation_cohort", "0003_screen12_dashboard",
    "0004_screen13_trainer_dashboard", "0005_screen19_college_overview", "0006_screen15_parent_view",
    "0007_screen08_live_sessions", "0008_screen07_live_classroom", "0009_screen29_virtual_labs",
    "0010_screen30_sprint_board", "0011_screen36_mock_interviews", "0012_screen34_discussions",
    "0013_screen35_message_hub",
}


def _refuse_legacy_chain(connection) -> None:
    from sqlalchemy import inspect, text
    if "alembic_version" not in inspect(connection).get_table_names():
        return
    found = {r[0] for r in connection.execute(text("SELECT version_num FROM alembic_version"))} & LEGACY_REVISIONS
    connection.rollback()
    if found:
        raise RuntimeError(
            f"This database uses the old migration chain (revision {sorted(found)[0]}), which was replaced by "
            "0001_baseline. It cannot be upgraded in place. Development database: delete it (SQLite: apps/api/irep.db; "
            "PostgreSQL: drop and recreate the database), then run `alembic upgrade head` and `seed/run_seed.py`. "
            "A database with real data: stop and ask for a reviewed data migration; do not stamp it.")


def _run(connection) -> None:
    """SQLite batch mode rebuilds a table (copy, drop, rename); with foreign keys
    on, dropping a table that other rows reference fails. Switch enforcement off
    for the run, verify every reference, commit, then switch it back on (SQLite
    ignores the pragma inside an open transaction). Call with no transaction open."""
    _refuse_legacy_chain(connection)
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

