"""Model registry and factory.

Models register themselves by name; `create_ai_model` resolves the configured
(or requested) model. Adding a custom trained model = implement a new adapter
subclassing `ImageTo3DModel`, register it, and reference it via AI_MODEL or job
settings. No other code changes required.
"""

from __future__ import annotations

from typing import Dict, List, Type

from app.ai.models.base_model import ImageTo3DModel
from app.ai.models.custom_model import Custom3DModelService
from app.ai.models.hunyuan3d import Hunyuan3DAdapter
from app.ai.models.mock import MockAdapter
from app.ai.models.stable_fast_3d import StableFast3DAdapter
from app.config import get_settings

_REGISTRY: Dict[str, Type[ImageTo3DModel]] = {}


class ModelNotAvailableError(RuntimeError):
    pass


def register(name: str, model_cls: Type[ImageTo3DModel]) -> Type[ImageTo3DModel]:
    _REGISTRY[name] = model_cls
    return model_cls


def get_registered_models() -> List[str]:
    return list(_REGISTRY.keys())


def _build_kwargs(name: str) -> dict:
    settings = get_settings()
    if name == "stable-fast-3d":
        return {
            "repo_id": settings.STABLE_FAST_3D_REPO,
            "device": settings.AI_DEVICE or settings.STABLE_FAST_3D_DEVICE,
            "weight_dtype": settings.STABLE_FAST_3D_WEIGHT_DTYPE,
        }
    if name == "hunyuan3d":
        return {
            "diffusion_repo": settings.HUNYUAN3D_DIFFUSION_REPO,
            "shape_device": settings.HUNYUAN3D_DEVICE,
            "texture_device": settings.HUNYUAN3D_INCURSOR_DEVICE,
        }
    return {}


def create_ai_model(name: str = "auto") -> ImageTo3DModel:
    settings = get_settings()
    chosen = settings.AI_MODEL if name in ("auto", "", None) else name
    if chosen not in _REGISTRY:
        raise ModelNotAvailableError(f"AI model '{chosen}' is not registered. Available: {sorted(_REGISTRY)}")
    model_cls = _REGISTRY[chosen]
    return model_cls(**_build_kwargs(chosen))


# Register built-in models.
register("mock", MockAdapter)
register("stable-fast-3d", StableFast3DAdapter)
register("hunyuan3d", Hunyuan3DAdapter)
register("custom", Custom3DModelService)
