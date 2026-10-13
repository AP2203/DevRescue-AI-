"""Storage abstraction.

Bundles a `local` backing store for development and an S3-compatible backing
store (AWS S3, MinIO, DigitalOcean Spaces, ...) for production behind a single
async interface.
"""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import boto3

from app.config import Settings, get_settings
from app.exceptions import NotFoundError, StorageError

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    async def load(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    def public_url(self, key: str) -> str: ...

    @property
    @abstractmethod
    def provider(self) -> str: ...


@dataclass
class LocalStorageBackend(StorageBackend):
    base_dir: Path
    base_url: str
    file_route_prefix: str

    def _resolve(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        base = self.base_dir.resolve()
        if not path.is_relative_to(base):
            raise StorageError("Invalid storage key")
        return path

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(data)
        except OSError as exc:
            logger.error("Failed to write local file %s: %s", key, exc)
            raise StorageError("Failed to write storage object") from exc

    async def load(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise NotFoundError(f"Storage object '{key}' not found")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError("Failed to read storage object") from exc

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to delete local file %s: %s", key, exc)

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def public_url(self, key: str) -> str:
        return f"{self.base_url}{self.file_route_prefix}/{key}"

    @property
    def provider(self) -> str:
        return "local"


@dataclass
class S3StorageBackend(StorageBackend):
    bucket: str
    endpoint_url: Optional[str]
    region: str
    access_key: Optional[str]
    secret_key: Optional[str]
    _client: object = None

    def _get_client(self):
        if self._client is None:
            try:
                self._client = boto3.client(
                    "s3",
                    region_name=self.region,
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                )
            except Exception as exc:  # pragma: no cover
                raise StorageError("Could not initialize S3 client") from exc
        return self._client

    def _run(self, fn, *args, **kwargs):
        """Run a blocking boto3 call on a worker thread to avoid blocking the event loop."""
        result = {}

        def _target():
            try:
                result["value"] = fn(*args, **kwargs)
            except Exception as exc:  # pragma: no cover
                result["error"] = exc

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]  # type: ignore[misc]
        return result.get("value")

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._run(
                self._get_client().put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
            )
        except Exception as exc:
            logger.error("S3 put failed for %s: %s", key, exc)
            raise StorageError("Failed to upload storage object") from exc

    async def load(self, key: str) -> bytes:
        try:
            body = self._run(self._get_client().get_object, Bucket=self.bucket, Key=key)["Body"]
            return body.read()
        except StorageError:
            raise
        except Exception as exc:
            if getattr(exc, "response", {}).get("Error", {}).get("Code") == "NoSuchKey":
                raise NotFoundError(f"Storage object '{key}' not found") from exc
            raise StorageError("Failed to read storage object") from exc

    async def delete(self, key: str) -> None:
        try:
            self._run(self._get_client().delete_object, Bucket=self.bucket, Key=key)
        except Exception as exc:
            logger.warning("S3 delete failed for %s: %s", key, exc)

    async def exists(self, key: str) -> bool:
        try:
            await self.load(key)
            return True
        except NotFoundError:
            return False
        except Exception:
            return False

    def public_url(self, key: str) -> str:
        try:
            return self._run(
                self._get_client().generate_presigned_url,
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=3600,
            )
        except Exception as exc:
            logger.error("Failed to presign URL for %s: %s", key, exc)
            return ""

    @property
    def provider(self) -> str:
        return "s3"


_storage: Optional[StorageBackend] = None


def _build_storage(settings: Settings) -> StorageBackend:
    if settings.STORAGE_BACKEND == "s3":
        return S3StorageBackend(
            bucket=settings.S3_BUCKET or "vision3d",
            endpoint_url=settings.S3_ENDPOINT_URL,
            region=settings.S3_REGION,
            access_key=settings.S3_ACCESS_KEY_ID,
            secret_key=settings.S3_SECRET_ACCESS_KEY,
        )
    return LocalStorageBackend(
        base_dir=settings.storage_path,
        base_url=settings.PUBLIC_BASE_URL,
        file_route_prefix=f"{settings.API_V1_PREFIX}/files",
    )


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = _build_storage(get_settings())
    return _storage


def reset_storage_for_tests() -> None:
    global _storage
    _storage = None
