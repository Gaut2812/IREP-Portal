import datetime
from sqlalchemy import create_engine, DateTime, String, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from core.config import settings

# Format database URL for sync engine if sqlite+aiosqlite was specified
db_url = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "sqlite:///")

connect_args = {}
if "sqlite" in db_url:
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    echo=False,
    connect_args=connect_args
)

# Enable SQLite foreign key enforcement
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        # Check if underlying connection supports SQLite PRAGMA
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    pass

class TenantModel(Base):
    __abstract__ = True
    
    college_id: Mapped[str] = mapped_column(String(64), index=True, default=settings.DEFAULT_COLLEGE_ID)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
