"""Repair service.

Orchestrates:
1. Load GLB from storage
2. Run deterministic mesh repair
3. Save repaired GLB as a new model asset
4. Update project's model reference to point to repaired asset
5. Run before/after quality analysis and scores
6. Persist repaired quality report
7. Record edit history with comparison metrics
8. Record usage event
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from app.ai.mesh_repair import repair_glb
from app.ai.quality_analyzer import analyze_glb
from app.core.object_id import PyObjectId, to_object_id
from app.exceptions import NotFoundError
from app.models.edit_history import EditHistoryDocument
from app.models.model_asset import ModelAssetDocument
from app.models.quality_report import DimensionScore, QualityProblem, QualityReportDocument
from app.repositories.edit_history_repo import EditHistoryRepository
from app.repositories.model_repo import ModelAssetRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.quality_repo import QualityReportRepository
from app.repositories.usage_repo import UsageRepository
from app.schemas.common import normalize_doc
from app.services.storage_service import StorageBackend

logger = logging.getLogger(__name__)


class RepairService:
    def __init__(
        self,
        projects: ProjectRepository,
        models: ModelAssetRepository,
        edit_history: EditHistoryRepository,
        usage: UsageRepository,
        storage: StorageBackend,
        quality: QualityReportRepository,
    ) -> None:
        self.projects = projects
        self.models = models
        self.edit_history = edit_history
        self.usage = usage
        self.storage = storage
        self.quality = quality

    async def repair_project(
        self,
        user_id: str,
        project_id: str,
        fill_holes: bool = True,
        fix_normals: bool = True,
        remove_duplicates: bool = True,
        remove_degenerate: bool = True,
    ) -> dict:
        """Load project GLB, repair it, save new asset, record history with quality metrics."""
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
            raise NotFoundError("GLB file missing from storage")

        # Run quality analysis before repair
        before_analysis = analyze_glb(glb_bytes)
        before_score = before_analysis.overall_score
        before_problems = [
            QualityProblem(
                severity=p.severity,
                code=p.code,
                message=p.message,
                value=p.value,
            )
            for p in before_analysis.problems
        ]

        # Run repair
        result = repair_glb(
            glb_bytes,
            fill_holes=fill_holes,
            fix_normals=fix_normals,
            remove_duplicates=remove_duplicates,
            remove_degenerate=remove_degenerate,
            fix_non_manifold=True,
            remove_disconnected=True,
            reduce_geometry=True,
            fix_textures=True,
        )

        # Run quality analysis after repair
        after_analysis = analyze_glb(result.repaired_glb_bytes)
        after_score = after_analysis.overall_score
        after_problems = [
            QualityProblem(
                severity=p.severity,
                code=p.code,
                message=p.message,
                value=p.value,
            )
            for p in after_analysis.problems
        ]

        # Save repaired GLB
        uid = uuid.uuid4().hex[:8]
        repaired_key = f"models/{user_id}/{project_id}/{uid}/repaired.glb"
        await self.storage.save(repaired_key, result.repaired_glb_bytes, "model/gltf-binary")

        # Create new model asset record (repaired variant)
        repaired_asset = ModelAssetDocument(
            user_id=PyObjectId(str(to_object_id(user_id))),
            project_id=PyObjectId(str(to_object_id(project_id))),
            job_id=PyObjectId(str(asset["job_id"])),
            glb_key=repaired_key,
            gltf_key=None,
            obj_key=None,
            preview_key=None,
            filename="repaired.glb",
            size_bytes=len(result.repaired_glb_bytes),
            mime_type="model/gltf-binary",
            stats={
                "repaired": True,
                "operations": result.operations_applied,
                **result.after_stats,
            },
        )
        inserted_asset = await self.models.insert_one(repaired_asset.model_dump(by_alias=True))

        # Update the project's model reference to the repaired asset
        await self.projects.update_by_id(to_object_id(project_id), {"model_asset_id": inserted_asset["_id"]})

        # Save the new quality report document for the repaired asset
        after_report_doc = QualityReportDocument(
            project_id=to_object_id(project_id),
            user_id=to_object_id(user_id),
            model_asset_id=inserted_asset["_id"],
            overall_score=after_score,
            dimensions=[
                DimensionScore(
                    name=d.name,
                    score=d.score,
                    weight=d.weight,
                    details=d.details,
                )
                for d in after_analysis.dimensions
            ],
            problems=after_problems,
            recommendations=after_analysis.recommendations,
            stats_snapshot=after_analysis.stats_snapshot,
        )
        await self.quality.insert_one(after_report_doc.model_dump(by_alias=True))

        # Calculate which problems were fixed
        before_codes = {p.code for p in before_problems}
        after_codes = {p.code for p in after_problems}
        fixed_codes = before_codes - after_codes

        problems_found = [p.model_dump(by_alias=True) for p in before_problems]
        problems_fixed = []
        for p in before_problems:
            if p.code in fixed_codes:
                problems_fixed.append(p.message)

        # Record edit history
        history_doc = EditHistoryDocument(
            project_id=PyObjectId(str(to_object_id(project_id))),
            user_id=PyObjectId(str(to_object_id(user_id))),
            operation_type="repair",
            original_asset_id=PyObjectId(str(original_asset_id)),
            result_asset_id=PyObjectId(str(inserted_asset["_id"])),
            before_stats=result.before_stats,
            after_stats=result.after_stats,
            meta={
                "operations": result.operations_applied,
                "before_score": before_score,
                "after_score": after_score,
                "problems_found": [p.code for p in before_problems],
                "problems_fixed": list(fixed_codes),
            },
        )
        await self.edit_history.insert_one(history_doc.model_dump(by_alias=True))

        # Record usage
        await self.usage.record(
            to_object_id(user_id),
            "repair",
            payload_bytes=len(result.repaired_glb_bytes),
            project_id=project_id,
        )

        logger.info(
            "Repair completed for project %s: %d->%d faces (score: %.1f->%.1f)",
            project_id,
            result.before_stats.get("faces", 0),
            result.after_stats.get("faces", 0),
            before_score,
            after_score,
        )

        return {
            "asset_id": str(inserted_asset["_id"]),
            "before_stats": result.before_stats,
            "after_stats": result.after_stats,
            "operations_applied": result.operations_applied,
            "download_url": self.storage.public_url(repaired_key),
            "before_score": before_score,
            "after_score": after_score,
            "problems_found": problems_found,
            "problems_fixed": problems_fixed,
        }
