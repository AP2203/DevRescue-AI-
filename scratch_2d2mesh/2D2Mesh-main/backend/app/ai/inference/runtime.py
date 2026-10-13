"""Inference runtime utilities: timing, batch orchestration, and error recovery.

These helpers are framework-agnostic: the engine base model and any batch
worker can reuse them without coupling to a specific model implementation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional, Sequence

from app.ai.types import StageTiming, TransientError

logger = logging.getLogger(__name__)

_TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "cuda out of memory",
    "out of memory",
    "cudnn",
    "connection reset",
    "connection refused",
    "connection aborted",
    "temporarily unavailable",
    "resource temporarily unavailable",
    "interrupted",
    "transient",
)


class ErrorClassifier:
    """Classify inference exceptions as transient (retryable) or fatal."""

    TRANSIENT_TYPES = (TimeoutError, ConnectionError, TransientError)

    @classmethod
    def is_transient(cls, exc: BaseException) -> bool:
        if isinstance(exc, cls.TRANSIENT_TYPES):
            return True
        text = str(exc).lower()
        return any(marker in text for marker in _TRANSIENT_MARKERS)


def compute_backoff(
    attempt: int, base_delay: float = 2.0, factor: float = 2.0, max_delay: float = 30.0
) -> float:
    """Exponential backoff delay in seconds for a given 1-based attempt."""
    return min(max_delay, base_delay * (factor ** max(0, attempt - 1)))


async def retry_async(
    fn: Callable[..., Awaitable[Any]],
    *,
    retries: int = 2,
    base_delay: float = 2.0,
    on_retry: Optional[Callable[[int, BaseException], Any]] = None,
    **kwargs: Any,
) -> Any:
    """Run an async callable, retrying transient failures with backoff."""
    attempts = max(1, retries + 1)
    last_exc: Optional[BaseException] = None
    for attempt in range(attempts):
        try:
            return await fn(**kwargs)
        except BaseException as exc:  # noqa: BLE001 - must not swallow KeyboardInterrupt handling
            last_exc = exc
            if not ErrorClassifier.is_transient(exc) or attempt == attempts - 1:
                raise
            if on_retry is not None:
                on_retry(attempt + 1, exc)
            delay = compute_backoff(attempt + 1, base_delay)
            logger.warning(
                "Transient failure (attempt %d/%d): %s. Retrying in %.1fs",
                attempt + 1,
                attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


@dataclass
class InferenceReport:
    """Aggregated runtime information for one inference run."""

    total_seconds: float = 0.0
    timings: List[StageTiming] = field(default_factory=list)
    device: dict = field(default_factory=dict)
    retries: int = 0
    vram_delta_mb: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "total_seconds": round(self.total_seconds, 4),
            "timings": [t.to_dict() for t in self.timings],
            "device": self.device,
            "retries": self.retries,
            "vram_delta_mb": self.vram_delta_mb,
        }


class InferenceTimer:
    """Records wall-clock time of named stages (``start``/``stop``)."""

    def __init__(self) -> None:
        self.timings: List[StageTiming] = []
        self._start: Optional[float] = None
        self._current: Optional[str] = None

    def start(self, stage: str) -> None:
        self._finalize()
        self._current = stage
        self._start = time.perf_counter()

    def _finalize(self) -> None:
        if self._current is not None and self._start is not None:
            self.timings.append(StageTiming(stage=self._current, seconds=time.perf_counter() - self._start))
        self._current = None
        self._start = None

    def stop(self) -> List[StageTiming]:
        self._finalize()
        return list(self.timings)


class BatchProcessor:
    """Run an async worker over many items with bounded concurrency.

    Used by the engine's ``generate_batch`` and useful to any caller that wants
    batched inference without over-subscribing the GPU.
    """

    def __init__(self, concurrency: int = 1) -> None:
        self.concurrency = max(1, int(concurrency))
        self._semaphore = asyncio.Semaphore(self.concurrency)

    async def run(
        self,
        items: Sequence[Any],
        worker: Callable[[int, Any], Awaitable[Any]],
        raise_on_error: bool = True,
    ) -> List[Any]:
        """Run ``worker(index, item)`` for each item.

        Returns results aligned with ``items``. When ``raise_on_error`` is False
        failed slots contain the raised exception object.
        """

        async def _run_one(index: int, item: Any) -> tuple[int, Any]:
            async with self._semaphore:
                return (index, await worker(index, item))

        outcomes = await asyncio.gather(
            *[_run_one(i, item) for i, item in enumerate(items)],
            return_exceptions=True,
        )
        results: List[Any] = [None] * len(items)
        errors: List[BaseException] = []
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                errors.append(outcome)
            else:
                index, value = outcome
                results[index] = value
        if errors and raise_on_error:
            raise errors[0]
        return results
