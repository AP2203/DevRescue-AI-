"""Optimization service.

Orchestrates model optimization for web, game, and 3D-print profiles.
Saves an optimized model asset and records edit history.
"""
from __future__ import annotations

import logging
import uuid
from typing import Literal

from app.ai.optimizer import OptimizationProfile, optimize_glb
from app.core.object_id import PyObjectId, to_object_id
from app.exceptions import NotFoundError, ValidationError
from app.models.edit_history import EditHistoryDocument
from app.models.model_asset import ModelAssetDocument
from app.repositories.edit_history_repo import EditHistoryRepository
from app.repositories.model_repo import ModelAssetRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.usage_repo import UsageRepository
from app.schemas.common import normalize_doc
from app.services.storage_service import StorageBackend

logger = logging.getLogger(__name__)

VALID_PROFILES = {"web", "game", "print"}


class OptimizationService:
    def __init__(
        self,
        projects: ProjectRepository,
        models: ModelAssetRepository,
        edit_history: EditHistoryRepository,
        usage: UsageRepository,
        storage: StorageBackend,
    ) -> None:
        self.projects = projects
        self.models = models
        self.edit_history = edit_history
        self.usage = usage
        self.storage = storage

    async def optimize_project(
        self, user_id: str, project_id: str, profile: str, set_active: bool = False
    ) -> dict:
        """Optimize a project's model with the given profile."""
        if profile not in VALID_PROFILES:
            raise ValidationError(f"Profile must be one of: {', '.join(VALID_PROFILES)}")

        project = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if project is None:
            raise NotFoundError("Project not found")
        if not project.get("model_asset_id"):
            raise NotFoundError("This project has no generated model yet")

        original_asset_id = to_object_id(project["model_asset_id"])
        asset = await self.models.find_by_id(original_asset_id)
        if asset is None:
            raise NotFoundError("Model asset missing from storage")

        glb_bytes = await self.storage.load(asset["glb_key"])
        if not glb_bytes:
            raise NotFoundError("GLB file not found in storage")

        # Run optimization
        result = optimize_glb(glb_bytes, profile=profile)  # type: ignore[arg-type]

        # Save optimized GLB
        uid = uuid.uuid4().hex[:8]
        opt_key = f"models/{user_id}/{project_id}/{uid}/optimized_{profile}.glb"
        await self.storage.save(opt_key, result.optimized_glb_bytes, "model/gltf-binary")

        # Save STL if print profile
        stl_key = None
        if result.stl_bytes and profile == "print":
            stl_key = f"models/{user_id}/{project_id}/{uid}/model.stl"
            await self.storage.save(stl_key, result.stl_bytes, "model/stl")

        # Create new asset
        opt_asset = ModelAssetDocument(
            user_id=PyObjectId(str(to_object_id(user_id))),
            project_id=PyObjectId(str(to_object_id(project_id))),
            job_id=PyObjectId(str(asset["job_id"])),
            glb_key=opt_key,
            obj_key=None,
            gltf_key=None,
            preview_key=None,
            filename=f"optimized_{profile}.glb",
            size_bytes=len(result.optimized_glb_bytes),
            mime_type="model/gltf-binary",
            stats={
                "optimized": True,
                "profile": profile,
                "operations": result.operations,
                "stl_key": stl_key,
                **result.after_stats,
            },
        )
        inserted_asset = await self.models.insert_one(opt_asset.model_dump(by_alias=True))

        # Update the project's model reference if set_active is requested
        if set_active:
            await self.projects.update_by_id(
                to_object_id(project_id), {"model_asset_id": inserted_asset["_id"]}
            )

        # Record edit history
        history_doc = EditHistoryDocument(
            project_id=PyObjectId(str(to_object_id(project_id))),
            user_id=PyObjectId(str(to_object_id(user_id))),
            operation_type="optimization",
            original_asset_id=PyObjectId(str(original_asset_id)),
            result_asset_id=PyObjectId(str(inserted_asset["_id"])),
            before_stats=result.before_stats,
            after_stats=result.after_stats,
            meta={"profile": profile, "operations": result.operations},
        )
        await self.edit_history.insert_one(history_doc.model_dump(by_alias=True))

        await self.usage.record(
            to_object_id(user_id),
            "optimization",
            payload_bytes=len(result.optimized_glb_bytes),
            project_id=project_id,
        )

        logger.info("Optimization (%s) completed for project %s", profile, project_id)

        response: dict = {
            "asset_id": str(inserted_asset["_id"]),
            "profile": profile,
            "before_stats": result.before_stats,
            "after_stats": result.after_stats,
            "operations": result.operations,
            "download_url": self.storage.public_url(opt_key),
        }
        if stl_key:
            response["stl_download_url"] = self.storage.public_url(stl_key)

        return response
