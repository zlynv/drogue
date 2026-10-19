from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from drogue.core.abstracts import Storage
from drogue.core.errors import BackendFailure


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_duplicate_key_error(exc: Exception) -> bool:
    """Identify pymongo DuplicateKeyError without importing pymongo eagerly."""
    return getattr(exc, "code", None) == 11000 or type(exc).__name__ == "DuplicateKeyError"


def _return_document_before() -> Any:
    from pymongo import ReturnDocument

    return ReturnDocument.BEFORE


class MongoDBStorage(Storage):
    """MongoDB storage backend for rate limiting.

    Uses MongoDB's atomic operations for thread-safe rate limiting.
    Good for: Applications already using MongoDB, multi-worker deployments.

    Requires: pymongo (pip install drogue[mongodb])

    Storage format:
    - Collection: drogue_rate_limits
    - Document: { key: str, value: Any, expiry: datetime | None }
    """

    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        database: str = "drogue",
        collection: str = "rate_limits",
    ) -> None:
        self.uri = uri
        self.database_name = database
        self.collection_name = collection
        self._client: Any = None
        self._db: Any = None
        self._collection: Any = None

    async def initialize(self) -> None:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except ImportError as exc:
            raise ImportError(
                "motor is required for MongoDB storage. "
                "Install with: pip install drogue[mongodb]"
            ) from exc

        self._client = AsyncIOMotorClient(self.uri)
        self._db = self._client[self.database_name]
        self._collection = self._db[self.collection_name]

        # Create TTL index for automatic expiry
        await self._collection.create_index("expiry", expireAfterSeconds=0)
        # Create unique index on key
        await self._collection.create_index("key", unique=True)

    async def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def _cleanup_expired_sync(self) -> None:
        """Remove expired keys (called lazily)."""
        # MongoDB TTL index handles this automatically
        pass

    async def incr(self, key: str, window: float, amount: int = 1) -> int:
        now = _utcnow()
        result = await self._collection.find_one_and_update(
            {"key": key, "$or": [{"expiry": None}, {"expiry": {"$gt": now}}]},
            {
                "$inc": {"value": amount},
                "$setOnInsert": {"expiry": now + timedelta(seconds=window)},
            },
            upsert=True,
            return_document=True,
        )
        return result["value"] if result else amount

    async def get(self, key: str) -> Any:
        now = _utcnow()
        doc = await self._collection.find_one(
            {"key": key, "$or": [{"expiry": None}, {"expiry": {"$gt": now}}]}
        )
        if doc is None:
            return None
        return doc["value"]

    async def set(self, key: str, value: Any, ttl: float) -> None:
        now = _utcnow()
        try:
            await self._collection.update_one(
                {"key": key},
                {"$set": {"value": value, "expiry": now + timedelta(seconds=ttl)}},
                upsert=True,
            )
        except Exception as exc:
            if _is_duplicate_key_error(exc):
                raise BackendFailure(
                    message=f"MongoDB duplicate key race while setting {key}: {exc}",
                    backend=self.__class__.__name__,
                    original_error=exc,
                ) from exc
            raise

    async def delete(self, key: str) -> None:
        await self._collection.delete_one({"key": key})

    async def expire(self, key: str, ttl: float) -> None:
        now = _utcnow()
        await self._collection.update_one(
            {"key": key},
            {"$set": {"expiry": now + timedelta(seconds=ttl)}},
        )

    async def exists(self, key: str) -> bool:
        now = _utcnow()
        count = await self._collection.count_documents(
            {"key": key, "$or": [{"expiry": None}, {"expiry": {"$gt": now}}]},
            limit=1,
        )
        return count > 0

    async def ttl(self, key: str) -> float:
        now = _utcnow()
        doc = await self._collection.find_one(
            {"key": key, "$or": [{"expiry": None}, {"expiry": {"$gt": now}}]}
        )
        if doc is None:
            return -2.0
        expiry = doc.get("expiry")
        if expiry is None:
            return -1.0
        return max(0.0, (expiry - now).total_seconds())

    async def increment_by(
        self, key: str, amount: int, window: float
    ) -> tuple[int, float]:
        now = _utcnow()
        result = await self._collection.find_one_and_update(
            {"key": key, "$or": [{"expiry": None}, {"expiry": {"$gt": now}}]},
            {
                "$inc": {"value": amount},
                "$setOnInsert": {"expiry": now + timedelta(seconds=window)},
            },
            upsert=True,
            return_document=True,
        )
        new_count = result["value"] if result else amount
        expiry = result.get("expiry") if result else now + timedelta(seconds=window)
        remaining = (
            max(0.0, (expiry - now).total_seconds()) if expiry else window
        )
        return new_count, remaining

    async def compare_and_swap(
        self, key: str, expected: Any, new_value: Any, ttl: float
    ) -> bool:
        now = _utcnow()
        expiry = now + timedelta(seconds=ttl)
        if expected is None:
            # Create-if-absent: succeed only when no document was inserted
            # yet (fresh upsert). A pre-existing (or raced) document returns
            # the matched document instead of None.
            try:
                result = await self._collection.find_one_and_update(
                    {"key": key},
                    {"$setOnInsert": {"value": new_value, "expiry": expiry}},
                    upsert=True,
                    return_document=_return_document_before(),
                )
            except Exception as exc:
                if _is_duplicate_key_error(exc):
                    return False
                raise
            return result is None
        try:
            result = await self._collection.update_one(
                {
                    "key": key,
                    "value": expected,
                    "$or": [{"expiry": None}, {"expiry": {"$gt": now}}],
                },
                {"$set": {"value": new_value, "expiry": expiry}},
            )
        except Exception as exc:
            if _is_duplicate_key_error(exc):
                return False
            raise
        return result.modified_count > 0

    def __repr__(self) -> str:
        return f"MongoDBStorage(uri={self.uri}, db={self.database_name})"
