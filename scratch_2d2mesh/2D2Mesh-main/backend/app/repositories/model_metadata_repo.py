"""Model metadata repository."""
from __future__ import annotations

from typing import Optional

from bson import ObjectId

from app.models.enums import ModelFormat
from app.models.model_metadata import BoundingBox, ModelMetadataDocument
from app.core.object_id import PyObjectId
from app.repositories.base import BaseRepository


class ModelMetadataRepository(BaseRepository):
    """Repository for the ``model_metadata`` collection.

    There is at most **one** metadata document per generation job.
    The ``generation_id`` field has a unique index, so ``upsert`` is safe
    to call multiple times without creating duplicates.
    """

    collection_name = "model_metadata"

    async def find_by_generation_id(self, generation_id: ObjectId | str) -> Optional[dict]:
        """Return the metadata document for a given generation, or None."""
        oid = ObjectId(generation_id) if not isinstance(generation_id, ObjectId) else generation_id
        return await self.collection.find_one({"generation_id": oid})

    async def upsert(self, doc: ModelMetadataDocument) -> dict:
        """Insert or replace the metadata for a generation (idempotent).

        Uses ``replace_one`` with ``upsert=True`` keyed on ``generation_id``
        so re-running the pipeline doesn't create duplicate documents.
        """
        raw = doc.model_dump(by_alias=True)
        from app.repositories.base import make_storable

        raw = make_storable(raw)
        # Nested BoundingBox must be serialised to dict
        if isinstance(raw.get("bounding_box"), BoundingBox):
            raw["bounding_box"] = raw["bounding_box"].model_dump()

        await self.collection.replace_one(
            {"generation_id": raw["generation_id"]},
            raw,
            upsert=True,
        )
        return raw

    async def delete_by_generation_id(self, generation_id: ObjectId | str) -> bool:
        """Remove the metadata document for a generation."""
        oid = ObjectId(generation_id) if not isinstance(generation_id, ObjectId) else generation_id
        result = await self.collection.delete_one({"generation_id": oid})
        return result.deleted_count == 1

    @staticmethod
    def build_from_stats(
        generation_id: PyObjectId,
        stats: dict,
        *,
        file_format: ModelFormat = ModelFormat.GLB,
        generation_time: float = 0.0,
    ) -> ModelMetadataDocument:
        """Convenience factory: construct a document from raw AI pipeline stats."""
        bbox_raw = stats.get("bounding_box")
        bbox = BoundingBox(**bbox_raw) if isinstance(bbox_raw, dict) else None

        return ModelMetadataDocument(
            generation_id=generation_id,
            file_format=file_format,
            file_size=stats.get("file_size", 0),
            vertices=stats.get("vertices", 0),
            faces=stats.get("faces", 0),
            polygons=stats.get("polygons", stats.get("faces", 0)),
            materials=stats.get("materials", []),
            textures=stats.get("textures", []),
            bounding_box=bbox,
            generation_time=generation_time,
            extra={k: v for k, v in stats.items() if k not in {
                "file_size", "vertices", "faces", "polygons",
                "materials", "textures", "bounding_box",
            }},
        )
