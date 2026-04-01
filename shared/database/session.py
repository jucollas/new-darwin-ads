from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
import os

class Base(DeclarativeBase):
    pass

engine = None
async_session_factory = None


async def init_db():
    global engine, async_session_factory
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://adgen:changeme_in_production@postgres:5432/adgen_ai",
    )
    debug = os.getenv("DEBUG", "false").lower() == "true"
    engine = create_async_engine(database_url, echo=debug)
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
