from __future__ import annotations

import asyncio
import random
import time

from drogue.core.abstracts import AcquireResult, Algorithm, Storage
from drogue.core.errors import BackendFailure


class GCRAAlgorithm(Algorithm):
    """Generic Cell Rate Algorithm (GCRA).

    Smooth, cell-based rate limiting that evenly spaces requests.
    Best for: APIs requiring smooth traffic with no bursts.

    How it works:
    - Each request has a theoretical arrival time (TAT)
    - TAT = max(previous_TAT, now) + emission_interval
    - If TAT - now <= 0, request is allowed
    - emission_interval = window / limit (time between allowed requests)

    GCRA is used by telecom systems (ATM networks) and is the basis for
    IETF RFC 2697 (Single Rate Three Color Marker).
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
        self.emission_interval = window / limit  # time between allowed requests
        self.burst = limit  # burst capacity

    def _make_key(self, key: str) -> str:
        return f"drogue:gcra:{key}"

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
                message=f"GCRA storage error: {e}",
                backend=self.storage.__class__.__name__,
                original_error=e,
            ) from e

    async def _acquire_non_blocking(
        self, storage_key: str, cost: int, now: float
    ) -> AcquireResult:
        """Try to acquire without blocking using CAS."""
        max_retries = 3
        for _attempt in range(max_retries):
            tat = await self.storage.get(storage_key)

            if tat is None:
                if cost > self.burst:
                    # Impossible to ever satisfy: deny without storing state
                    return AcquireResult(
                        allowed=False,
                        remaining=self.limit,
                        limit=self.limit,
                        retry_after=0.0,
                    )
                new_tat = now + cost * self.emission_interval
                # Initialize atomically (CAS against absent key) so
                # concurrent first requests can't each over-admit.
                if await self.storage.compare_and_swap(
                    storage_key, None, float(new_tat), self.window
                ):
                    return AcquireResult(
                        allowed=True,
                        remaining=self.limit - cost,
                        limit=self.limit,
                        reset_at=now,  # allowed immediately
                    )
                # Another request initialized state; retry
                continue

            # tat is the previous theoretical arrival time
            try:
                prev_tat = float(tat)
            except (TypeError, ValueError):
                continue

            new_tat = max(prev_tat, now) + cost * self.emission_interval
            allow_at = new_tat - self.burst * self.emission_interval

            if allow_at <= now:
                # CAS: only write if tat hasn't changed
                if await self.storage.compare_and_swap(
                    storage_key, prev_tat, new_tat, self.window
                ):
                    # Remaining = how many more requests can fit before hitting burst limit
                    # This is the number of emission_intervals between now and the burst boundary
                    remaining = max(0, int((self.burst * self.emission_interval - (new_tat - now)) / self.emission_interval))
                    return AcquireResult(
                        allowed=True,
                        remaining=min(remaining, self.limit - cost),
                        limit=self.limit,
                        reset_at=allow_at,  # when next request is allowed
                    )
                # CAS failed — another request modified the TAT, retry
                await asyncio.sleep(random.uniform(0, 0.001))
                continue
            else:
                retry_after = allow_at - now
                return AcquireResult(
                    allowed=False,
                    remaining=0,
                    limit=self.limit,
                    retry_after=retry_after,
                    reset_at=allow_at,  # when request will be allowed
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
        tat = await self.storage.get(storage_key)
        now = time.monotonic()

        if tat is None:
            return AcquireResult(
                allowed=True,
                remaining=self.limit,
                limit=self.limit,
                reset_at=now,
            )

        try:
            prev_tat = float(tat)
        except (TypeError, ValueError):
            return AcquireResult(
                allowed=True,
                remaining=self.limit,
                limit=self.limit,
                reset_at=now,
            )

        new_tat = max(prev_tat, now) + self.emission_interval
        allow_at = new_tat - self.burst * self.emission_interval
        remaining = max(0, int((self.burst * self.emission_interval - (new_tat - now)) / self.emission_interval))

        return AcquireResult(
            allowed=allow_at <= now,
            remaining=min(remaining, self.limit),
            limit=self.limit,
            reset_at=allow_at,
        )

    async def reset(self, key: str) -> None:
        storage_key = self._make_key(key)
        await self.storage.delete(storage_key)