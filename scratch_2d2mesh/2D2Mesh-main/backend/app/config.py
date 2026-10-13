"""Centralized application configuration loaded from environment variables.

Values are read from a local `.env` file or the process environment. Every
secret stays server-side only; the frontend never receives these values.
"""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Keep comma-separated env strings (e.g. CORS_ORIGINS) and let the
        # field validators below parse them instead of forcing JSON decoding.
        enable_decoding=False,
    )

    # Application
    APP_NAME: str = "Vision3D AI"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # Canonical alias: BACKEND_URL (used by Docker/.env at deploy time).
    PUBLIC_BASE_URL: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("PUBLIC_BASE_URL", "BACKEND_URL"),
    )

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Security
    # Canonical alias: JWT_SECRET (used by Docker/.env at deploy time).
    SECRET_KEY: str = Field(
        default=secrets.token_urlsafe(64),
        validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET"),
    )
    # Optional separate key for refresh tokens. Falls back to SECRET_KEY if unset.
    JWT_REFRESH_SECRET: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    SESSION_TTL_DAYS: int = 30  # mirrors REFRESH_TOKEN_EXPIRE_DAYS; used by SessionRepository

    # Database
    # Canonical alias: DATABASE_URL (MongoDB Atlas or local, used at deploy time).
    MONGODB_URL: str = Field(
        default="mongodb://localhost:27017",
        validation_alias=AliasChoices("MONGODB_URL", "DATABASE_URL"),
    )
    MONGODB_DB_NAME: str = "vision3d"
    MONGODB_MAX_POOL_SIZE: int = 50   # max connections in Motor pool
    MONGODB_MIN_POOL_SIZE: int = 5    # min idle connections kept alive

    # Storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_DIR: Path = Path("./storage")
    # Canonical aliases STORAGE_* (S3-compatible object storage, used at deploy time).
    S3_ENDPOINT_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("S3_ENDPOINT_URL", "STORAGE_ENDPOINT"),
    )
    S3_BUCKET: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("S3_BUCKET", "STORAGE_BUCKET"),
    )
    S3_ACCESS_KEY_ID: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("S3_ACCESS_KEY_ID", "STORAGE_ACCESS_KEY"),
    )
    S3_SECRET_ACCESS_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("S3_SECRET_ACCESS_KEY", "STORAGE_SECRET_KEY"),
    )
    S3_REGION: str = "us-east-1"

    # Upload validation
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "webp"]
    ALLOWED_IMAGE_MIME_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp"]

    # AI engine
    AI_MODEL: Literal["mock", "stable-fast-3d", "hunyuan3d", "custom"] = "mock"
    AI_DEVICE: str = "auto"  # auto | cpu | cuda
    AI_MAX_IMAGE_SIZE: int = 1024
    # Face-count budget used by output validation ("excessive polygons" check).
    AI_MAX_POLYGONS: int = 500_000
    # "strict" raises on fatal quality failures, "warn" logs them, "off" skips.
    AI_VALIDATION: str = "strict"
    # Render a PNG preview image of the generated model.
    AI_PREVIEW_RENDER: bool = True
    # Export an OBJ variant alongside GLB/GLTF.
    AI_OBJ_EXPORT: bool = True
    # Extra inference attempts after a transient failure.
    AI_DEFAULT_RETRIES: int = 1
    # Default concurrency for batch generation.
    AI_BATCH_CONCURRENCY: int = 1

    # Stable Fast 3D
    STABLE_FAST_3D_REPO: str = "stabilityai/stable-fast-3d"
    STABLE_FAST_3D_DEVICE: str = "cuda"
    STABLE_FAST_3D_WEIGHT_DTYPE: str = "fp16"

    # Hunyuan3D-2
    HUNYUAN3D_DIFFUSION_REPO: str = "tencent/Hunyuan3D-2"
    HUNYUAN3D_DEVICE: str = "cuda"
    HUNYUAN3D_INCURSOR_DEVICE: str = "cuda"

    # Optional external command for the custom adapter. Template placeholders:
    # {input} -> path to input image, {output} -> output directory,
    # {model_path} -> MODEL_PATH (below).
    CUSTOM_MODEL_COMMAND: Optional[str] = None

    # Optional path to a locally mounted custom model (weights/checkpoints) used
    # by the custom adapter. Passed through to the command template as {model_path}.
    MODEL_PATH: Optional[str] = None

    # Optional canonical name of the frontend origin; appended to CORS_ORIGINS.
    FRONTEND_URL: Optional[str] = None

    # Background worker
    JOB_WORKER_ENABLED: bool = True
    JOB_POLL_INTERVAL_SECONDS: float = 2.0
    JOB_MAX_RETRIES: int = 3
    JOB_STALE_TIMEOUT_MINUTES: int = 30

    # Rate limiting
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_UPLOAD: str = "30/hour"
    RATE_LIMIT_GENERAL: str = "240/hour"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # ── LLM (for NL editing) ─────────────────────────────────────────────────
    # If OPENAI_API_KEY is set, the NL edit feature will use GPT. Otherwise,
    # a keyword-based mock parser is used (no API key required).
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator(
        "ALLOWED_IMAGE_EXTENSIONS",
        "ALLOWED_IMAGE_MIME_TYPES",
        mode="before",
    )
    @classmethod
    def _parse_list(cls, v: object) -> object:
        if isinstance(v, str):
            return [item.strip().lower() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def _merge_frontend_origin(self) -> "Settings":
        if self.FRONTEND_URL and self.FRONTEND_URL not in self.CORS_ORIGINS:
            self.CORS_ORIGINS = [self.FRONTEND_URL, *self.CORS_ORIGINS]
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def storage_path(self) -> Path:
        path = self.LOCAL_STORAGE_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
