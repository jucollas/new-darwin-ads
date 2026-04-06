import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


_engine = None
_session_factory = None


def get_sync_session() -> Session:
    """Create a synchronous DB session for use in Celery tasks."""
    global _engine, _session_factory
    if _engine is None:
        url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://adgen:changeme_in_production@postgres:5432/adgen_ai",
        ).replace("postgresql+asyncpg", "postgresql+psycopg2")
        _engine = create_engine(url, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=_engine)
    return _session_factory()
