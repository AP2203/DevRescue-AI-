"""Simple in-memory sliding-window rate limiter used by the protected JWT routes.

This complements the global slowapi limiter applied to public endpoints. It is
process-local, which is fine for single-instance deployments; for multi-worker
deployments swap it for a Redis-backed limiter behind the same interface.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Tuple

from app.exceptions import RateLimitExceeded

# Re-exported for convenience.


@dataclass
class _Bucket:
    hits: Deque[float] = field(default_factory=deque)


class SlidingWindowLimiter:
    """Allows `limit` requests per `window_seconds` sliding window, keyed by route+identity."""

    def __init__(self) -> None:
        self._buckets: Dict[Tuple[str, str], _Bucket] = defaultdict(_Bucket)

    def check(self, key: str, identity: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        bucket = self._buckets[(key, identity)]
        while bucket.hits and now - bucket.hits[0] > window_seconds:
            bucket.hits.popleft()
        if len(bucket.hits) >= limit:
            raise RateLimitExceeded()
        bucket.hits.append(now)


rate_limiter = SlidingWindowLimiter()
