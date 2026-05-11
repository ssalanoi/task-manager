import os

os.environ.setdefault("API_KEY", "test-key-xyz")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

# Override the engine BEFORE importing the app so every layer (routers,
# get_session, init_db) shares the same single in-memory SQLite database.
from app import db as _db

_db.engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.drop_all(_db.engine)
    SQLModel.metadata.create_all(_db.engine)
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def auth_headers() -> dict:
    return {"X-API-Key": os.environ["API_KEY"]}
