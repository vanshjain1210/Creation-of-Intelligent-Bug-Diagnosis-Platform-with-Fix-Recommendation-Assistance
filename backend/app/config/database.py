"""SQLAlchemy database configuration."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config.settings import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_sqlite_columns() -> None:
    """Add new columns on existing SQLite files without wiping data."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(bugs)")).fetchall()
        if not rows:
            return
        existing = {row[1] for row in rows}
        if "root_cause" not in existing:
            conn.execute(text("ALTER TABLE bugs ADD COLUMN root_cause TEXT"))
            conn.commit()
