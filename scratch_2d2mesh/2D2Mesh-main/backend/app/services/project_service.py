"""Project lifecycle service with ownership enforcement."""
from __future__ import annotations

import logging
from datetime import UTC
from typing import Optional, Tuple

from app.core.object_id import to_object_id
from app.exceptions import NotFoundError, ValidationError
from app.repositories.job_repo import JobRepository
from app.repositories.model_repo import ModelAssetRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.upload_repo import UploadRepository
from app.repositories.user_repo import UserRepository
from app.schemas.common import normalize_doc
from app.services.storage_service import StorageBackend, get_storage

logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(
        self,
        projects: ProjectRepository,
        users: UserRepository,
        uploads: UploadRepository,
        models: ModelAssetRepository,
        jobs: JobRepository,
        storage: Optional[StorageBackend] = None,
    ) -> None:
        self.projects = projects
        self.users = users
        self.uploads = uploads
        self.models = models
        self.jobs = jobs
        self.storage = storage or get_storage()

    async def create(self, user_id: str, name: str, description: Optional[str]) -> dict:
        oid = to_object_id(user_id)
        doc = {
            "user_id": oid,
            "name": name.strip(),
            "description": (description or "").strip() or None,
            "status": "no_model",
            "image_upload_id": None,
            "model_asset_id": None,
            "last_job_id": None,
            "edit_version": 0,
        }
        from datetime import datetime

        doc["created_at"] = datetime.now(UTC)
        doc["updated_at"] = datetime.now(UTC)
        inserted = await self.projects.insert_one(doc)
        await self.users.increment_metrics(oid, projects_created=1)
        return normalize_doc(inserted)

    async def list_for_user(
        self,
        user_id: str,
        query: Optional[str],
        status: Optional[str],
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
    ) -> Tuple[int, list]:
        total, docs = await self.projects.list_for_user(
            to_object_id(user_id), query, status, page, page_size, sort_by, sort_dir
        )
        return total, [normalize_doc(d) for d in docs]

    async def get_owned(self, user_id: str, project_id: str) -> dict:
        doc = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if doc is None:
            raise NotFoundError("Project not found")
        return normalize_doc(doc)

    async def get_model_asset(self, user_id: str, project_id: str) -> dict:
        project = await self.get_owned(user_id, project_id)
        if not project.get("model_asset_id"):
            raise NotFoundError("This project has no generated model yet")
        asset = await self.models.find_by_id(to_object_id(project["model_asset_id"]))
        if asset is None:
            raise NotFoundError("Model asset is missing from storage")
        return normalize_doc(asset)

    async def get_model_asset_by_id(self, user_id: str, model_id: str) -> dict:
        """Fetch a model asset directly by its id, enforcing ownership."""
        asset = await self.models.find_by_id(to_object_id(model_id))
        if asset is None or str(asset.get("user_id", "")) != user_id:
            raise NotFoundError("Model not found")
        return normalize_doc(asset)

    async def get_model_metadata(self, user_id: str, model_id: str) -> dict:
        asset = await self.get_model_asset_by_id(user_id, model_id)

        project_id = str(asset["project_id"])
        project = await self.projects.owned_by(
            to_object_id(project_id), to_object_id(user_id)
        )
        thumbnail_url = None
        if project is not None and project.get("image_upload_id"):
            upload = await self.uploads.find_by_id(to_object_id(project["image_upload_id"]))
            if upload is not None and str(upload.get("user_id", "")) == user_id:
                thumbnail_url = self.storage.public_url(upload["storage_key"])

        return {
            "id": model_id,
            "project_id": project_id,
            "job_id": str(asset["job_id"]) if asset.get("job_id") else None,
            "filename": asset.get("filename", "model.glb"),
            "size_bytes": asset.get("size_bytes", 0),
            "mime_type": asset.get("mime_type", "model/gltf-binary"),
            "provider": str(asset.get("provider", "local")),
            "stats": asset.get("stats"),
            "created_at": asset.get("created_at"),
            "model_url": self.storage.public_url(asset["glb_key"]),
            "obj_url": self.storage.public_url(asset["obj_key"]) if asset.get("obj_key") else None,
            "preview_url": (
                self.storage.public_url(asset["preview_key"]) if asset.get("preview_key") else None
            ),
            "thumbnail_url": thumbnail_url,
        }

    async def get_detail(self, user_id: str, project_id: str) -> dict:
        project = await self.get_owned(user_id, project_id)
        detail = dict(project)

        if project.get("image_upload_id"):
            up = await self.uploads.find_by_id(to_object_id(project["image_upload_id"]))
            if up is not None and str(up.get("user_id", "")) == user_id:
                detail["image_url"] = self.storage.public_url(up["storage_key"])

        if project.get("model_asset_id"):
            asset = await self.models.find_by_id(to_object_id(project["model_asset_id"]))
            if asset is not None:
                detail["model_summary"] = {
                    "filename": asset.get("filename", "model.glb"),
                    "size_bytes": asset.get("size_bytes", 0),
                    "mime_type": asset.get("mime_type", "model/gltf-binary"),
                    "stats": asset.get("stats"),
                    "created_at": asset.get("created_at"),
                    "download_glb_url": self.storage.public_url(asset["glb_key"]),
                    "download_gltf_url": (
                        self.storage.public_url(asset["gltf_key"]) if asset.get("gltf_key") else None
                    ),
                    "download_obj_url": (
                        self.storage.public_url(asset["obj_key"]) if asset.get("obj_key") else None
                    ),
                    "preview_url": (
                        self.storage.public_url(asset["preview_key"])
                        if asset.get("preview_key")
                        else None
                    ),
                }

        if project.get("last_job_id"):
            job = await self.jobs.find_by_id(to_object_id(project["last_job_id"]))
            if job is not None:
                detail["last_job"] = normalize_doc(job)

        return detail

    async def rename(self, user_id: str, project_id: str, name: str) -> dict:
        await self.get_owned(user_id, project_id)
        name = name.strip()
        if not name:
            raise ValidationError("Project name cannot be empty")
        await self.projects.update_by_id(to_object_id(project_id), {"name": name})
        return await self.get_owned(user_id, project_id)

    async def update(self, user_id: str, project_id: str, **fields) -> dict:
        await self.get_owned(user_id, project_id)
        updates = {}
        if "name" in fields and fields["name"]:
            updates["name"] = fields["name"].strip()
        if "description" in fields:
            updates["description"] = fields["description"]
        if updates:
            await self.projects.update_by_id(to_object_id(project_id), updates)
        return await self.get_owned(user_id, project_id)

    async def delete(self, user_id: str, project_id: str) -> None:
        project = await self.get_owned(user_id, project_id)
        await self._delete_project_data(project, user_id, project_id)

    async def delete_all_for_user(self, user_id: str) -> None:
        """Delete every project belonging to a user (used on account deletion)."""
        uid = to_object_id(user_id)
        project_docs = await self.projects.find_many({"user_id": uid})
        for project in project_docs:
            await self._delete_project_data(
                project, user_id, str(project["_id"])
            )
        await self.uploads.delete_many({"user_id": uid})
        await self.jobs.delete_many({"user_id": uid})
        await self.models.delete_many({"user_id": uid})
        logger.info("Deleted all data for user %s", user_id)

    async def _delete_project_data(self, project: dict, user_id: str, project_id: str) -> None:
        pid = to_object_id(project_id)
        uid = to_object_id(user_id)

        model_docs = await self.models.find_many({"project_id": pid})
        job_docs = await self.jobs.find_many({"project_id": pid})
        upload_ids = {to_object_id(project["image_upload_id"])} if project.get("image_upload_id") else set()
        upload_ids.update(job.get("upload_id") for job in job_docs if job.get("upload_id"))

        # Clean storage
        for model in model_docs:
            for key in ("glb_key", "gltf_key", "obj_key", "preview_key", "thumbnail_key"):
                if model.get(key):
                    await self.storage.delete(model[key])
        for uid_item in set(upload_ids):
            up = await self.uploads.find_by_id(uid_item)
            if up and up.get("user_id") == uid:
                await self.storage.delete(up["storage_key"])

        await self.models.delete_many({"project_id": pid})
        await self.jobs.delete_many({"project_id": pid})
        if upload_ids:
            await self.uploads.collection.delete_many({"_id": {"$in": list(upload_ids)}})
        await self.projects.delete_by_id(pid)
        logger.info("Deleted project %s for user %s", project_id, user_id)
