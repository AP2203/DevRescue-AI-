"""Inference engine package: hardware awareness, runtime, and output validation."""

from app.ai.inference.device import (
    DeviceInfo,
    VRAMMonitor,
    cuda_available,
    device_count,
    get_device_info,
    resolve_device,
    vram_snapshot,
)
from app.ai.inference.runtime import (
    BatchProcessor,
    ErrorClassifier,
    InferenceReport,
    InferenceTimer,
    compute_backoff,
    retry_async,
)
from app.ai.inference.validator import OutputValidator, QualityReportBuilder

__all__ = [
    "VRAMMonitor",
    "DeviceInfo",
    "cuda_available",
    "device_count",
    "get_device_info",
    "resolve_device",
    "vram_snapshot",
    "BatchProcessor",
    "ErrorClassifier",
    "InferenceReport",
    "InferenceTimer",
    "compute_backoff",
    "retry_async",
    "OutputValidator",
    "QualityReportBuilder",
]
