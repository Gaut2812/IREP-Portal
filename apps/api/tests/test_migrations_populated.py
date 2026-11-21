"""Migrations must also work on a database that has rows (the demo VM, a dev DB).

SQLite batch mode rebuilds a table by copy/drop/rename; with foreign keys on,
dropping a table other rows reference fails. Empty databases never show it.
"""
import sys
from pathlib import Path

api_dir = Path(__file__).resolve().parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event


def _cfg(conn):
    cfg = Config(str(api_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_dir / "alembic"))
    cfg.attributes["connection"] = conn
    return cfg


def test_upgrade_rebuilds_referenced_tables_without_losing_rows(tmp_path):
    eng = create_engine(f"sqlite:///{(tmp_path / 'pop.db').as_posix()}")

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _):          # like the app: foreign keys enforced
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    with eng.connect() as conn:
        command.upgrade(_cfg(conn), "0007_trainer_batches")
        conn.commit()
        now = "2026-11-20 10:00:00"
        conn.exec_driver_sql(
            "INSERT INTO users (id, email, hashed_password, role, name, avatar_initials, language_pref, is_active, failed_logins, college_id, created_at, updated_at) "
            f"VALUES ('u1', 'a@b.c', 'x', 'student', 'A', 'A', 'en', 1, 0, 'c1', '{now}', '{now}')")
        conn.exec_driver_sql(
            "INSERT INTO sessions (id, title, track, trainer_name, scheduled_start, scheduled_end, duration_min, session_type, status, has_lab_preload, college_id, created_at, updated_at) "
            f"VALUES ('s1', 'T', 'AI', 'X', '{now}', '{now}', 60, 'Live', 'Upcoming', 0, 'c1', '{now}', '{now}')")
        conn.exec_driver_sql(
            "INSERT INTO join_events (id, session_id, user_id, event, at, source, college_id, created_at, updated_at) "
            f"VALUES ('j1', 's1', 'u1', 'joined', '{now}', 'portal', 'c1', '{now}', '{now}')")
        conn.commit()

        command.upgrade(_cfg(conn), "head")          # 0008 rebuilds `sessions`, which join_events references
        conn.commit()
        assert conn.exec_driver_sql("SELECT count(*) FROM sessions").scalar() == 1
        assert conn.exec_driver_sql("SELECT count(*) FROM join_events").scalar() == 1
        assert "room" in {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(sessions)")}
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1          # enforcement restored
    eng.dispose()
