"""Session repository.

Manages refresh-token sessions stored in the ``sessions`` collection.
MongoDB's TTL index on ``expires_at`` handles passive expiry automatically.
This repository provides active revocation (immediate hard-delete).
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import List, Optional

from bson import ObjectId

from app.models.session import SessionDocument
from app.core.object_id import PyObjectId
from app.repositories.base import BaseRepository, make_storable


def _hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of a refresh token.

    Never store the raw token — only the hash is persisted.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


class SessionRepository(BaseRepository):
    """Repository for the ``sessions`` collection."""

    collection_name = "sessions"

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def create_session(
        self,
        user_id: PyObjectId,
        raw_token: str,
        expires_at: datetime,
        *,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        """Persist a new session.  The raw token is hashed before storage."""
        doc = SessionDocument(
            user_id=user_id,
            refresh_token_hash=_hash_token(raw_token),
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        raw = make_storable(doc.model_dump(by_alias=True))
        return await self.insert_one(raw)

    async def revoke_session_by_token(self, raw_token: str) -> bool:
        """Immediately delete the session matching this refresh token."""
        token_hash = _hash_token(raw_token)
        result = await self.collection.delete_one({"refresh_token_hash": token_hash})
        return result.deleted_count == 1

    async def revoke_all_for_user(self, user_id: ObjectId) -> int:
        """Delete all sessions for a user (logout everywhere).

        Returns the number of sessions revoked.
        """
        return await self.delete_many({"user_id": user_id})

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def find_valid_session(self, raw_token: str) -> Optional[dict]:
        """Return a session document only if the token matches AND has not expired.

        Note: the TTL index will eventually remove expired docs, but there is a
        ~60-second window where MongoDB hasn't yet deleted them.  This explicit
        ``expires_at`` check closes that gap.
        """
        token_hash = _hash_token(raw_token)
        now = datetime.now(UTC)
        return await self.collection.find_one(
            {
                "refresh_token_hash": token_hash,
                "expires_at": {"$gt": now},
            }
        )

    async def find_all_for_user(self, user_id: ObjectId) -> List[dict]:
        """List all non-expired sessions for a user (useful for 'active sessions' UI)."""
        now = datetime.now(UTC)
        return await self.find_many(
            {"user_id": user_id, "expires_at": {"$gt": now}},
            sort=[("created_at", -1)],
        )

    async def count_active_for_user(self, user_id: ObjectId) -> int:
        """Count unexpired sessions for a user."""
        now = datetime.now(UTC)
        return await self.count({"user_id": user_id, "expires_at": {"$gt": now}})
