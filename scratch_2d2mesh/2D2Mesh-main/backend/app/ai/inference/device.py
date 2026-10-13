"""Hardware detection and VRAM monitoring for inference.

Degrades gracefully when PyTorch / CUDA are not installed: a CPU-only
environment still gets accurate ``DeviceInfo`` so the rest of the engine can
make device decisions without importing torch directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Snapshot of the compute device available for inference."""

    type: str = "cpu"  # "cuda" | "cpu"
    name: str = "CPU"
    index: int = 0
    cuda_available: bool = False
    device_count: int = 0
    backend: str = "none"  # "torch" | "none"
    vram_total_mb: Optional[int] = None
    vram_used_mb: Optional[int] = None
    vram_free_mb: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "name": self.name,
            "index": self.index,
            "cuda_available": self.cuda_available,
            "device_count": self.device_count,
            "backend": self.backend,
            "vram_total_mb": self.vram_total_mb,
            "vram_used_mb": self.vram_used_mb,
            "vram_free_mb": self.vram_free_mb,
        }


def _torch():
    """Return the torch module when importable, else None."""
    try:
        import torch  # type: ignore

        return torch
    except ImportError:  # pragma: no cover - torch optional
        return None


def cuda_available() -> bool:
    torch = _torch()
    if torch is None:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:  # pragma: no cover
        return False


def device_count() -> int:
    torch = _torch()
    if torch is None:
        return 0
    try:
        return int(torch.cuda.device_count())
    except Exception:  # pragma: no cover
        return 0


def resolve_device(preference: str = "auto") -> str:
    """Resolve a device preference to a concrete runtime device.

    ``auto`` -> CUDA when available, else CPU.
    ``cuda`` -> CUDA when available, else CPU (with a warning).
    ``cpu``  -> always CPU.
    """
    pref = (preference or "auto").lower()
    if pref == "cpu":
        return "cpu"
    if cuda_available():
        return "cuda"
    if pref == "cuda":
        logger.warning("CUDA requested but unavailable; falling back to CPU")
    return "cpu"


def vram_snapshot(device_index: int = 0) -> dict:
    """Return a VRAM usage snapshot for a device (all-None when unsupported)."""
    torch = _torch()
    snapshot = {
        "device": device_index,
        "total_mb": None,
        "used_mb": None,
        "free_mb": None,
        "allocated_mb": None,
        "reserved_mb": None,
    }
    if torch is None or not cuda_available():
        return snapshot
    try:
        free, total = torch.cuda.mem_get_info(device_index)
        snapshot["total_mb"] = total // (1024 * 1024)
        snapshot["free_mb"] = free // (1024 * 1024)
        snapshot["used_mb"] = (total - free) // (1024 * 1024)
        snapshot["allocated_mb"] = torch.cuda.memory_allocated(device_index) // (1024 * 1024)
        snapshot["reserved_mb"] = torch.cuda.memory_reserved(device_index) // (1024 * 1024)
    except Exception as exc:  # pragma: no cover
        logger.warning("VRAM snapshot failed: %s", exc)
    return snapshot


def get_device_info(preference: str = "auto") -> DeviceInfo:
    """Describe the resolved inference device (CPU or CUDA GPU)."""
    torch = _torch()
    if torch is None:
        return DeviceInfo(backend="none", type="cpu", name="CPU")
    info = DeviceInfo(backend="torch")
    if cuda_available():
        index = 0
        info.cuda_available = True
        info.device_count = device_count()
        info.type = "cuda"
        info.index = index
        try:
            info.name = torch.cuda.get_device_name(index)
        except Exception:  # pragma: no cover
            info.name = f"CUDA GPU {index}"
        snap = vram_snapshot(index)
        info.vram_total_mb = snap["total_mb"]
        info.vram_used_mb = snap["used_mb"]
        info.vram_free_mb = snap["free_mb"]
    else:
        info.type = "cpu"
        info.name = "CPU"
    return info


class VRAMMonitor:
    """Context manager that measures VRAM deltas around an inference block."""

    def __init__(self, device_index: int = 0) -> None:
        self.device_index = device_index
        self.before: dict = {}
        self.after: dict = {}

    def __enter__(self) -> "VRAMMonitor":
        self.before = vram_snapshot(self.device_index)
        return self

    def __exit__(self, *_exc) -> bool:
        self.after = vram_snapshot(self.device_index)
        return False

    def delta_mb(self) -> Optional[int]:
        if self.before.get("used_mb") is None or self.after.get("used_mb") is None:
            return None
        return int(self.after["used_mb"] - self.before["used_mb"])
