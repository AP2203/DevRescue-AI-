"""Backward-compatible import path for the engine base class."""

from app.ai.models.base_model import ImageTo3DModel, ModelState

__all__ = ["ImageTo3DModel", "ModelState"]
