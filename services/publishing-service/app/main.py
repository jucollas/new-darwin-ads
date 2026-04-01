from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.SERVICE_NAME,
    version="0.1.0",
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,
)


@app.get("/health")
@app.get(f"{settings.API_PREFIX}/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
