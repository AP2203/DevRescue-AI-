"""Image upload service: validation, dimension sniffing, hashing, and storage."""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import uuid
from datetime import UTC
from typing import Optional

from bson import ObjectId
from fastapi import UploadFile

from app.config import get_settings
from app.core.object_id import to_object_id
from app.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError, ValidationError
from app.repositories.upload_repo import UploadRepository
from app.repositories.usage_repo import UsageRepository
from app.repositories.user_repo import UserRepository
from app.schemas.common import normalize_doc
from app.services.storage_service import StorageBackend, get_storage

logger = logging.getLogger(__name__)

# Approximate blocks for async chunked reads
_CHUNK = 1024 * 1024


class UploadService:
    def __init__(
        self,
        uploads: UploadRepository,
        users: UserRepository,
        usage: UsageRepository,
        storage: Optional[StorageBackend] = None,
    ) -> None:
        self.uploads = uploads
        self.users = users
        self.usage = usage
        self.storage = storage or get_storage()

    async def create(self, user_id: str, file: UploadFile) -> dict:
        settings = get_settings()

        original = file.filename or "upload"
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
            raise UnsupportedMediaTypeError("Only JPG, PNG and WEBP images are supported")

        if file.content_type not in settings.ALLOWED_IMAGE_MIME_TYPES:
            raise UnsupportedMediaTypeError("Unsupported image file type")

        data = await self._read_limited(file)
        if len(data) > settings.max_upload_bytes:
            raise PayloadTooLargeError(
                f"Image exceeds the maximum size of {settings.MAX_UPLOAD_SIZE_MB} MB"
            )
        if not data:
            raise ValidationError("Uploaded file is empty")

        try:
            width, height, mime = await asyncio.to_thread(self._inspect_image, data)
        except (ValueError, OSError) as exc:
            logger.warning("Image inspection failed: %s", exc)
            raise UnsupportedMediaTypeError(
                "The uploaded file is not a valid image"
            ) from exc

        # Reject mismatches between the declared MIME and the real payload.
        declared = (file.content_type or "").lower()
        if declared and declared not in settings.ALLOWED_IMAGE_MIME_TYPES:
            raise UnsupportedMediaTypeError("Unsupported image file type")
        if declared and declared != mime:
            raise UnsupportedMediaTypeError("File content does not match its declared type")

        storage_key = f"uploads/{user_id}/{uuid.uuid4().hex}.{ext}"
        await self.storage.save(storage_key, data, mime)

        doc_id = ObjectId()
        doc = {
            "_id": doc_id,
            "user_id": ObjectId(user_id),
            "original_filename": original[:255],
            "content_type": mime,
            "size_bytes": len(data),
            "storage_key": storage_key,
            "width": width,
            "height": height,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        from datetime import datetime

        doc["created_at"] = datetime.now(UTC)
        await self.uploads.insert_one(doc)
        await self.users.increment_metrics(ObjectId(user_id), total_upload_bytes=len(data))
        await self.usage.record(ObjectId(user_id), "upload", payload_bytes=len(data))

        upload = normalize_doc(doc)
        upload["url"] = self.storage.public_url(storage_key)
        logger.info("Uploaded %s (%s bytes) for user %s", original, len(data), user_id)
        return upload

    async def _read_limited(self, file: UploadFile) -> bytes:
        settings = get_settings()
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > settings.max_upload_bytes:
                raise PayloadTooLargeError(
                    f"Image exceeds the maximum size of {settings.MAX_UPLOAD_SIZE_MB} MB"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def _inspect_image(self, data: bytes) -> tuple[int, int, str]:
        """Verify the payload really decodes as an image and return dims + detected MIME."""
        from PIL import Image

        try:
            image = Image.open(io.BytesIO(data))
            image.verify()
        except Exception as exc:
            raise ValidationError("Could not decode image") from exc

        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
            mime_map = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
            if fmt not in mime_map:
                raise UnsupportedMediaTypeError("Only JPG, PNG and WEBP images are supported")
            return width, height, mime_map[fmt]

    async def get_owned(self, user_id: str, upload_id: str) -> dict:
        doc = await self.uploads.owned_by(to_object_id(upload_id), to_object_id(user_id))
        if doc is None:
            raise ValidationError("Upload not found or not owned by user")
        upload = normalize_doc(doc)
        upload["url"] = self.storage.public_url(doc["storage_key"])
        return upload
