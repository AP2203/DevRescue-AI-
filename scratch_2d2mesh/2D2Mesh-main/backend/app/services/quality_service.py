"""Quality analysis service.

Orchestrates the full quality analysis workflow:
1. Load GLB bytes from storage
2. Run the deterministic quality analyzer
3. Persist the report to ``quality_reports`` collection
4. Record usage event
"""

from __future__ import annotations

import logging

from app.ai.quality_analyzer import analyze_glb
from app.core.object_id import to_object_id
from app.exceptions import NotFoundError
from app.models.quality_report import DimensionScore, QualityProblem, QualityReportDocument
from app.repositories.model_repo import ModelAssetRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.quality_repo import QualityReportRepository
from app.repositories.usage_repo import UsageRepository
from app.schemas.common import normalize_doc
from app.services.storage_service import StorageBackend

logger = logging.getLogger(__name__)


class QualityService:
    def __init__(
        self,
        projects: ProjectRepository,
        models: ModelAssetRepository,
        quality: QualityReportRepository,
        usage: UsageRepository,
        storage: StorageBackend,
    ) -> None:
        self.projects = projects
        self.models = models
        self.quality = quality
        self.usage = usage
        self.storage = storage

    async def analyze_project(self, user_id: str, project_id: str) -> dict:
        """Run quality analysis on the current model asset of a project."""
        project = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if project is None:
            raise NotFoundError("Project not found")
        if not project.get("model_asset_id"):
            raise NotFoundError("This project has no generated model yet")

        asset = await self.models.find_by_id(to_object_id(project["model_asset_id"]))
        if asset is None:
            raise NotFoundError("Model asset missing from storage")

        # Load GLB bytes
        glb_bytes = await self.storage.load(asset["glb_key"])
        if not glb_bytes:
            raise NotFoundError("GLB file missing from storage")

        # Run analysis
        result = analyze_glb(glb_bytes)

        # Build document
        doc = QualityReportDocument(
            project_id=to_object_id(project_id),
            user_id=to_object_id(user_id),
            model_asset_id=to_object_id(project["model_asset_id"]),
            overall_score=result.overall_score,
            dimensions=[
                DimensionScore(
                    name=d.name,
                    score=d.score,
                    weight=d.weight,
                    details=d.details,
                )
                for d in result.dimensions
            ],
            problems=[
                QualityProblem(
                    severity=p.severity,
                    code=p.code,
                    message=p.message,
                    value=p.value,
                )
                for p in result.problems
            ],
            recommendations=result.recommendations,
            stats_snapshot=result.stats_snapshot,
        )

        inserted = await self.quality.insert_one(doc.model_dump(by_alias=True))

        # Record usage
        await self.usage.record(
            to_object_id(user_id),
            "quality_analysis",
            project_id=project_id,
        )

        logger.info(
            "Quality analysis completed for project %s (score=%.1f)", project_id, result.overall_score
        )
        return normalize_doc(inserted)

    async def get_latest_report(self, user_id: str, project_id: str) -> dict:
        """Return the most recent quality report for a project."""
        project = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if project is None:
            raise NotFoundError("Project not found")

        report = await self.quality.find_latest_for_project(to_object_id(project_id))
        if report is None:
            raise NotFoundError("No quality report found — run analysis first")
        return normalize_doc(report)
