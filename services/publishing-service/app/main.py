from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.api.router import router
from app.utils.seed_meta_account import seed_meta_account_if_empty
import shared.database.session as db_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_session.init_db()
    async with db_session.async_session_factory() as session:
        await seed_meta_account_if_empty(session)
    yield


app = FastAPI(
    title=settings.SERVICE_NAME,
    version="1.0.0",
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,
)

app.include_router(router, prefix=settings.API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
