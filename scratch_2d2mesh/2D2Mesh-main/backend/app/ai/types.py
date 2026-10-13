"""Shared types for the AI generation layer.

Holds the stable data contracts that flow through the whole engine: generation
settings, generation results, progress reporting, stage timing, and output
quality checks. No heavy framework imports here on purpose so this module can be
imported anywhere cheaply.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Dict, List, Optional


class OutputFormat(StrEnum):
    """Supported output artifacts produced by the engine."""

    GLB = "glb"
    GLTF = "gltf"
    OBJ = "obj"
    PREVIEW = "preview"


@dataclass
class StageTiming:
    """Wall-clock duration of a named pipeline stage."""

    stage: str
    seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {"stage": self.stage, "seconds": round(self.seconds, 4)}


@dataclass
class GenerationSettings:
    model: str = "auto"
    resolution: int = 512
    texture_quality: str = "medium"
    remesh: bool = True
    simplify_target: int | None = None
    #: Artifacts requested from the engine (subset of OutputFormat values).
    formats: List[str] = field(default_factory=lambda: ["glb", "gltf", "obj", "preview"])
    #: Hard cap on face count; meshes above it are flagged by validation.
    max_polygons: int = 500_000
    #: Extra inference attempts after a transient failure.
    retries: int = 1
    #: "strict" raises on fatal quality failures, "warn" logs them, "off" skips checks.
    validation: str = "strict"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """Everything produced for one input image."""

    glb_bytes: bytes
    gltf_bytes: Optional[bytes] = None
    obj_bytes: Optional[bytes] = None
    preview_bytes: Optional[bytes] = None
    filename: str = "model.glb"
    stats: Dict[str, Any] = field(default_factory=dict)
    timings: List[StageTiming] = field(default_factory=list)
    validation: Optional[Dict[str, Any]] = None
    device: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "glb_bytes": self.glb_bytes,
            "gltf_bytes": self.gltf_bytes,
            "obj_bytes": self.obj_bytes,
            "preview_bytes": self.preview_bytes,
            "filename": self.filename,
            "stats": self.stats,
            "timings": [t.to_dict() for t in self.timings],
            "validation": self.validation,
            "device": self.device,
            "extra": self.extra,
        }


# -- Errors -----------------------------------------------------------------


class ModelValidationError(RuntimeError):
    """Raised when a generated model fails required quality checks."""


class TransientError(RuntimeError):
    """Marker for recoverable inference failures (safe to retry)."""


# -- Quality checks ---------------------------------------------------------


@dataclass
class QualityCheck:
    name: str
    passed: bool
    severity: str  # "error" | "warning"
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class QualityReport:
    checks: List[QualityCheck] = field(default_factory=list)
    passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "checks": [c.to_dict() for c in self.checks]}

    def summary(self) -> str:
        failed = [c for c in self.checks if not c.passed and c.severity == "error"]
        warned = [c for c in self.checks if not c.passed and c.severity == "warning"]
        return f"{len(failed)} errors, {len(warned)} warnings"


# -- Progress ---------------------------------------------------------------


async def _noop(_p: float, _stage: str, _msg: str) -> None:
    return None


async def dispatch_progress(callback, progress: float, stage: str, message: str) -> None:
    callback = callback or _noop
    result = callback(progress, stage, message)
    if inspect.isawaitable(result):
        await result


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class ProgressReporter:
    """Reports progress to an optional awaitable callback, always in the loop.

    Also records per-stage wall-clock timings (thread-safe, uses
    ``time.perf_counter``) which the engine attaches to every result.
    """

    def __init__(self, callback: Optional[Callable[[float, str, str], Any]] = None) -> None:
        self._callback = callback
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._current_stage: Optional[str] = None
        self._stage_start: Optional[float] = None
        self.timings: List[StageTiming] = []

    def attach_loop(self) -> None:
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def _record_stage(self, stage: str) -> None:
        now = time.perf_counter()
        if self._current_stage is not None and self._stage_start is not None:
            self.timings.append(StageTiming(stage=self._current_stage, seconds=now - self._stage_start))
        self._current_stage = stage
        self._stage_start = now

    async def report(self, progress: float, stage: str, message: str) -> None:
        self._record_stage(stage)
        await dispatch_progress(self._callback, progress, stage, message)

    def sync(self, progress: float, stage: str, message: str) -> None:
        """Safely schedule a progress update from a worker thread."""
        self._record_stage(stage)
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self.report(progress, stage, message)))
