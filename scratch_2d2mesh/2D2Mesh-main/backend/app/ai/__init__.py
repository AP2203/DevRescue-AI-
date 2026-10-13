"""AI engine.

The `ImageTo3DModel` base class in :mod:`app.ai.models.base_model` defines one
stable interface. Concrete implementations live in :mod:`app.ai.models` and are
registered in the :mod:`app.ai.factory`. The engine layers device resolution,
VRAM monitoring, timing, batch processing, retries, and output validation on
top of every adapter. New models (including custom trained checkpoints) can be
plugged in by adding an adapter class and registering it without touching any
other part of the app.
"""

from app.ai.factory import ModelNotAvailableError, create_ai_model, get_registered_models
from app.ai.models.base_model import ImageTo3DModel, ModelState
from app.ai.types import (
    GenerationResult,
    GenerationSettings,
    ModelValidationError,
    OutputFormat,
    ProgressReporter,
    QualityCheck,
    QualityReport,
    StageTiming,
    TransientError,
)

__all__ = [
    "ImageTo3DModel",
    "ModelState",
    "GenerationResult",
    "GenerationSettings",
    "OutputFormat",
    "ProgressReporter",
    "QualityCheck",
    "QualityReport",
    "StageTiming",
    "ModelValidationError",
    "TransientError",
    "create_ai_model",
    "get_registered_models",
    "ModelNotAvailableError",
]
