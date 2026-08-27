from __future__ import annotations

import asyncio
import random
import time

from drogue.core.abstracts import AcquireResult, Algorithm, Storage


class SlidingWindowAlgorithm(Algorithm):
    """Sliding Window Counter rate limiting algorithm.

    O(1) memory per key. More accurate than Fixed Window, avoids the
    boundary burst problem. Best for: distributed systems, general APIs.

    How it works:
    - Two consecutive windows are weighted: previous window's count ×
      overlap_ratio + current window's count
    - overlap_ratio = (window_size - elapsed_in_current_window) / window_size
    - This smooths the transition between windows

    Uses compare-and-swap (CAS) for atomic read-modify-write to prevent
    race conditions that cause over-admission.
    """

    def __init__(
        self,
        storage: Storage,
        limit: int,
        window: float,
    ) -> None:
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        if window <= 0:
            raise ValueError(f"window must be > 0, got {window}")
        self.storage = storage
        self.limit = limit
        self.window = window

    def _make_key(self, key: str, window_id: int) -> str:
        return f"drogue:sw:{key}:{window_id}"

    def _get_window_id(self, now: float) -> int:
        return int(now / self.window)

    def _get_elapsed(self, now: float) -> float:
        return now - (self._get_window_id(now) * self.window)

    def _compute_estimated(
        self, prev_count: int, curr_count: int, weight: float
    ) -> float:
        """Compute weighted estimate from previous and current window counts."""
        return prev_count * weight + curr_count

    async def acquire(
        self,
        key: str,
        cost: int = 1,
        block: bool = False,
        timeout: float | None = None,
    ) -> AcquireResult:
        now = time.monotonic()
        max_retries = 5

        for _attempt in range(max_retries):
            current_window = self._get_window_id(now)
            previous_window = current_window - 1
            elapsed = self._get_elapsed(now)
            weight = (self.window - elapsed) / self.window

            prev_key = self._make_key(key, previous_window)
            curr_key = self._make_key(key, current_window)

            # Read previous window count (read-only, no race on previous window)
            prev_count = await self.storage.get(prev_key) or 0

            # Read current window count and attempt CAS increment
            state = await self.storage.get(curr_key)
            curr_count = state if isinstance(state, int) and state > 0 else 0

            # Compute estimate using current count (before our potential increment)
            estimated = self._compute_estimated(prev_count, curr_count, weight)

            if estimated + cost <= self.limit:
                # Try to atomically increment current window
                # Use expected=None for create-if-absent on first request
                expected = curr_count if curr_count > 0 else None
                if await self.storage.compare_and_swap(
                    curr_key, expected, curr_count + cost, self.window * 2
                ):
                    remaining = int(self.limit - estimated - cost)
                    return AcquireResult(
                        allowed=True,
                        remaining=max(0, remaining),
                        limit=self.limit,
                        reset_at=time.time() + (self.window - elapsed),
                    )
                # CAS failed — another request modified the counter, retry
                await asyncio.sleep(random.uniform(0, 0.001))
                continue
            else:
                # Over limit — don't increment
                retry_after = self.window - elapsed
                if block and timeout is not None:
                    await asyncio.sleep(min(retry_after, timeout))
                    now = time.monotonic()
                    continue

                remaining = max(0, int(self.limit - estimated))
                return AcquireResult(
                    allowed=False,
                    remaining=max(0, remaining),
                    limit=self.limit,
                    retry_after=retry_after,
                    reset_at=time.time() + retry_after,
                )

        # Exhausted retries — fail closed
        return AcquireResult(
            allowed=False,
            remaining=0,
            limit=self.limit,
            retry_after=0.0,
            reset_at=time.time() + self.window,
        )

    async def peek(self, key: str) -> AcquireResult:
        """Check state without consuming tokens."""
        now = time.monotonic()
        current_window = self._get_window_id(now)
        previous_window = current_window - 1
        elapsed = self._get_elapsed(now)
        weight = (self.window - elapsed) / self.window

        prev_key = self._make_key(key, previous_window)
        curr_key = self._make_key(key, current_window)

        prev_count = await self.storage.get(prev_key) or 0
        curr_count = await self.storage.get(curr_key) or 0

        estimated = prev_count * weight + curr_count
        remaining = max(0, int(self.limit - estimated))

        return AcquireResult(
            allowed=remaining > 0,
            remaining=remaining,
            limit=self.limit,
            reset_at=time.time() + (self.window - elapsed),
        )

    async def reset(self, key: str) -> None:
        now = time.monotonic()
        current_window = self._get_window_id(now)
        previous_window = current_window - 1

        await self.storage.delete(self._make_key(key, current_window))
        await self.storage.delete(self._make_key(key, previous_window))