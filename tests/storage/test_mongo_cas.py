"""Tests for MongoDBStorage CAS semantics and UTC datetimes (mocked collection)."""
from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from drogue.core.errors import BackendFailure
from drogue.core.storage.mongo import MongoDBStorage

_RETURN_DOCUMENT = types.SimpleNamespace(BEFORE=-1, AFTER=1)
_PYMONGO_STUB = types.ModuleType("pymongo")
_PYMONGO_STUB.ReturnDocument = _RETURN_DOCUMENT
_ERRORS_STUB = types.ModuleType("pymongo.errors")


class _StubDuplicateKeyError(Exception):
    code = 11000


_ERRORS_STUB.DuplicateKeyError = _StubDuplicateKeyError
_PYMONGO_STUB.errors = _ERRORS_STUB
sys.modules.setdefault("pymongo", _PYMONGO_STUB)
sys.modules.setdefault("pymongo.errors", _ERRORS_STUB)


@pytest.fixture
def collection() -> MagicMock:
    mock = MagicMock()
    mock.find_one_and_update = AsyncMock()
    mock.update_one = AsyncMock()
    mock.find_one = AsyncMock()
    return mock


@pytest.fixture
def storage(collection: MagicMock) -> MongoDBStorage:
    s = MongoDBStorage()
    s._collection = collection
    return s


def _utc() -> datetime:
    return datetime.now(timezone.utc)


class TestCompareAndSwap:
    """Tests for create-if-absent and match-value CAS paths."""

    @pytest.mark.asyncio
    async def test_create_if_absent_fresh_insert(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.find_one_and_update.return_value = None

        assert await storage.compare_and_swap("k", None, 5, 60.0) is True

        collection.find_one_and_update.assert_awaited_once()
        args, kwargs = collection.find_one_and_update.call_args
        assert args[0] == {"key": "k"}
        update = args[1]
        assert set(update) == {"$setOnInsert"}
        assert update["$setOnInsert"]["value"] == 5
        assert isinstance(update["$setOnInsert"]["expiry"], datetime)
        assert update["$setOnInsert"]["expiry"].tzinfo == timezone.utc
        assert kwargs["upsert"] is True
        assert kwargs["return_document"] == _RETURN_DOCUMENT.BEFORE

    @pytest.mark.asyncio
    async def test_create_if_absent_doc_exists_returns_false(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.find_one_and_update.return_value = {
            "key": "k",
            "value": 1,
            "expiry": _utc() + timedelta(seconds=30),
        }

        assert await storage.compare_and_swap("k", None, 5, 60.0) is False

    @pytest.mark.asyncio
    async def test_create_race_duplicate_key_returns_false(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.find_one_and_update.side_effect = _StubDuplicateKeyError("E11000")

        assert await storage.compare_and_swap("k", None, 5, 60.0) is False

    @pytest.mark.asyncio
    async def test_update_matches_expected_value(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        result = MagicMock()
        result.modified_count = 1
        collection.update_one.return_value = result

        assert await storage.compare_and_swap("k", 4, 5, 60.0) is True

        collection.update_one.assert_awaited_once()
        args, _kwargs = collection.update_one.call_args
        assert args[0]["key"] == "k"
        assert args[0]["value"] == 4
        future_expiry = args[0]["$or"][1]["expiry"]["$gt"]
        assert isinstance(future_expiry, datetime)
        assert future_expiry > _utc() - timedelta(seconds=1)
        assert args[1]["$set"]["value"] == 5
        assert isinstance(args[1]["$set"]["expiry"], datetime)

    @pytest.mark.asyncio
    async def test_update_no_modification_returns_false(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        result = MagicMock()
        result.modified_count = 0
        collection.update_one.return_value = result

        assert await storage.compare_and_swap("k", 4, 5, 60.0) is False


class TestDuplicateKeyWrapping:
    """Concurrent upsert races must surface as clean failures."""

    @pytest.mark.asyncio
    async def test_set_wraps_duplicate_key_error(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.update_one.side_effect = _StubDuplicateKeyError("E11000")

        with pytest.raises(BackendFailure):
            await storage.set("k", "v", ttl=60.0)

    @pytest.mark.asyncio
    async def test_set_passes_other_errors_through(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        boom = RuntimeError("boom")
        collection.update_one.side_effect = boom

        with pytest.raises(RuntimeError, match="boom"):
            await storage.set("k", "v", ttl=60.0)


class TestExpiryUsesUtcDatetimes:
    """Expiry must be BSON datetime, so the TTL index actually deletes docs."""

    @pytest.mark.asyncio
    async def test_set_expiry_is_utc_datetime(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.update_one.return_value = MagicMock()

        await storage.set("k", "v", ttl=10.0)

        args = collection.update_one.call_args
        expiry = args.args[1]["$set"]["expiry"]
        assert isinstance(expiry, datetime)
        assert expiry.tzinfo == timezone.utc
        delta = expiry - _utc()
        assert timedelta(seconds=0) < delta <= timedelta(seconds=11)

    @pytest.mark.asyncio
    async def test_get_filters_on_datetime_expiry(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.find_one.return_value = {
            "key": "k",
            "value": 42,
            "expiry": _utc() + timedelta(seconds=30),
        }

        assert await storage.get("k") == 42

        args = collection.find_one.call_args
        future_expiry = args.args[0]["$or"][1]["expiry"]["$gt"]
        assert isinstance(future_expiry, datetime)
        assert future_expiry > _utc() - timedelta(seconds=1)

    @pytest.mark.asyncio
    async def test_get_returns_none_for_expired(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.find_one.return_value = None

        assert await storage.get("k") is None

    @pytest.mark.asyncio
    async def test_incr_expires_as_datetime(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.find_one_and_update.return_value = {
            "key": "k", "value": 3, "expiry": _utc() + timedelta(seconds=60)
        }

        assert await storage.incr("k", window=60.0, amount=1) == 3

        args = collection.find_one_and_update.call_args
        assert isinstance(
            args.args[1]["$setOnInsert"]["expiry"], datetime
        )

    @pytest.mark.asyncio
    async def test_ttl_returns_seconds_from_datetime(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.find_one.return_value = {
            "key": "k",
            "value": 1,
            "expiry": _utc() + timedelta(seconds=7),
        }

        result = await storage.ttl("k")

        assert 6.0 <= result <= 7.5

    @pytest.mark.asyncio
    async def test_increment_by_returns_datetime_seconds(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.find_one_and_update.return_value = {
            "key": "k", "value": 2, "expiry": _utc() + timedelta(seconds=9)
        }

        count, remaining = await storage.increment_by("k", 2, window=60.0)

        assert count == 2
        assert 8.0 <= remaining <= 9.5

    @pytest.mark.asyncio
    async def test_exists_filters_on_datetime_expiry(
        self, storage: MongoDBStorage, collection: MagicMock
    ) -> None:
        collection.count_documents = AsyncMock(return_value=1)

        exists = await storage.exists("k")

        assert exists is True
        trigger = collection.count_documents.call_args
        future_expiry = trigger.args[0]["$or"][1]["expiry"]["$gt"]
        assert isinstance(future_expiry, datetime)
