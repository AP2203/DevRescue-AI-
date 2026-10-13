"""Natural-language 3D Edit Service.

Implements the full NL-edit pipeline:

    User Command → LLM → Structured JSON Operation → Validation → 3D Editing
    Service → Updated Model → Quality Check → Save New Version

Steps:
1. Parse user text into a structured command (LLM or mock)
2. Validate the structured command (never let an invalid op reach the editor)
3. Load the current GLB for the project's active version
4. Apply the operations deterministically with the mesh editor
5. Run a quality check on the edited bytes
6. Save the edited GLB as a new model asset + bump the project version
7. Record edit history (with version) + usage
8. Support undo / redo / version listing
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.ai.command_validator import CommandValidationError, validate_command
from app.ai.llm_command_parser import parse_command
from app.ai.mesh_editor import apply_command
from app.ai.quality_analyzer import analyze_glb
from app.config import get_settings
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


class EditService:
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

    # ── Core pipeline ─────────────────────────────────────────────────────────

    async def apply_nl_edit(self, user_id: str, project_id: str, command_text: str) -> dict:
        """Parse → validate → apply → quality-check → save new version."""
        project = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if project is None:
            raise NotFoundError("Project not found")
        if not project.get("model_asset_id"):
            raise NotFoundError("This project has no generated model yet")

        settings = get_settings()
        use_openai = bool(getattr(settings, "OPENAI_API_KEY", None))

        # Step 1 — LLM interprets the command into structured JSON
        parsed = parse_command(
            command_text,
            use_openai=use_openai,
            openai_model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
        )

        if parsed.get("operation") == "unknown" or not parsed.get("operations"):
            raise ValidationError(parsed.get("error", "Could not understand the command."))

        # Step 2 — Validation (never edit blindly)
        try:
            parsed = validate_command(parsed)
        except CommandValidationError as exc:
            raise ValidationError(exc.message, details={"operations": exc.details}) from exc

        # Step 3 — Load the active GLB
        current_asset = await self.models.find_by_id(to_object_id(project["model_asset_id"]))
        if current_asset is None:
            raise NotFoundError("Model asset missing from storage")

        glb_bytes = await self.storage.load(current_asset["glb_key"])
        if not glb_bytes:
            raise NotFoundError("GLB file not found in storage")

        # Step 4 — Deterministic edit
        edit_result = apply_command(glb_bytes, parsed)

        # Step 5 — Quality check on the original and updated model
        quality_before = analyze_glb(glb_bytes)
        quality_after = analyze_glb(edit_result.edited_glb_bytes)
        quality = quality_after

        # Step 6 — Save the new version + bump project version
        uid = uuid.uuid4().hex[:8]
        edited_key = f"models/{user_id}/{project_id}/{uid}/edited.glb"
        await self.storage.save(edited_key, edit_result.edited_glb_bytes, "model/gltf-binary")

        edited_asset = ModelAssetDocument(
            user_id=PyObjectId(str(to_object_id(user_id))),
            project_id=PyObjectId(str(to_object_id(project_id))),
            job_id=PyObjectId(str(current_asset["job_id"])),
            glb_key=edited_key,
            filename="edited.glb",
            size_bytes=len(edit_result.edited_glb_bytes),
            mime_type="model/gltf-binary",
            stats={
                "edited": True,
                "operations": edit_result.applied_operations,
                "quality_score": quality.overall_score,
                **edit_result.after_stats,
            },
        )
        inserted_asset = await self.models.insert_one(edited_asset.model_dump(by_alias=True))

        # Version bookkeeping: truncate any redo branch, then append.
        current_version = int(project.get("edit_version") or 0)
        new_version = current_version + 1
        await self.edit_history.delete_versions_after(to_object_id(project_id), current_version)
        await self.projects.update_by_id(
            to_object_id(project_id),
            {
                "model_asset_id": inserted_asset["_id"],
                "edit_version": new_version,
                "status": "ready",
            },
        )

        # Step 7 — Record history + usage
        history_doc = EditHistoryDocument(
            project_id=PyObjectId(str(to_object_id(project_id))),
            user_id=PyObjectId(str(to_object_id(user_id))),
            operation_type="ai_edit",
            version=new_version,
            original_asset_id=PyObjectId(str(current_asset["_id"])),
            result_asset_id=PyObjectId(str(inserted_asset["_id"])),
            user_command=command_text,
            parsed_command=parsed,
            before_stats=edit_result.before_stats,
            after_stats=edit_result.after_stats,
            meta={
                "quality_before": quality_before.overall_score,
                "quality_after": quality_after.overall_score,
            },
        )
        await self.edit_history.insert_one(history_doc.model_dump(by_alias=True))

        await self.usage.record(
            to_object_id(user_id),
            "ai_edit",
            payload_bytes=len(edit_result.edited_glb_bytes),
            project_id=project_id,
        )

        logger.info("AI edit applied to project %s -> version %d", project_id, new_version)

        return {
            "asset_id": str(inserted_asset["_id"]),
            "version": new_version,
            "parsed_command": parsed,
            "message": edit_result.message,
            "before_stats": edit_result.before_stats,
            "after_stats": edit_result.after_stats,
            "quality_score": quality.overall_score,
            "download_url": self.storage.public_url(edited_key),
        }

    # ── Version navigation: undo / redo ──────────────────────────────────────

    async def undo_edit(self, user_id: str, project_id: str) -> dict:
        """Move the project one version backward (Original → Edit 1 → …)."""
        project = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if project is None:
            raise NotFoundError("Project not found")

        current_version = int(project.get("edit_version") or 0)
        if current_version <= 0:
            raise ValidationError("Nothing to undo — already at the Original version")

        target_version = current_version - 1
        asset_id = await self._asset_for_version(project_id, target_version)
        if asset_id is None:
            raise NotFoundError("Previous version asset is missing")

        await self.projects.update_by_id(
            to_object_id(project_id),
            {"model_asset_id": asset_id, "edit_version": target_version},
        )
        logger.info("Undo -> version %d for project %s", target_version, project_id)

        return {
            "asset_id": str(asset_id),
            "version": target_version,
            "can_undo": target_version > 0,
            "can_redo": True,
        }

    async def redo_edit(self, user_id: str, project_id: str) -> dict:
        """Move the project one version forward (… → Edit 2 → Edit 3)."""
        project = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if project is None:
            raise NotFoundError("Project not found")

        current_version = int(project.get("edit_version") or 0)
        max_version = await self.edit_history.max_version(to_object_id(project_id))
        if current_version >= max_version:
            raise ValidationError("Nothing to redo — already at the latest version")

        target_version = current_version + 1
        asset_id = await self._asset_for_version(project_id, target_version)
        if asset_id is None:
            raise NotFoundError("Next version asset is missing")

        await self.projects.update_by_id(
            to_object_id(project_id),
            {"model_asset_id": asset_id, "edit_version": target_version},
        )
        logger.info("Redo -> version %d for project %s", target_version, project_id)

        return {
            "asset_id": str(asset_id),
            "version": target_version,
            "can_undo": True,
            "can_redo": target_version < max_version,
        }

    # ── Version history listing ───────────────────────────────────────────────

    async def get_versions(self, user_id: str, project_id: str) -> dict:
        """Return the version timeline (Original, Edit 1, Edit 2, …)."""
        project = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if project is None:
            raise NotFoundError("Project not found")

        docs = await self.edit_history.list_for_project_asc(to_object_id(project_id))
        current_version = int(project.get("edit_version") or 0)
        max_version = await self.edit_history.max_version(to_object_id(project_id))

        versions = [self._version_entry(0, "Original", project.get("model_asset_id"), None, None)]
        for doc in docs:
            version = int(doc.get("version") or 0)
            if version <= 0:
                continue
            versions.append(
                self._version_entry(
                    version,
                    f"Edit {version}",
                    doc.get("result_asset_id"),
                    doc.get("user_command"),
                    doc.get("operation_type"),
                )
            )

        return {
            "versions": versions,
            "current_version": current_version,
            "max_version": max_version,
            "can_undo": current_version > 0,
            "can_redo": current_version < max_version,
        }

    async def get_edit_history(self, user_id: str, project_id: str, limit: int = 20) -> list:
        """Return edit history for a project."""
        project = await self.projects.owned_by(to_object_id(project_id), to_object_id(user_id))
        if project is None:
            raise NotFoundError("Project not found")

        docs = await self.edit_history.list_for_project(to_object_id(project_id), limit=limit)
        return [normalize_doc(d) for d in docs]

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _asset_for_version(self, project_id: str, version: int) -> Optional[object]:
        """Resolve the model asset id that represents `version` of the project.

        Version 0 (Original) has no history row — it is the ``original_asset_id``
        of the first edit, or the project's current model if no edits exist.
        """
        if version == 0:
            first = await self.edit_history.list_for_project_asc(to_object_id(project_id), limit=1)
            if first:
                return first[0].get("original_asset_id")
            project = await self.projects.find_by_id(to_object_id(project_id))
            return project.get("model_asset_id") if project else None

        doc = await self.edit_history.get_by_version(to_object_id(project_id), version)
        if doc is None:
            return None
        return doc.get("result_asset_id")

    @staticmethod
    def _version_entry(
        version: int,
        label: str,
        asset_id: object,
        user_command: Optional[str],
        operation_type: Optional[str],
    ) -> dict:
        return {
            "version": version,
            "label": label,
            "asset_id": str(asset_id) if asset_id else None,
            "user_command": user_command,
            "operation_type": operation_type,
        }
