"""User repository."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    collection_name = "users"

    async def find_by_email(self, email: str) -> Optional[dict]:
        return await self.collection.find_one({"email": email.lower()})

    async def find_by_username(self, username: str) -> Optional[dict]:
        return await self.collection.find_one({"username": username})

    async def increment_metrics(self, user_id: ObjectId, **deltas: int) -> None:
        operations = {f"metrics.{key}": value for key, value in deltas.items()}
        await self.collection.update_one(
            {"_id": user_id},
            {"$inc": operations, "$set": {"updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)}},
        )

    async def search(
        self,
        query: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[int, List[dict]]:
        filter_query: Dict[str, Any] = {}
        if query:
            import re

            regex = re.compile(re.escape(query), re.IGNORECASE)
            filter_query["$or"] = [{"email": regex}, {"username": regex}]
        total = await self.count(filter_query)
        items = await self.find_many(
            filter_query,
            sort=[("created_at", -1)],
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        return total, items
