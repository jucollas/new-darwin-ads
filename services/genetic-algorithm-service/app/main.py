from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.router import router
from app.config import settings
from shared.database.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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
