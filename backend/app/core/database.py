from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models."""


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create configured SQLAlchemy engine for SQLite or PostgreSQL."""
    settings = get_settings()
    url = database_url or settings.database_url
    connect_args = {}
    if _is_sqlite(url):
        connect_args = {"check_same_thread": False}
        if ":///" in url and ":memory:" not in url:
            db_path = Path(url.split(":///", 1)[1])
            db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )

    if _is_sqlite(url):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health(db: Session) -> bool:
    """Execute a lightweight query to verify database connectivity."""
    db.execute(text("SELECT 1"))
    return True
