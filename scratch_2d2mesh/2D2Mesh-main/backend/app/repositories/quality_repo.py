"""Quality report repository."""
from __future__ import annotations

from typing import List, Optional

from bson import ObjectId

from app.repositories.base import BaseRepository


class QualityReportRepository(BaseRepository):
    collection_name = "quality_reports"

    async def find_latest_for_asset(self, model_asset_id: ObjectId) -> Optional[dict]:
        """Return the most recent quality report for a given model asset."""
        docs = await self.find_many(
            {"model_asset_id": model_asset_id},
            sort=[("created_at", -1)],
            limit=1,
        )
        return docs[0] if docs else None

    async def find_latest_for_project(self, project_id: ObjectId) -> Optional[dict]:
        """Return the most recent quality report for a given project."""
        docs = await self.find_many(
            {"project_id": project_id},
            sort=[("created_at", -1)],
            limit=1,
        )
        return docs[0] if docs else None

    async def list_for_project(self, project_id: ObjectId, limit: int = 10) -> List[dict]:
        return await self.find_many(
            {"project_id": project_id},
            sort=[("created_at", -1)],
            limit=limit,
        )

    async def count_for_user(self, user_id: ObjectId) -> int:
        return await self.count({"user_id": user_id})
