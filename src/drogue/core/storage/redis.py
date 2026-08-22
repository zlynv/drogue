"""Redis storage backend for distributed rate limiting.

Provides atomic operations using Redis commands, supporting
multi-process and multi-server deployments.
"""
from __future__ import annotations

import json
from typing import Any

from drogue.core.abstracts import Storage

# Sentinel used in compare_and_swap to mean "key must not exist yet"
_NONE_SENTINEL = "__drogue_none__"


def _serialize(value: Any) -> str:
    """Serialize a value for storage.

    Ints are stored as plain integers (backwards compatible with INCR-based
    counters). Floats, tuples, and other values are stored as JSON so that
    algorithm state like (tokens, last_refill) round-trips losslessly.
    """
    if isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return json.dumps(value, separators=(",", ":"))


def _deserialize(raw: str | None) -> Any:
    """Deserialize a stored value.

    Tries int, then float, then JSON. Returns None for missing keys.
    """
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return json.loads(raw)


class RedisStorage(Storage):
    """Redis-backed storage for distributed rate limiting.

    Uses Redis atomic operations (INCR, EXPIRE, SET with TTL)
    for thread-safe and process-safe rate limit state.

    Usage:
        storage = RedisStorage(url="redis://localhost:6379")
        await storage.initialize()
        count = await storage.incr("rate:user1", window=60.0)
        await storage.close()

    Requirements:
        pip install "redis[hiredis]>=5.0.0"
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        prefix: str = "drogue:",
        **kwargs: Any,
    ) -> None:
        self.url = url
        self.prefix = prefix
        self._redis: Any = None
        self._kwargs = kwargs

    def _key(self, key: str) -> str:
        """Prefix key with namespace."""
        return f"{self.prefix}{key}"

    async def initialize(self) -> None:
        """Connect to Redis."""
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise ImportError(
                "Redis storage requires redis[hiredis]. "
                "Install with: pip install drogue[redis]"
            ) from exc
        self._redis = aioredis.from_url(
            self.url,
            decode_responses=True,
            **self._kwargs,
        )

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def incr(self, key: str, window: float, amount: int = 1) -> int:
        """Increment counter with sliding window expiry."""
        rkey = self._key(key)
        pipe = self._redis.pipeline()
        pipe.incr(rkey, amount)
        pipe.expire(rkey, int(window) + 1)
        results = await pipe.execute()
        return results[0]

    async def get(self, key: str) -> Any:
        """Get current value for key (int, float, or deserialized JSON)."""
        val = await self._redis.get(self._key(key))
        return _deserialize(val)

    async def set(self, key: str, value: Any, ttl: float) -> None:
        """Set value with TTL in seconds."""
        await self._redis.set(self._key(key), _serialize(value), ex=int(ttl) + 1)

    async def delete(self, key: str) -> None:
        """Delete key."""
        await self._redis.delete(self._key(key))

    async def expire(self, key: str, ttl: float) -> None:
        """Set expiry on existing key."""
        await self._redis.expire(self._key(key), int(ttl) + 1)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self._redis.exists(self._key(key)) > 0

    async def ttl(self, key: str) -> float:
        """Get remaining TTL for key."""
        val = await self._redis.ttl(self._key(key))
        if val == -2:
            return -2.0  # not found
        if val == -1:
            return -1.0  # no expiry
        return float(val)

    async def increment_by(
        self, key: str, amount: int, window: float
    ) -> tuple[int, float]:
        """Atomically increment and get (new_count, ttl_remaining)."""
        rkey = self._key(key)
        pipe = self._redis.pipeline()
        pipe.incrby(rkey, amount)
        pipe.expire(rkey, int(window) + 1)
        pipe.ttl(rkey)
        results = await pipe.execute()
        count = results[0]
        ttl_remaining = float(results[2]) if results[2] >= 0 else 0.0
        return count, ttl_remaining

    async def compare_and_swap(
        self, key: str, expected: Any, new_value: Any, ttl: float
    ) -> bool:
        """Atomically swap value only if current value matches expected.

        Uses a Lua script for atomicity in Redis. Values are compared as
        serialized strings (exact match), so float/tuple state round-trips
        correctly.

        If expected is None, the swap only succeeds when the key does NOT
        exist yet (create-if-absent), enabling race-free initialization.
        """
        script = """
        local current = redis.call('GET', KEYS[1])
        local expected = ARGV[1]
        if expected == '__drogue_none__' then
            if current ~= false then
                return 0
            end
        else
            if current == false then
                return 0
            end
            if current ~= expected then
                return 0
            end
        end
        redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
        return 1
        """
        rkey = self._key(key)
        expected_raw = _NONE_SENTINEL if expected is None else _serialize(expected)
        result = await self._redis.eval(
            script,
            1,
            rkey,
            expected_raw,
            _serialize(new_value),
            int(ttl) + 1,
        )
        return result == 1

    async def eval_script(
        self, script: str, keys: list[str], args: list[str | int]
    ) -> Any:
        """Execute a Lua script atomically."""
        prefixed_keys = [self._key(k) for k in keys]
        return await self._redis.eval(script, len(prefixed_keys), *prefixed_keys, *args)
