from __future__ import annotations

import time

from drogue.core.abstracts import AcquireResult, Algorithm, Storage
from drogue.core.errors import BackendFailure


class SlidingWindowAlgorithm(Algorithm):
    """Sliding Window Counter rate limiting algorithm.

    O(1) memory per key. More accurate than Fixed Window, avoids the
    boundary burst problem. Best for: distributed systems, general APIs.

    How it works:
    - Two consecutive windows are weighted: previous window's count ×
      overlap_ratio + current window's count
    - overlap_ratio = (window_size - elapsed_in_current_window) / window_size
    - This smooths the transition between windows

    Redis Lua script for atomic operations:
    ```lua
    local key_prefix = KEYS[1]
    local window = tonumber(ARGV[1])
    local limit = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local cost = tonumber(ARGV[4])

    local current_window = math.floor(now / window)
    local previous_window = current_window - 1
    local elapsed = now - (current_window * window)
    local weight = (window - elapsed) / window

    local prev_key = key_prefix .. ':' .. previous_window
    local curr_key = key_prefix .. ':' .. current_window

    local prev_count = tonumber(redis.call('get', prev_key) or '0')
    local curr_count = tonumber(redis.call('get', curr_key) or '0')

    local estimated = prev_count * weight + curr_count

    if estimated + cost <= limit then
        redis.call('incrby', curr_key, cost)
        redis.call('expire', curr_key, window * 2)
        return {1, math.floor(limit - estimated - cost)}
    else
        local retry_after = window - elapsed
        return {0, math.floor(limit - estimated), retry_after}
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
        return f"drogue:sw:{key}:{window_id}"

    def _get_window_id(self, now: float) -> int:
        return int(now / self.window)

    def _get_elapsed(self, now: float) -> float:
        return now - (self._get_window_id(now) * self.window)

    async def acquire(
        self,
        key: str,
        cost: int = 1,
        block: bool = False,
        timeout: float | None = None,
    ) -> AcquireResult:
        now = time.monotonic()

        try:
            current_window = self._get_window_id(now)
            previous_window = current_window - 1
            elapsed = self._get_elapsed(now)
            weight = (self.window - elapsed) / self.window

            # Get previous window count (read-only, no race)
            prev_key = self._make_key(key, previous_window)
            curr_key = self._make_key(key, current_window)

            prev_count = await self.storage.get(prev_key) or 0

            # Atomically increment current window to reserve tokens
            new_curr_count, _ = await self.storage.increment_by(
                curr_key, cost, self.window * 2
            )

            # Weighted estimate uses the OLD current count (before our increment)
            old_curr_count = new_curr_count - cost
            estimated = prev_count * weight + old_curr_count

            if estimated + cost <= self.limit:
                # Allow: we already incremented
                remaining = int(self.limit - estimated - cost)
                return AcquireResult(
                    allowed=True,
                    remaining=max(0, remaining),
                    limit=self.limit,
                    reset_at=now + (self.window - elapsed),
                )
            else:
                # Deny: decrement what we incremented (undo)
                await self.storage.increment_by(curr_key, -cost, self.window * 2)
                retry_after = self.window - elapsed
                if block and timeout is not None:
                    await self._async_sleep(min(retry_after, timeout))
                    return await self.acquire(key, cost, block=False)

                return AcquireResult(
                    allowed=False,
                    remaining=max(0, int(self.limit - estimated)),
                    limit=self.limit,
                    retry_after=retry_after,
                    reset_at=now + retry_after,
                )

        except BackendFailure:
            raise
        except Exception as e:
            raise BackendFailure(
                message=f"Sliding window storage error: {e}",
                backend=self.storage.__class__.__name__,
                original_error=e,
            ) from e

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
            reset_at=now + (self.window - elapsed),
        )

    async def reset(self, key: str) -> None:
        now = time.monotonic()
        current_window = self._get_window_id(now)
        previous_window = current_window - 1

        await self.storage.delete(self._make_key(key, current_window))
        await self.storage.delete(self._make_key(key, previous_window))

    async def _async_sleep(self, seconds: float) -> None:
        """Async sleep wrapper."""
        import asyncio
        await asyncio.sleep(seconds)
