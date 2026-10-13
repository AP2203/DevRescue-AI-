"""Admin dashboard routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_current_admin, get_services
from app.exceptions import ValidationError
from app.models.enums import UserRole
from app.repositories import (
    JobRepository,
    ModelAssetRepository,
    ProjectRepository,
    UploadRepository,
    UsageRepository,
    UserRepository,
)
from app.schemas.admin import (
    AdminStats,
    AdminUpdateUserRequest,
    AdminUserList,
    AdminUserRow,
)
from app.schemas.common import normalize_doc
from app.services import Services

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


def _repos(request: Request):
    db = request.app.state.db
    return {
        "users": UserRepository(db),
        "projects": ProjectRepository(db),
        "jobs": JobRepository(db),
        "uploads": UploadRepository(db),
        "models": ModelAssetRepository(db),
        "usage": UsageRepository(db),
    }


@router.get("/stats", response_model=AdminStats)
async def admin_stats(request: Request) -> AdminStats:
    repos = _repos(request)
    jobs_by_status = await repos["jobs"].status_counts()
    storage_rows = await repos["uploads"].aggregate(
        [
            {"$group": {"_id": "$content_type", "count": {"$sum": 1}, "size_bytes": {"$sum": "$size_bytes"}}},
            {"$project": {"kind": "$_id", "count": 1, "bytes": "$size_bytes", "_id": 0}},
        ]
    )
    active = await repos["usage"].recent_activity_user_ids(hours=24)
    return AdminStats(
        users=await repos["users"].count(),
        projects=await repos["projects"].count(),
        jobs=await repos["jobs"].count(),
        uploads=await repos["uploads"].count(),
        models=await repos["models"].count(),
        storage_total_bytes=sum(r.get("bytes") or 0 for r in storage_rows),
        jobs_by_status=[{"status": r["status"], "count": r["count"]} for r in jobs_by_status],
        storage_by_kind=[
            {"kind": r.get("kind") or "unknown", "count": r.get("count") or 0, "bytes": r.get("bytes") or 0}
            for r in storage_rows
        ],
        active_in_last_24h=len(active),
    )


@router.get("/users", response_model=AdminUserList)
async def admin_list_users(
    request: Request,
    query: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> AdminUserList:
    repos = _repos(request)
    total, items = await repos["users"].search(query, page, page_size)
    return AdminUserList(
        items=[normalize_doc(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/users/{user_id}", response_model=AdminUserRow)
async def admin_update_user(
    user_id: str,
    payload: AdminUpdateUserRequest,
    request: Request,
    services: Services = Depends(get_services),
) -> dict:
    if payload.role not in (None, UserRole.USER.value, UserRole.ADMIN.value):
        raise ValidationError("Invalid role")
    if payload.role:
        await services.users.set_role(user_id, payload.role)
    if payload.is_active is not None:
        await services.users.set_active(user_id, payload.is_active)
    public = await services.users.get_public(user_id)
    return {
        "id": public["id"],
        "email": public["email"],
        "username": public["username"],
        "role": public["role"],
        "is_active": public["is_active"],
        "metrics": public.get("metrics", {}),
        "created_at": public["created_at"],
    }


@router.get("/jobs")
async def admin_list_jobs(
    request: Request,
    job_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    repos = _repos(request)
    query = {"status": job_status} if job_status else {}
    total = await repos["jobs"].count(query)
    items = await repos["jobs"].find_many(query, sort=[("created_at", -1)], skip=(page - 1) * page_size, limit=page_size)
    return {
        "items": [normalize_doc(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }
