"""Upload repository."""
from __future__ import annotations

from bson import ObjectId

from app.repositories.base import BaseRepository


class UploadRepository(BaseRepository):
    collection_name = "uploads"

    async def owned_by(self, upload_id: ObjectId | str, user_id: ObjectId) -> dict | None:
        return await self.collection.find_one({"_id": ObjectId(upload_id) if not isinstance(upload_id, ObjectId) else upload_id, "user_id": user_id})
