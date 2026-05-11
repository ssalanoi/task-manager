from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_db
from .routers import tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Task Manager API",
    version="0.1.0",
    description="REST CRUD for tasks. All /tasks endpoints require X-API-Key.",
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


app.include_router(tasks.router)
