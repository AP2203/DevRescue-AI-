"""Edit history repository."""
from __future__ import annotations

from typing import List, Optional

from bson import ObjectId

from app.repositories.base import BaseRepository


class EditHistoryRepository(BaseRepository):
    collection_name = "edit_history"

    async def list_for_project(self, project_id: ObjectId, limit: int = 50) -> List[dict]:
        return await self.find_many(
            {"project_id": project_id},
            sort=[("created_at", -1)],
            limit=limit,
        )

    async def list_for_project_asc(self, project_id: ObjectId, limit: int = 100) -> List[dict]:
        """Return edit history for a project, oldest first (Original → latest)."""
        return await self.find_many(
            {"project_id": project_id},
            sort=[("version", 1), ("created_at", 1)],
            limit=limit,
        )

    async def list_for_user(self, user_id: ObjectId, limit: int = 20) -> List[dict]:
        return await self.find_many(
            {"user_id": user_id},
            sort=[("created_at", -1)],
            limit=limit,
        )

    async def count_by_type_for_user(self, user_id: ObjectId, operation_type: str) -> int:
        return await self.count({"user_id": user_id, "operation_type": operation_type})

    async def recent_by_type(self, user_id: ObjectId, operation_type: Optional[str] = None, limit: int = 10) -> List[dict]:
        query: dict = {"user_id": user_id}
        if operation_type:
            query["operation_type"] = operation_type
        return await self.find_many(query, sort=[("created_at", -1)], limit=limit)

    # ── Versioning (undo / redo) ──────────────────────────────────────────────

    async def get_by_version(self, project_id: ObjectId, version: int) -> Optional[dict]:
        return await self.find_one({"project_id": project_id, "version": version})

    async def max_version(self, project_id: ObjectId) -> int:
        """Highest recorded edit version for a project (0 when none exist)."""
        rows = await self.aggregate([
            {"$match": {"project_id": project_id}},
            {"$group": {"_id": None, "max": {"$max": "$version"}}},
        ])
        return int(rows[0]["max"]) if rows and rows[0].get("max") is not None else 0

    async def delete_versions_after(self, project_id: ObjectId, version: int) -> int:
        """Remove redo history: entries with version > `version`."""
        result = await self.collection.delete_many(
            {"project_id": project_id, "version": {"$gt": version}}
        )
        return result.deleted_count
