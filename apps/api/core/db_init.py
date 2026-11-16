"""Development-time schema sync.

Production uses Alembic migrations only. In development (SQLite) the app
also tolerates a database created by an older create_all(): it creates any
missing tables and adds any missing columns so a `git pull` never leaves the
local database behind. Column drops/renames are never attempted here.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from core.database import Base


def _default_clause(column) -> str:
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return ""
    val = default.arg
    if isinstance(val, bool):
        return f" DEFAULT {1 if val else 0}"
    if isinstance(val, (int, float)):
        return f" DEFAULT {val}"
    if isinstance(val, str):
        escaped = val.replace("'", "''")
        return f" DEFAULT '{escaped}'"
    return ""


def ensure_schema(engine: Engine) -> dict:
    """Create missing tables and add missing columns. Returns a summary."""
    import models.schema  # noqa: F401  (registers all models on Base)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    Base.metadata.create_all(engine)
    added = {"tables": [], "columns": []}
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                added["tables"].append(table.name)
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_cols:
                    continue
                coltype = column.type.compile(dialect=engine.dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {coltype}' + _default_clause(column)
                conn.execute(text(ddl))
                added["columns"].append(f"{table.name}.{column.name}")
    return added
