"""MongoDB connection management using Motor (async driver).

Connection:
- Shared ``AsyncIOMotorClient`` with configurable pool (maxPoolSize / minPoolSize).
- ``retryWrites`` and ``retryReads`` enabled for Atlas resilience.

Indexes:
- All six collections have their required indexes created at startup.
- ``sessions.expires_at`` carries a TTL index (``expireAfterSeconds=0``) so
  MongoDB automatically purges expired sessions — no cron job needed.

IMPORTANT — index naming:
  Do NOT pass explicit ``name=`` to IndexModel on existing collections.
  MongoDB auto-names indexes from the field spec (e.g. ``email_1``).
  If a named index is submitted with a key spec that already exists under a
  *different* name, MongoDB tries to drop-then-recreate it, which blocks
  until all in-flight operations complete and causes a startup hang.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.config import get_settings

logger = logging.getLogger(__name__)

client: Optional[AsyncIOMotorClient] = None


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


async def connect() -> AsyncIOMotorDatabase:
    """Create the shared Mongo client and ensure indexes exist."""
    global client
    settings = get_settings()
    if client is None:
        client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            # ── Timeouts ───────────────────────────────────────────────────
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=30_000,
            # ── Connection pool ────────────────────────────────────────────
            maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
            minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
            # ── Atlas resilience ───────────────────────────────────────────
            retryWrites=True,
            retryReads=True,
        )
    db = client[settings.MONGODB_DB_NAME]
    await _ensure_indexes(db)
    return db


async def disconnect() -> None:
    global client
    if client is not None:
        client.close()
        client = None


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    if client is None:
        await connect()
    yield client[get_settings().MONGODB_DB_NAME]  # type: ignore[index]


def col(db: AsyncIOMotorDatabase, name: str) -> AsyncIOMotorCollection:
    return db[name]


# ---------------------------------------------------------------------------
# Index bootstrap
# ---------------------------------------------------------------------------


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Idempotently create all collection indexes.

    Called once at startup.  Motor / MongoDB silently skip indexes that
    already exist with identical key specs and options.
    """

    # ── users ─────────────────────────────────────────────────────────────────
    await db["users"].create_indexes(
        [
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("username", ASCENDING)], unique=True),
            IndexModel([("deleted_at", ASCENDING)], sparse=True),
        ]
    )
    logger.debug("Indexes ensured: users")

    # ── projects ──────────────────────────────────────────────────────────────
    await db["projects"].create_indexes(
        [
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("name", ASCENDING)]),
            IndexModel([("deleted_at", ASCENDING)], sparse=True),
        ]
    )
    logger.debug("Indexes ensured: projects")

    # ── jobs (generations) ────────────────────────────────────────────────────
    await db["jobs"].create_indexes(
        [
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("project_id", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
    )
    logger.debug("Indexes ensured: jobs")

    # ── model_metadata ────────────────────────────────────────────────────────
    # unique: one metadata doc per generation job
    await db["model_metadata"].create_indexes(
        [
            IndexModel([("generation_id", ASCENDING)], unique=True),
        ]
    )
    logger.debug("Indexes ensured: model_metadata")

    # ── usage_records ─────────────────────────────────────────────────────────
    await db["usage_records"].create_indexes(
        [
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
        ]
    )
    logger.debug("Indexes ensured: usage_records")

    # ── sessions ──────────────────────────────────────────────────────────────
    # TTL: MongoDB removes docs whose expires_at < now automatically.
    await db["sessions"].create_indexes(
        [
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
        ]
    )
    logger.debug("Indexes ensured: sessions (TTL on expires_at)")

    # ── quality_reports ───────────────────────────────────────────────────────
    await db["quality_reports"].create_indexes(
        [
            IndexModel([("project_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("model_asset_id", ASCENDING)]),
            IndexModel([("user_id", ASCENDING)]),
        ]
    )
    logger.debug("Indexes ensured: quality_reports")

    # ── edit_history ──────────────────────────────────────────────────────────
    await db["edit_history"].create_indexes(
        [
            IndexModel([("project_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("operation_type", ASCENDING)]),
            # version timeline (Original → Edit 1 → Edit 2 …)
            # NOTE: not unique — repair/optimization records keep version 0
            IndexModel([("project_id", ASCENDING), ("version", ASCENDING)]),
        ]
    )
    logger.debug("Indexes ensured: edit_history")

    logger.info("All MongoDB indexes verified.")
