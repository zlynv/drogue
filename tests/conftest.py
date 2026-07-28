"""Shared test fixtures for drogue."""
from __future__ import annotations

import pytest

from drogue.core.algorithms.fixed_window import FixedWindowAlgorithm
from drogue.core.algorithms.sliding_window import SlidingWindowAlgorithm
from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
from drogue.core.storage.memory import MemoryStorage


@pytest.fixture
def memory_storage() -> MemoryStorage:
    return MemoryStorage()


@pytest.fixture
def token_bucket(memory_storage: MemoryStorage) -> TokenBucketAlgorithm:
    return TokenBucketAlgorithm(storage=memory_storage, limit=10, window=1.0)


@pytest.fixture
def sliding_window(memory_storage: MemoryStorage) -> SlidingWindowAlgorithm:
    return SlidingWindowAlgorithm(storage=memory_storage, limit=10, window=1.0)


@pytest.fixture
def fixed_window(memory_storage: MemoryStorage) -> FixedWindowAlgorithm:
    return FixedWindowAlgorithm(storage=memory_storage, limit=10, window=1.0)
