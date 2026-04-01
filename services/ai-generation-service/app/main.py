from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.api.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.SERVICE_NAME,
    version="1.0.0",
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,
)

app.include_router(router, prefix=settings.API_PREFIX)


@app.get("/health")
@app.get(f"{settings.API_PREFIX}/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
