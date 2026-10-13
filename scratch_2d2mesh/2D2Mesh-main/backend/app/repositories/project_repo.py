"""Project repository with search/filter support."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    collection_name = "projects"

    def _build_query(self, user_id: ObjectId, query: Optional[str], status: Optional[str]) -> Dict[str, Any]:
        filter_query: Dict[str, Any] = {"user_id": user_id}
        if status == "ready":
            filter_query["status"] = "ready"
        elif status == "processing":
            filter_query["status"] = {"$in": ["processing", "queued"]}
        elif status == "failed":
            filter_query["status"] = "failed"
        elif status == "no_model":
            filter_query["status"] = "no_model"
        if query:
            regex = re.compile(re.escape(query), re.IGNORECASE)
            filter_query["$and"] = [
                {"$or": [{"name": regex}, {"description": regex}]}
            ]
        return filter_query

    async def list_for_user(
        self,
        user_id: ObjectId,
        query: Optional[str],
        status: Optional[str],
        page: int,
        page_size: int,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> Tuple[int, List[dict]]:
        filter_query = self._build_query(user_id, query, status)
        total = await self.count(filter_query)
        direction = 1 if sort_dir == "asc" else -1
        sort_key = sort_by if sort_by in ("created_at", "updated_at", "name") else "created_at"
        items = await self.find_many(
            filter_query,
            sort=[(sort_key, direction)],
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        return total, items

    async def owned_by(self, project_id: ObjectId | str, user_id: ObjectId) -> Optional[dict]:
        return await self.collection.find_one({"_id": ObjectId(project_id) if not isinstance(project_id, ObjectId) else project_id, "user_id": user_id})

    async def set_status(self, project_id: ObjectId, status: str) -> None:
        await self.update_by_id(project_id, {"status": status})

    async def set_status_where_job(self, job_id: ObjectId, status: str) -> None:
        await self.collection.update_many({"last_job_id": job_id}, {"$set": {"status": status}})
