"""Generation job orchestration service (API-facing side)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Optional

from bson import ObjectId

from app.core.object_id import to_object_id
from app.exceptions import JobStateError, NotFoundError, ValidationError
from app.models.enums import JobStage, JobStatus
from app.repositories.job_repo import JobRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.upload_repo import UploadRepository
from app.repositories.usage_repo import UsageRepository
from app.repositories.user_repo import UserRepository
from app.schemas.common import normalize_doc
from app.schemas.job import GenerationSettings

logger = logging.getLogger(__name__)


class JobService:
    def __init__(
        self,
        jobs: JobRepository,
        projects: ProjectRepository,
        uploads: UploadRepository,
        users: UserRepository,
        usage: UsageRepository,
    ) -> None:
        self.jobs = jobs
        self.projects = projects
        self.uploads = uploads
        self.users = users
        self.usage = usage

    async def create_generation(
        self,
        user_id: str,
        project_id: str,
        upload_id: str,
        settings: GenerationSettings,
        ai_model: str = "auto",
    ) -> dict:
        project = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if project is None:
            raise NotFoundError("Project not found")
        upload = await self.uploads.owned_by(to_object_id(upload_id), to_object_id(user_id))
        if upload is None:
            raise ValidationError("Upload not found or not owned by user")

        if ai_model == "auto":
            from app.config import get_settings

            ai_model = get_settings().AI_MODEL

        doc = {
            "user_id": ObjectId(user_id),
            "project_id": ObjectId(project_id),
            "upload_id": ObjectId(upload_id),
            "status": JobStatus.QUEUED.value,
            "stage": JobStage.UPLOADED.value,
            "progress": 0.0,
            "message": "Queued for generation",
            "error": None,
            "ai_model": ai_model,
            "settings": settings.model_dump(),
            "model_asset_id": None,
            "metrics": {},
            "retry_count": 0,
            "worker_id": None,
        }
        doc["created_at"] = datetime.now(UTC)
        doc["started_at"] = None
        doc["completed_at"] = None
        inserted = await self.jobs.insert_one(doc)

        await self.projects.update_by_id(
            to_object_id(project_id),
            {
                "status": "processing",
                "image_upload_id": ObjectId(upload_id),
                "last_job_id": inserted["_id"],
            },
        )
        logger.info("Created generation job %s for project %s", inserted["_id"], project_id)
        return normalize_doc(inserted)

    async def list_for_user(self, user_id: str, status: Optional[str], page: int, page_size: int):
        total, docs = await self.jobs.list_for_user(to_object_id(user_id), status, page, page_size)
        return total, [normalize_doc(d) for d in docs]

    async def get_owned(self, user_id: str, job_id: str) -> dict:
        doc = await self.jobs.find_by_id(to_object_id(job_id))
        if doc is None or str(doc.get("user_id", "")) != user_id:
            raise NotFoundError("Job not found")
        return normalize_doc(doc)

    async def retry(self, user_id: str, job_id: str, settings: Optional[GenerationSettings], use_same_upload: bool = True) -> dict:
        job = await self.get_owned(user_id, job_id)
        if use_same_upload and not job.get("upload_id"):
            raise ValidationError("Original upload is unavailable for retry")

        new_settings = settings or GenerationSettings(**job.get("settings", {}))
        return await self.create_generation(
            user_id,
            job["project_id"],
            job["upload_id"],
            new_settings,
            ai_model="auto",
        )

    async def cancel(self, user_id: str, job_id: str) -> dict:
        job = await self.get_owned(user_id, job_id)
        if job["status"] in (JobStatus.SUCCEEDED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value):
            raise JobStateError("Cannot cancel a job that already finished")
        await self.jobs.cancel(to_object_id(job_id))
        await self.projects.set_status(to_object_id(job["project_id"]), "no_model")
        return await self.get_owned(user_id, job_id)
