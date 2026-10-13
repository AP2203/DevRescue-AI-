"""User profile and statistics service."""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from app.core.object_id import to_object_id
from app.exceptions import ConflictError, NotFoundError
from app.repositories.usage_repo import UsageRepository
from app.repositories.user_repo import UserRepository
from app.schemas.common import normalize_doc

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, users: UserRepository, usage: UsageRepository) -> None:
        self.users = users
        self.usage = usage

    async def get_public(self, user_id: str) -> dict:
        doc = await self.users.find_by_id(to_object_id(user_id))
        if doc is None:
            raise NotFoundError("User not found")
        return normalize_doc(doc)

    async def update_profile(self, user_id: str, **fields) -> dict:
        oid = to_object_id(user_id)
        updates = {}
        if "username" in fields and fields["username"]:
            existing = await self.users.find_by_username(fields["username"])
            if existing is not None and str(existing["_id"]) != user_id:
                raise ConflictError("This username is already taken")
            updates["username"] = fields["username"]
        if "avatar_url" in fields:
            updates["avatar_url"] = fields["avatar_url"] or None
        if "preferences" in fields and fields["preferences"] is not None:
            prefs = fields["preferences"]
            updates["preferences"] = prefs if isinstance(prefs, dict) else prefs.model_dump()
        if updates:
            await self.users.update_by_id(oid, updates)
        return await self.get_public(user_id)

    async def get_statistics(self, user_id: str) -> dict:
        oid = to_object_id(user_id)
        doc = await self.users.find_by_id(oid)
        if doc is None:
            raise NotFoundError("User not found")
        summary = await self.usage.user_summary(oid)
        return {
            "usage": {
                "uploads": summary["uploads"],
                "generations": summary["generations"],
                "completed_generations": summary.get("completed_generations", 0),
                "failed_generations": summary.get("failed_generations", 0),
                "downloads": summary["downloads"],
                "total_upload_bytes": summary["upload_bytes"],
                "total_model_bytes": summary["model_bytes"],
                "by_day": summary["by_day"],
            },
            "metrics": doc.get("metrics", {}),
        }

    # ---- admin ----
    async def list_users(self, query: Optional[str], page: int, page_size: int) -> Tuple[int, list]:
        return await self.users.search(query, page, page_size)

    async def set_role(self, user_id: str, role: str) -> dict:
        await self.users.update_by_id(to_object_id(user_id), {"role": role})
        return await self.get_public(user_id)

    async def set_active(self, user_id: str, active: bool) -> dict:
        await self.users.update_by_id(to_object_id(user_id), {"is_active": active})
        return await self.get_public(user_id)
