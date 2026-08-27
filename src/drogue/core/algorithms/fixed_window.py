from __future__ import annotations

import asyncio
import random
import time

from drogue.core.abstracts import AcquireResult, Algorithm, Storage


class FixedWindowAlgorithm(Algorithm):
    """Fixed Window Counter rate limiting algorithm.

    Simplest algorithm. Counts requests in fixed time windows.
    Has a boundary burst problem: up to 2x limit at window edges.
    Best for: simple use cases, low-memory, analytics.

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
        return f"drogue:fw:{key}:{window_id}"

    def _get_window_id(self, now: float) -> int:
        return int(now / self.window)

    async def acquire(
        self,
        key: str,
        cost: int = 1,
        block: bool = False,
        timeout: float | None = None,
    ) -> AcquireResult:
        max_retries = 5

        for _attempt in range(max_retries):
            now = time.monotonic()
            window_id = self._get_window_id(now)
            storage_key = self._make_key(key, window_id)

            # Read current count and attempt CAS increment
            state = await self.storage.get(storage_key)
            count = state if isinstance(state, int) and state > 0 else 0
            new_count = count + cost

            if new_count <= self.limit:
                # Try to atomically increment (use expected=None for create-if-absent)
                expected = count if count > 0 else None
                if await self.storage.compare_and_swap(
                    storage_key, expected, new_count, self.window * 2
                ):
                    remaining = self.limit - new_count
                    next_window = (window_id + 1) * self.window
                    return AcquireResult(
                        allowed=True,
                        remaining=max(0, remaining),
                        limit=self.limit,
                        reset_at=next_window,
                    )
                # CAS failed — another request modified the counter, retry
                await asyncio.sleep(random.uniform(0, 0.001))
                continue
            else:
                # Over limit — don't increment
                next_window = (window_id + 1) * self.window
                retry_after = next_window - now

                if block and timeout is not None:
                    wait_time = min(retry_after, timeout)
                    await asyncio.sleep(wait_time)
                    continue

                remaining = max(0, self.limit - (new_count - cost))
                return AcquireResult(
                    allowed=False,
                    remaining=max(0, remaining),
                    limit=self.limit,
                    retry_after=retry_after,
                    reset_at=next_window,
                )

        # Exhausted retries — fail closed
        return AcquireResult(
            allowed=False,
            remaining=0,
            limit=self.limit,
            retry_after=0.0,
            reset_at=time.monotonic() + self.window,
        )

    async def peek(self, key: str) -> AcquireResult:
        """Check state without consuming tokens."""
        now = time.monotonic()
        window_id = self._get_window_id(now)
        storage_key = self._make_key(key, window_id)

        count = await self.storage.get(storage_key) or 0
        remaining = max(0, self.limit - count)
        next_window = (window_id + 1) * self.window

        return AcquireResult(
            allowed=remaining > 0,
            remaining=remaining,
            limit=self.limit,
            reset_at=next_window,
        )

    async def reset(self, key: str) -> None:
        now = time.monotonic()
        window_id = self._get_window_id(now)
        await self.storage.delete(self._make_key(key, window_id))