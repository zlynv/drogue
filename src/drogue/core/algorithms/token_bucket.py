from __future__ import annotations

import asyncio
import random
import time

from drogue.core.abstracts import AcquireResult, Algorithm, Storage
from drogue.core.errors import BackendFailure


class TokenBucketAlgorithm(Algorithm):
    """Token Bucket rate limiting algorithm.

    Allows bursts up to bucket capacity, then refills at a steady rate.
    Best for: APIs that allow occasional bursts but enforce average rate.

    How it works:
    - Bucket holds up to `limit` tokens
    - Tokens are consumed on each request
    - Tokens refill at `limit / window` tokens per second
    - If no tokens available, request is denied (or blocked)

    Redis Lua script for atomic operations:
    ```lua
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local requested = tonumber(ARGV[4])
    local ttl = tonumber(ARGV[5])

    local bucket = redis.call('hmget', key, 'tokens', 'last_refill')
    local tokens = tonumber(bucket[1]) or capacity
    local last_refill = tonumber(bucket[2]) or now

    -- Refill tokens
    local elapsed = now - last_refill
    local new_tokens = math.min(capacity, tokens + elapsed * refill_rate)

    if new_tokens >= requested then
        new_tokens = new_tokens - requested
        redis.call('hmset', key, 'tokens', new_tokens, 'last_refill', now)
        redis.call('expire', key, ttl)
        return {1, math.floor(new_tokens), 0}
    else
        local wait_time = (requested - new_tokens) / refill_rate
        return {0, math.floor(new_tokens), wait_time}
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
        self.refill_rate = limit / window  # tokens per second

    def _make_key(self, key: str) -> str:
        return f"drogue:tb:{key}"

    def _time_to_full(self, tokens: float) -> float:
        """Time in seconds until bucket is full."""
        if tokens >= self.limit:
            return 0.0
        return (self.limit - tokens) / self.refill_rate

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
                message=f"Token bucket storage error: {e}",
                backend=self.storage.__class__.__name__,
                original_error=e,
            ) from e

    async def _acquire_non_blocking(
        self, storage_key: str, cost: int, now: float
    ) -> AcquireResult:
        """Try to acquire tokens without blocking.

        Uses compare_and_swap for thread-safe read-modify-write.

        Storage format: (remaining_tokens: float, last_refill_time: float)
        This matches the Redis Lua script pattern and avoids fractional
        truncation bugs that occur when deriving elapsed time from TTL.
        """
        max_retries = 3
        for _attempt in range(max_retries):
            state = await self.storage.get(storage_key)

            if state is None:
                # First request: initialize atomically (CAS against absent key)
                # so concurrent first requests can't each over-admit.
                remaining = self.limit - cost
                if remaining < 0:
                    return AcquireResult(
                        allowed=False,
                        remaining=self.limit,
                        limit=self.limit,
                        retry_after=abs(remaining) / self.refill_rate,
                    )
                new_state: tuple[float, float] = (float(remaining), now)
                if await self.storage.compare_and_swap(
                    storage_key, None, new_state, self.window
                ):
                    return AcquireResult(
                        allowed=True,
                        remaining=remaining,
                        limit=self.limit,
                        reset_at=time.time() + self._time_to_full(remaining),
                    )
                # Another request initialized the bucket first; retry with backoff
                await asyncio.sleep(random.uniform(0, 0.001))
                continue

            # Unpack stored state
            stored_tokens: float
            last_refill: float
            try:
                stored_tokens, last_refill = state
            except (TypeError, ValueError):
                continue

            # Refill based on elapsed time since last refill
            elapsed = max(0.0, now - last_refill)
            tokens = min(self.limit, stored_tokens + elapsed * self.refill_rate)

            if tokens >= cost:
                new_tokens = tokens - cost
                new_state: tuple[float, float] = (new_tokens, now)
                # CAS: only write if state hasn't changed
                if await self.storage.compare_and_swap(
                    storage_key, state, new_state, self.window
                ):
                    time_to_full = self._time_to_full(new_tokens)
                    return AcquireResult(
                        allowed=True,
                        remaining=int(new_tokens),
                        limit=self.limit,
                        reset_at=time.time() + time_to_full,
                    )
                # CAS failed, retry with backoff
                await asyncio.sleep(random.uniform(0, 0.001))
                continue
            else:
                wait_time = (cost - tokens) / self.refill_rate
                return AcquireResult(
                    allowed=False,
                    remaining=int(tokens),
                    limit=self.limit,
                    retry_after=wait_time,
                    reset_at=time.time() + wait_time,
                )

        # Exhausted retries — fail closed
        return AcquireResult(
            allowed=False,
            remaining=0,
            limit=self.limit,
            retry_after=0.0,
        )

    async def _acquire_blocking(
        self, storage_key: str, cost: int, timeout: float | None, now: float
    ) -> AcquireResult:
        """Try to acquire tokens, blocking until available or timeout."""
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

            # Check again soon (don't sleep the full retry_after)
            await asyncio.sleep(min(remaining_wait, 0.01))

    async def peek(self, key: str) -> AcquireResult:
        """Check state without consuming tokens."""
        storage_key = self._make_key(key)
        state = await self.storage.get(storage_key)
        now = time.monotonic()

        if state is None:
            return AcquireResult(
                allowed=True,
                remaining=self.limit,
                limit=self.limit,
                reset_at=time.time(),
            )

        try:
            stored_tokens, last_refill = state
        except (TypeError, ValueError):
            return AcquireResult(
                allowed=True,
                remaining=self.limit,
                limit=self.limit,
                reset_at=time.time(),
            )

        elapsed = max(0.0, now - last_refill)
        tokens = min(self.limit, stored_tokens + elapsed * self.refill_rate)

        time_to_full = self._time_to_full(tokens)
        return AcquireResult(
            allowed=tokens >= 1,
            remaining=int(tokens),
            limit=self.limit,
            reset_at=time.time() + time_to_full,
        )

    async def reset(self, key: str) -> None:
        storage_key = self._make_key(key)
        await self.storage.delete(storage_key)