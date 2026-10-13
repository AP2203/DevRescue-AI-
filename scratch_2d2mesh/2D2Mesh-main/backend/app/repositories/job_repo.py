"""Generation job repository with atomic worker claiming."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from app.models.enums import JobStatus
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository):
    collection_name = "jobs"

    async def list_for_user(
        self,
        user_id: ObjectId,
        status: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[int, List[dict]]:
        query: Dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status
        total = await self.count(query)
        items = await self.find_many(
            query,
            sort=[("created_at", -1)],
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        return total, items

    async def claim_next(self, worker_id: str, stale_minutes: int) -> Optional[dict]:
        stale_before = datetime.now(UTC) - timedelta(minutes=stale_minutes)
        query = {
            "$or": [
                {"status": JobStatus.QUEUED.value},
                {
                    "status": JobStatus.PROCESSING.value,
                    "started_at": {"$lt": stale_before},
                },
            ]
        }
        update = {
            "$set": {
                "status": JobStatus.PROCESSING.value,
                "worker_id": worker_id,
                "started_at": datetime.now(UTC),
            }
        }
        return await self.collection.find_one_and_update(query, update, return_document=True)

    async def set_progress(self, job_id: ObjectId, progress: float, stage: str, message: str) -> None:
        from app.models.enums import JobStage

        stage_value = None
        if stage:
            try:
                stage_value = JobStage(stage)
            except ValueError:
                stage_value = None
        await self.collection.update_one(
            {"_id": job_id},
            {"$set": {"progress": max(0.0, min(100.0, progress)), "stage": stage_value.value if stage_value else None, "message": message}},
        )

    async def mark_succeeded(
        self,
        job_id: ObjectId,
        model_asset_id: ObjectId,
        metrics: Dict[str, Any],
    ) -> None:
        await self.collection.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.SUCCEEDED.value,
                    "progress": 100.0,
                    "stage": "complete",
                    "model_asset_id": model_asset_id,
                    "metrics": metrics,
                    "completed_at": datetime.now(UTC),
                    "error": None,
                }
            },
        )

    async def mark_failed(self, job_id: ObjectId, error: str) -> None:
        await self.collection.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.FAILED.value,
                    "error": error[:2000],
                    "completed_at": datetime.now(UTC),
                }
            },
        )

    async def increment_retry(self, job_id: ObjectId) -> int:
        doc = await self.collection.find_one_and_update(
            {"_id": job_id},
            {"$inc": {"retry_count": 1}},
            return_document=True,
        )
        return int(doc["retry_count"]) if doc else 0

    async def cancel(self, job_id: ObjectId) -> Optional[dict]:
        return await self.update_by_id(job_id, {"status": JobStatus.CANCELLED.value, "completed_at": datetime.now(UTC)})

    async def status_counts(self) -> List[dict]:
        return await self.aggregate(
            [{"$group": {"_id": "$status", "count": {"$sum": 1}}}, {"$project": {"status": "$_id", "count": 1, "_id": 0}}]
        )
