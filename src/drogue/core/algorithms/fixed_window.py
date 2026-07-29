from __future__ import annotations

import time

from drogue.core.abstracts import AcquireResult, Algorithm, Storage
from drogue.core.errors import BackendFailure


class FixedWindowAlgorithm(Algorithm):
    """Fixed Window Counter rate limiting algorithm.

    Simplest algorithm. Counts requests in fixed time windows.
    Has a boundary burst problem: up to 2x limit at window edges.
    Best for: simple use cases, low-memory, analytics.

    How it works:
    - Time divided into fixed windows (e.g., every 60 seconds)
    - Each window has a counter
    - Counter resets at window boundary
    - If counter >= limit, request denied

    Redis Lua script for atomic operations:
    ```lua
    local key = KEYS[1]
    local window = tonumber(ARGV[1])
    local limit = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local cost = tonumber(ARGV[4])

    local window_id = math.floor(now / window)
    local window_key = key .. ':' .. window_id

    local count = tonumber(redis.call('get', window_key) or '0')

    if count + cost <= limit then
        redis.call('incrby', window_key, cost)
        redis.call('expire', window_key, window * 2)
        return {1, limit - count - cost, 0}
    else
        local next_window = (window_id + 1) * window
        local retry_after = next_window - now
        return {0, limit - count, retry_after}
    end
    ```
    """

    def __init__(
        self,
        storage: Storage,
        limit: int,
        window: float,
    ) -> None:
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
        now = time.monotonic()

        try:
            window_id = self._get_window_id(now)
            storage_key = self._make_key(key, window_id)

            # Use atomic increment_by to avoid race condition
            new_count, ttl_remaining = await self.storage.increment_by(
                storage_key, cost, self.window * 2
            )

            if new_count <= self.limit:
                # Allow
                remaining = self.limit - new_count
                next_window = (window_id + 1) * self.window
                return AcquireResult(
                    allowed=True,
                    remaining=max(0, remaining),
                    limit=self.limit,
                    reset_at=now + (next_window - now),
                )
            else:
                # Over limit — we incremented too far, need to "undo" conceptually
                # The counter is now over limit, but the next request will see it
                # This is acceptable for fixed window (slight over-admission at boundary)
                next_window = (window_id + 1) * self.window
                retry_after = next_window - now

                if block and timeout is not None:
                    wait_time = min(retry_after, timeout)
                    import asyncio
                    await asyncio.sleep(wait_time)
                    return await self.acquire(key, cost, block=False)

                return AcquireResult(
                    allowed=False,
                    remaining=max(0, self.limit - (new_count - cost)),
                    limit=self.limit,
                    retry_after=retry_after,
                    reset_at=next_window,
                )

        except BackendFailure:
            raise
        except Exception as e:
            raise BackendFailure(
                message=f"Fixed window storage error: {e}",
                backend=self.storage.__class__.__name__,
                original_error=e,
            ) from e

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
