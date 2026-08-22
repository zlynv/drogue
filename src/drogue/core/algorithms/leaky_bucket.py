from __future__ import annotations

import asyncio
import time

from drogue.core.abstracts import AcquireResult, Algorithm, Storage
from drogue.core.errors import BackendFailure


class LeakyBucketAlgorithm(Algorithm):
    """Leaky Bucket rate limiting algorithm.

    Smooths traffic by queuing requests and processing them at a fixed rate.
    Best for: APIs requiring perfectly smooth traffic with no bursts.

    How it works:
    - Bucket has fixed capacity (limit)
    - Requests fill the bucket
    - Bucket leaks at a constant rate (limit / window per second)
    - If bucket is full, request is denied (or blocked)
    - Uses timestamps to calculate how much has leaked

    This is different from Token Bucket:
    - Token Bucket allows bursts up to capacity
    - Leaky Bucket processes at constant rate (smoother)

    Used by: NGINX, HAProxy, AWS WAF rate-based rules

    Redis Lua script for atomic operations:
    ```lua
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local leak_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local ttl = tonumber(ARGV[4])

    local bucket = redis.call('hmget', key, 'water', 'last_leak')
    local water = tonumber(bucket[1]) or 0
    local last_leak = tonumber(bucket[2]) or now

    -- Leak water based on elapsed time
    local elapsed = now - last_leak
    local leaked = elapsed * leak_rate
    water = math.max(0, water - leaked)

    if water < capacity then
        water = water + 1
        redis.call('hmset', key, 'water', water, 'last_leak', now)
        redis.call('expire', key, ttl)
        return {1, capacity - math.floor(water), 0}
    else
        local wait_time = (1 - (capacity - water)) / leak_rate
        return {0, 0, wait_time}
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
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        self.limit = limit
        self.window = window
        self.leak_rate = limit / window  # requests leaked per second

    def _make_key(self, key: str) -> str:
        return f"drogue:lb:{key}"

    async def acquire(
        self,
        key: str,
        cost: int = 1,
        block: bool = False,
        timeout: float | None = None,
    ) -> AcquireResult:
        storage_key = self._make_key(key)
        now = time.monotonic()

        try:
            if block:
                return await self._acquire_blocking(storage_key, cost, timeout, now)
            else:
                return await self._acquire_non_blocking(storage_key, cost, now)
        except BackendFailure:
            raise
        except Exception as e:
            raise BackendFailure(
                message=f"Leaky bucket storage error: {e}",
                backend=self.storage.__class__.__name__,
                original_error=e,
            ) from e

    async def _acquire_non_blocking(
        self, storage_key: str, cost: int, now: float
    ) -> AcquireResult:
        """Try to acquire without blocking using CAS."""
        max_retries = 3
        for _attempt in range(max_retries):
            state = await self.storage.get(storage_key)

            if state is None:
                # First request: bucket is empty. Initialize atomically
                # (CAS against absent key) so concurrent first requests
                # can't each over-admit.
                water = float(cost)
                if water > self.limit:
                    wait_time = (water - self.limit) / self.leak_rate
                    return AcquireResult(
                        allowed=False,
                        remaining=0,
                        limit=self.limit,
                        retry_after=wait_time,
                    )
                if await self.storage.compare_and_swap(
                    storage_key, None, (water, now), self.window
                ):
                    return AcquireResult(
                        allowed=True,
                        remaining=self.limit - int(water),
                        limit=self.limit,
                        reset_at=now + self.window,
                    )
                # Another request initialized the bucket first; retry
                continue

            # Unpack stored state
            stored_water: float
            last_leak: float
            try:
                stored_water, last_leak = state
            except (TypeError, ValueError):
                continue

            # Leak based on elapsed time
            elapsed = max(0.0, now - last_leak)
            leaked = elapsed * self.leak_rate
            water = max(0.0, stored_water - leaked)

            # Add new request
            new_water = water + cost

            if new_water <= self.limit:
                new_state: tuple[float, float] = (new_water, now)
                if await self.storage.compare_and_swap(
                    storage_key, state, new_state, self.window
                ):
                    remaining = max(0, self.limit - int(new_water))
                    return AcquireResult(
                        allowed=True,
                        remaining=remaining,
                        limit=self.limit,
                        reset_at=now + self.window,
                    )
                continue
            else:
                # Bucket would overflow
                wait_time = (new_water - self.limit) / self.leak_rate
                return AcquireResult(
                    allowed=False,
                    remaining=max(0, self.limit - int(water)),
                    limit=self.limit,
                    retry_after=wait_time,
                    reset_at=now + self.window,
                )

        return AcquireResult(
            allowed=False,
            remaining=0,
            limit=self.limit,
            retry_after=0.0,
        )

    async def _acquire_blocking(
        self, storage_key: str, cost: int, timeout: float | None, now: float
    ) -> AcquireResult:
        """Try to acquire, blocking until available or timeout."""
        start = time.monotonic()
        max_wait = timeout or float("inf")

        while True:
            result = await self._acquire_non_blocking(storage_key, cost, time.monotonic())
            if result.allowed:
                return result

            if result.retry_after is None:
                return result

            elapsed = time.monotonic() - start
            remaining_wait = min(result.retry_after, max_wait - elapsed)

            if remaining_wait <= 0:
                return result

            await asyncio.sleep(min(remaining_wait, 0.01))

    async def peek(self, key: str) -> AcquireResult:
        """Check state without consuming."""
        storage_key = self._make_key(key)
        state = await self.storage.get(storage_key)
        now = time.monotonic()

        if state is None:
            return AcquireResult(
                allowed=True,
                remaining=self.limit,
                limit=self.limit,
                reset_at=now + self.window,
            )

        try:
            stored_water, last_leak = state
        except (TypeError, ValueError):
            return AcquireResult(
                allowed=True,
                remaining=self.limit,
                limit=self.limit,
                reset_at=now + self.window,
            )

        elapsed = max(0.0, now - last_leak)
        leaked = elapsed * self.leak_rate
        water = max(0.0, stored_water - leaked)
        remaining = max(0, self.limit - int(water))

        return AcquireResult(
            allowed=remaining > 0,
            remaining=remaining,
            limit=self.limit,
            reset_at=now + max(0.0, self.window - elapsed),
        )

    async def reset(self, key: str) -> None:
        storage_key = self._make_key(key)
        await self.storage.delete(storage_key)
