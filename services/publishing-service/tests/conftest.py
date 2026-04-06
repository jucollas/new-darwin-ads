import asyncio
import os
import uuid

# Set test encryption key before any app imports
os.environ.setdefault(
    "META_TOKEN_ENCRYPTION_KEY",
    "dGVzdC1rZXktZm9yLXVuaXQtdGVzdHMhIQ==",  # test key
)
# Generate a proper Fernet key for tests
from cryptography.fernet import Fernet
os.environ["META_TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text, event, schema

from shared.database.session import Base

# Force model registration
import app.models.publishing  # noqa: F401


MOCK_USER = {
    "user_id": str(uuid.uuid4()),
    "email": "test@test.com",
    "name": "Test User",
    "roles": ["user"],
}


def _is_sqlite(url: str) -> bool:
    return "sqlite" in url


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client():
    """Test client with mocked auth. Works with PostgreSQL or SQLite."""
    db_url = os.getenv(
        "TEST_DATABASE_URL",
        "sqlite+aiosqlite:///./test_publishing.db",
    )
    using_sqlite = _is_sqlite(db_url)

    execution_options = {}
    if using_sqlite:
        execution_options["schema_translate_map"] = {"publishing_schema": None}

    engine = create_async_engine(
        db_url,
        echo=False,
        execution_options=execution_options,
    )

    if using_sqlite:
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        for table in Base.metadata.tables.values():
            for col in table.columns:
                if col.server_default is not None:
                    sd_text = str(col.server_default.arg) if hasattr(col.server_default, "arg") else ""
                    if "NOW()" in sd_text.upper():
                        col.server_default = schema.DefaultClause(text("CURRENT_TIMESTAMP"))

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        if not using_sqlite:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS publishing_schema"))
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def override_get_current_user():
        return MOCK_USER

    from shared.database.session import get_db
    from shared.auth.jwt_middleware import get_current_user
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()

    # Clean up test data
    async with engine.begin() as conn:
        if using_sqlite:
            await conn.execute(text("DELETE FROM publications"))
            await conn.execute(text("DELETE FROM ad_accounts"))
        else:
            await conn.execute(text("DELETE FROM publishing_schema.publications"))
            await conn.execute(text("DELETE FROM publishing_schema.ad_accounts"))

    await engine.dispose()
