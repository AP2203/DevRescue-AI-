"""Usage statistics recording service."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from bson import ObjectId

from app.repositories.usage_repo import UsageRepository

logger = logging.getLogger(__name__)


class UsageService:
    def __init__(self, usage: UsageRepository) -> None:
        self.usage = usage

    async def record(
        self,
        user_id: str,
        kind: str,
        payload_bytes: int = 0,
        *,
        ai_model: Optional[str] = None,
        project_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> None:
        meta = {}
        if ai_model:
            meta["ai_model"] = ai_model
        if project_id:
            meta["project_id"] = project_id
        if job_id:
            meta["job_id"] = job_id
        await self.usage.record(ObjectId(user_id), kind, payload_bytes, **meta)

    async def summary_for(self, user_id: str) -> Dict[str, Any]:
        return await self.usage.user_summary(ObjectId(user_id))
