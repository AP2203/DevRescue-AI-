"""Background job processor.

A long-running async worker that claims queued generation jobs, runs the AI
pipeline off the event loop, persists the resulting GLB/GLTF to storage, and
updates job/project/user state. It uses an atomic find-and-claim on the jobs
collection so it is safe to run multiple worker replicas.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.ai.factory import create_ai_model
from app.ai.types import GenerationSettings, OutputFormat
from app.config import get_settings
from app.core.object_id import PyObjectId, to_object_id
from app.repositories import (
    JobRepository,
    ModelAssetRepository,
    ProjectRepository,
    UploadRepository,
    UsageRepository,
    UserRepository,
)
from app.services.storage_service import StorageBackend

logger = logging.getLogger(__name__)

STORAGE_KIND_MIME = "model/gltf-binary"
GLTF_MIME = "model/gltf+json"


class JobProcessor:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        storage: StorageBackend,
        poll_interval: float = 2.0,
        stale_minutes: int = 30,
        max_retries: int = 3,
        worker_id: Optional[str] = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self.poll_interval = poll_interval
        self.stale_minutes = stale_minutes
        self.max_retries = max_retries
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._stop = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()

        self.jobs = JobRepository(db)
        self.projects = ProjectRepository(db)
        self.uploads = UploadRepository(db)
        self.models = ModelAssetRepository(db)
        self.users = UserRepository(db)
        self.usage = UsageRepository(db)

    def _build_generation_settings(self, job_settings: dict) -> GenerationSettings:
        """Merge engine defaults (from config) with per-job settings."""
        settings = get_settings()
        formats = [f.value for f in OutputFormat]
        if not settings.AI_PREVIEW_RENDER:
            formats = [f for f in formats if f != OutputFormat.PREVIEW.value]
        if not settings.AI_OBJ_EXPORT:
            formats = [f for f in formats if f != OutputFormat.OBJ.value]
        base = {
            "formats": formats,
            "max_polygons": settings.AI_MAX_POLYGONS,
            "validation": settings.AI_VALIDATION,
            "retries": settings.AI_DEFAULT_RETRIES,
        }
        return GenerationSettings(**{**base, **dict(job_settings or {})})

    async def run(self) -> None:
        logger.info("Job processor started (worker=%s)", self.worker_id)
        while not self._stop.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Job processor tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
            except TimeoutError:
                continue

    async def stop(self) -> None:
        self._stop.set()
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Job processor stopped")

    async def _tick(self) -> None:
        job = await self.jobs.claim_next(self.worker_id, self.stale_minutes)
        if job is None:
            return
        task = asyncio.create_task(self._process(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _process(self, job: dict) -> None:
        job_id = to_object_id(job["_id"])
        upload_id = to_object_id(job["upload_id"])
        project_id = to_object_id(job["project_id"])
        user_id = to_object_id(job["user_id"])

        image_path: Optional[Path] = None
        workdir: Optional[tempfile.TemporaryDirectory] = None
        try:
            upload = await self.uploads.find_by_id(upload_id)
            if upload is None:
                raise RuntimeError("Upload record no longer exists")
            data = await self.storage.load(upload["storage_key"])

            workdir = tempfile.TemporaryDirectory(prefix="vision3d-job-")
            image_path = Path(workdir.name) / f"input.{upload['storage_key'].split('.')[-1]}"
            image_path.write_bytes(data)

            gs = self._build_generation_settings(job.get("settings", {}))
            model = create_ai_model(job.get("ai_model", "auto"))

            async def report(progress: float, stage: str, message: str) -> None:
                await self.jobs.set_progress(job_id, progress, stage, message)

            result = await model.generate(image_path, Path(workdir.name) / "out", gs, report)

            uid = uuid.uuid4().hex[:8]
            glb_key = f"models/{user_id}/{project_id}/{uid}/model.glb"
            gltf_key = f"models/{user_id}/{project_id}/{uid}/model.gltf"
            preview_key: Optional[str] = None
            obj_key: Optional[str] = None
            await self.storage.save(glb_key, result.glb_bytes, STORAGE_KIND_MIME)
            if result.gltf_bytes:
                await self.storage.save(gltf_key, result.gltf_bytes, GLTF_MIME)
            if result.preview_bytes:
                preview_key = f"models/{user_id}/{project_id}/{uid}/preview.png"
                await self.storage.save(preview_key, result.preview_bytes, "image/png")
            if result.obj_bytes:
                obj_key = f"models/{user_id}/{project_id}/{uid}/model.obj"
                await self.storage.save(obj_key, result.obj_bytes, "text/plain")

            from app.models.model_asset import ModelAssetDocument

            asset_stats = dict(result.stats)
            if result.timings:
                asset_stats["timings"] = [t.to_dict() for t in result.timings]
            if result.validation:
                asset_stats["validation"] = result.validation
            if result.device:
                asset_stats["device"] = result.device

            asset_doc = ModelAssetDocument(
                user_id=PyObjectId(str(user_id)),
                project_id=PyObjectId(str(project_id)),
                job_id=PyObjectId(str(job_id)),
                glb_key=glb_key,
                gltf_key=gltf_key if result.gltf_bytes else None,
                preview_key=preview_key,
                obj_key=obj_key,
                filename=result.filename,
                size_bytes=len(result.glb_bytes),
                mime_type=STORAGE_KIND_MIME,
                provider=self.storage.provider,  # type: ignore[arg-type]
                stats=asset_stats,
            )
            await self.models.insert_one(asset_doc.model_dump(by_alias=True))

            # Re-check cancellation: a cancel issued while inference was running
            # must win over a stale success. Query the job directly so we see the
            # latest status even if `job` is from an earlier claim.
            current = await self.jobs.find_by_id(job_id)
            if current is not None and current.get("status") == "cancelled":
                logger.info("Job %s was cancelled during processing; discarding result", job_id)
                return

            await self.jobs.mark_succeeded(job_id, to_object_id(asset_doc.id), result.stats)
            await self.projects.update_by_id(
                project_id,
                {"status": "ready", "model_asset_id": to_object_id(asset_doc.id)},
            )
            await self.users.increment_metrics(
                user_id,
                generations_completed=1,
                total_model_size_bytes=len(result.glb_bytes),
            )
            await self.usage.record(
                user_id,
                "generation",
                payload_bytes=len(result.glb_bytes),
                ai_model=model.name,
                project_id=str(project_id),
                job_id=str(job_id),
            )
            logger.info("Job %s completed (%s, %s bytes)", job_id, model.name, len(result.glb_bytes))

            # ── Auto quality analysis ──────────────────────────────────────────
            # Non-blocking: run quality analysis in the background so the report
            # is available immediately when the user opens the project page.
            qa_task = asyncio.create_task(self._run_quality_analysis(
                str(user_id), str(project_id)
            ))
            self._tasks.add(qa_task)
            qa_task.add_done_callback(self._tasks.discard)
        except Exception as exc:
            logger.exception("Job %s failed", job["_id"])
            await self.jobs.mark_failed(job_id, str(exc))
            await self.projects.set_status(project_id, "failed")
            await self.users.increment_metrics(user_id, generations_failed=1)
            await self.usage.record(
                user_id,
                "generation_failed",
                payload_bytes=0,
                ai_model=job.get("ai_model"),
                project_id=str(project_id),
                job_id=str(job_id),
            )
        finally:
            if workdir is not None:
                workdir.cleanup()

    async def _run_quality_analysis(self, user_id: str, project_id: str) -> None:
        """Run quality analysis in background after job completion."""
        try:
            from app.repositories.quality_repo import QualityReportRepository
            from app.services.quality_service import QualityService

            quality_repo = QualityReportRepository(self.db)
            quality_svc = QualityService(
                self.projects, self.models, quality_repo, self.usage, self.storage
            )
            await quality_svc.analyze_project(user_id, project_id)
            logger.info("Auto quality analysis completed for project %s", project_id)
        except Exception as exc:
            logger.warning("Auto quality analysis failed for project %s: %s", project_id, exc)

