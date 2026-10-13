"""Pytest fixtures: in-memory MongoDB, isolated local storage, test app.

Environment must be configured BEFORE importing `app.main` so the cached
Settings object picks up test values.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# ---- point MongoDB to an in-memory emulator before app import --------------
import mongomock_motor  # noqa: E402

_TMP = tempfile.TemporaryDirectory(prefix="vision3d-test-")
os.environ["MONGODB_URL"] = "mongodb://localhost:27017"
os.environ["MONGODB_DB_NAME"] = "vision3d_test"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["AI_MODEL"] = "mock"
os.environ["JOB_WORKER_ENABLED"] = "false"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = str(Path(_TMP.name) / "storage")
os.environ["PUBLIC_BASE_URL"] = "http://testserver"
os.environ["LOG_LEVEL"] = "ERROR"

import app.db.mongodb as mongodb_module  # noqa: E402

mongodb_module.AsyncIOMotorClient = mongomock_motor.AsyncMongoMockClient
mongodb_module.AsyncIOMotorCollection = mongomock_motor.AsyncMongoMockCollection
mongodb_module.AsyncIOMotorDatabase = mongomock_motor.AsyncMongoMockDatabase

import io  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402
from app.services.storage_service import reset_storage_for_tests  # noqa: E402


@pytest.fixture(autouse=True)
def reset_storage():
    reset_storage_for_tests()
    yield
    reset_storage_for_tests()


async def _wipe_db():
    from app.db.mongodb import client as mongo_client

    if mongo_client is not None:
        db = mongo_client["vision3d_test"]
        for name in await db.list_collection_names():
            await db[name].drop()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        import asyncio

        asyncio.run(_wipe_db())
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient):
    """Register + login a fresh user; returns Authorization headers."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "tester@vision3d.dev",
            "username": "tester",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_user_headers(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@vision3d.dev",
            "username": "otheruser",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_test_image(format: str = "PNG", width: int = 64, height: int = 48) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (90, 120, 200)).save(buffer, format=format)
    return buffer.getvalue()


@pytest.fixture()
def sample_png() -> bytes:
    return make_test_image("PNG")


@pytest.fixture()
def sample_webp() -> bytes:
    return make_test_image("WEBP")


@pytest.fixture()
def upload(client: TestClient, auth_headers: dict, sample_png: bytes):
    response = client.post(
        "/api/v1/uploads",
        headers=auth_headers,
        files={"file": ("sample.png", sample_png, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def db_client():
    from app.db.mongodb import client

    return client
