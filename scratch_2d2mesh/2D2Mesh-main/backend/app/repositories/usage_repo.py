"""Usage statistics repository."""
from __future__ import annotations

from datetime import UTC
from typing import Dict, List

from bson import ObjectId

from app.core.object_id import PyObjectId
from app.models.usage_record import UsageRecordDocument
from app.repositories.base import BaseRepository


class UsageRepository(BaseRepository):
    collection_name = "usage_records"

    async def user_summary(self, user_id: ObjectId) -> Dict[str, object]:
        totals = await self.aggregate(
            [
                {"$match": {"user_id": user_id}},
                {
                    "$group": {
                        "_id": None,
                        "uploads": {"$sum": {"$cond": [{"$eq": ["$kind", "upload"]}, 1, 0]}},
                        "generations": {"$sum": {"$cond": [{"$eq": ["$kind", "generation"]}, 1, 0]}},
                        "completed_generations": {
                            "$sum": {"$cond": [{"$eq": ["$kind", "generation"]}, 1, 0]}
                        },
                        "failed_generations": {
                            "$sum": {"$cond": [{"$eq": ["$kind", "generation_failed"]}, 1, 0]}
                        },
                        "downloads": {"$sum": {"$cond": [{"$eq": ["$kind", "download"]}, 1, 0]}},
                        "upload_bytes": {
                            "$sum": {"$cond": [{"$eq": ["$kind", "upload"]}, "$payload_bytes", 0]}
                        },
                        "model_bytes": {
                            "$sum": {"$cond": [{"$eq": ["$kind", "generation"]}, "$payload_bytes", 0]}
                        },
                    },
                },
            ]
        )
        base = {
            "uploads": 0,
            "generations": 0,
            "completed_generations": 0,
            "failed_generations": 0,
            "downloads": 0,
            "upload_bytes": 0,
            "model_bytes": 0,
        }
        if totals:
            base.update(
                {
                    "uploads": totals[0]["uploads"],
                    "generations": totals[0]["generations"],
                    "completed_generations": totals[0]["completed_generations"],
                    "failed_generations": totals[0]["failed_generations"],
                    "downloads": totals[0]["downloads"],
                    "upload_bytes": totals[0]["upload_bytes"],
                    "model_bytes": totals[0]["model_bytes"],
                }
            )

        by_day = await self.aggregate(
            [
                {"$match": {"user_id": user_id}},
                {
                    "$group": {
                        "_id": {
                            "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                            "kind": "$kind",
                        },
                        "count": {"$sum": 1},
                        "bytes": {"$sum": "$payload_bytes"},
                    }
                },
                {"$sort": {"_id.date": 1}},
            ]
        )
        daily = [
            {"date": row["_id"]["date"], "kind": row["_id"]["kind"], "count": row["count"], "bytes": row["bytes"]}
            for row in by_day
        ]
        return {**base, "by_day": daily}

    async def record(self, user_id: ObjectId, kind: str, payload_bytes: int = 0, **meta) -> None:
        record = UsageRecordDocument(
            user_id=PyObjectId(str(user_id)),
            kind=kind,
            payload_bytes=payload_bytes,
            project_id=PyObjectId(str(meta["project_id"])) if meta.get("project_id") else None,
            job_id=PyObjectId(str(meta["job_id"])) if meta.get("job_id") else None,
            ai_model=meta.get("ai_model"),
        )
        await self.insert_one(record.model_dump(by_alias=True))

    async def total_storage_bytes(self) -> int:
        rows = await self.aggregate([{"$group": {"_id": None, "bytes": {"$sum": "$payload_bytes"}}}])
        return int(rows[0]["bytes"]) if rows else 0

    async def recent_activity_user_ids(self, hours: int = 24) -> List[ObjectId]:
        from datetime import datetime, timedelta

        since = datetime.now(UTC) - timedelta(hours=hours)
        rows = await self.aggregate(
            [
                {"$match": {"created_at": {"$gte": since}}},
                {"$group": {"_id": "$user_id"}},
            ]
        )
        return [row["_id"] for row in rows]
