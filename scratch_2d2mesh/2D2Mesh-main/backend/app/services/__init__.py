"""Service container: wires repositories and domain services together.

Centralizes the composition root so routes depend on a small set of service
objects instead of individual repositories.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.repositories import (
    EditHistoryRepository,
    JobRepository,
    ModelAssetRepository,
    ProjectRepository,
    QualityReportRepository,
    UploadRepository,
    UsageRepository,
    UserRepository,
)
from app.services.auth_service import AuthService
from app.services.edit_service import EditService
from app.services.job_service import JobService
from app.services.optimization_service import OptimizationService
from app.services.project_service import ProjectService
from app.services.quality_service import QualityService
from app.services.repair_service import RepairService
from app.services.storage_service import StorageBackend, get_storage
from app.services.upload_service import UploadService
from app.services.usage_service import UsageService
from app.services.user_service import UserService


@dataclass
class Services:
    auth: AuthService
    users: UserService
    projects: ProjectService
    jobs: JobService
    uploads: UploadService
    usage: UsageService
    storage: StorageBackend
    # -- New services --
    quality: QualityService
    repair: RepairService
    edit: EditService
    optimization: OptimizationService


def build_services(db: Any) -> Services:
    storage = get_storage()

    user_repo = UserRepository(db)
    usage_repo = UsageRepository(db)
    upload_repo = UploadRepository(db)
    project_repo = ProjectRepository(db)
    job_repo = JobRepository(db)
    model_repo = ModelAssetRepository(db)
    quality_repo = QualityReportRepository(db)
    edit_history_repo = EditHistoryRepository(db)

    usage_service = UsageService(usage_repo)
    auth_service = AuthService(user_repo)
    user_service = UserService(user_repo, usage_repo)
    upload_service = UploadService(upload_repo, user_repo, usage_repo, storage)
    project_service = ProjectService(
        project_repo,
        user_repo,
        upload_repo,
        model_repo,
        job_repo,
        storage,
    )
    job_service = JobService(job_repo, project_repo, upload_repo, user_repo, usage_repo)

    quality_service = QualityService(project_repo, model_repo, quality_repo, usage_repo, storage)
    repair_service = RepairService(project_repo, model_repo, edit_history_repo, usage_repo, storage, quality_repo)
    edit_service = EditService(project_repo, model_repo, edit_history_repo, usage_repo, storage)
    optimization_service = OptimizationService(project_repo, model_repo, edit_history_repo, usage_repo, storage)

    return Services(
        auth=auth_service,
        users=user_service,
        projects=project_service,
        jobs=job_service,
        uploads=upload_service,
        usage=usage_service,
        storage=storage,
        quality=quality_service,
        repair=repair_service,
        edit=edit_service,
        optimization=optimization_service,
    )

