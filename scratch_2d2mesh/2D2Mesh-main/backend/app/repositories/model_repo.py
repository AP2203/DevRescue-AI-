"""Model asset repository."""
from __future__ import annotations

from bson import ObjectId

from app.repositories.base import BaseRepository


class ModelAssetRepository(BaseRepository):
    collection_name = "models"

    async def owned_by(self, model_id: ObjectId | str, user_id: ObjectId) -> dict | None:
        return await self.collection.find_one(
            {"_id": ObjectId(model_id) if not isinstance(model_id, ObjectId) else model_id, "user_id": user_id}
        )
