"""Tests for the DRF throttle adapter (settings wiring + LRU cache)."""
from __future__ import annotations

import unittest.mock as mock

from django.test import RequestFactory, SimpleTestCase, override_settings

import drogue.adapters.django.throttle as throttle_mod
from drogue.core.storage.memory import MemoryStorage


def _reset_module_state() -> None:
    throttle_mod._storage = None
    throttle_mod._algorithms.clear()


class TestDrogueStorageSetting(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        _reset_module_state()

    def tearDown(self) -> None:
        _reset_module_state()
        super().tearDown()

    def test_drogue_storage_setting_used(self) -> None:
        storage = MemoryStorage()
        with override_settings(DROGUE_STORAGE=storage):
            assert throttle_mod._get_storage() is storage

    def test_fallback_memory_storage_without_setting(self) -> None:
        assert isinstance(throttle_mod._get_storage(), MemoryStorage)

    def test_setting_wired_through_real_requests(self) -> None:
        storage = MemoryStorage()
        factory = RequestFactory()
        request = factory.get("/api")
        request.user = type("User", (), {"is_authenticated": False})()
        view = type(
            "View",
            (),
            {"throttle_scope": "test", "throttle_rates": {"test": "1/minute"}},
        )()
        throttle = throttle_mod.DrogueThrottle()

        with override_settings(DROGUE_STORAGE=storage):
            assert throttle.allow_request(request, view) is True
            assert throttle_mod._get_storage() is storage
            # The configured storage, not the module fallback, got writes.
            assert len(storage._store) >= 1

            assert throttle.allow_request(request, view) is False
            assert throttle.wait() is not None


class TestAlgorithmCacheLRU(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        _reset_module_state()

    def tearDown(self) -> None:
        _reset_module_state()
        super().tearDown()

    def test_eviction_removes_one_entry_not_all(self) -> None:
        for i in range(throttle_mod._MAX_ALGORITHMS + 10):
            throttle_mod._get_algorithm("5/minute", route_key=f"r{i}")

        # Ten evictions happened, oldest-first, and nothing else was touched.
        assert len(throttle_mod._algorithms) == throttle_mod._MAX_ALGORITHMS
        for i in range(10):
            assert f"r{i}:5/minute" not in throttle_mod._algorithms
        assert "r10:5/minute" in throttle_mod._algorithms
        assert f"r{throttle_mod._MAX_ALGORITHMS + 9}:5/minute" in throttle_mod._algorithms

    def test_eviction_preserves_recently_used_algorithms(self) -> None:
        cap = 3
        with mock.patch.object(throttle_mod, "_MAX_ALGORITHMS", cap):
            algo_first = throttle_mod._get_algorithm("5/minute", route_key="r1")
            throttle_mod._get_algorithm("5/minute", route_key="r2")
            throttle_mod._get_algorithm("5/minute", route_key="r3")
            # Touch r1 so r2 becomes the least-recently-used entry.
            assert throttle_mod._get_algorithm("5/minute", route_key="r1") is algo_first
            throttle_mod._get_algorithm("5/minute", route_key="r4")

            assert "r1:5/minute" in throttle_mod._algorithms
            assert "r2:5/minute" not in throttle_mod._algorithms
            assert "r3:5/minute" in throttle_mod._algorithms
            assert len(throttle_mod._algorithms) == cap

    def test_evicted_entry_recreated_not_reused(self) -> None:
        cap = 2
        with mock.patch.object(throttle_mod, "_MAX_ALGORITHMS", cap):
            orig = throttle_mod._get_algorithm("5/minute", route_key="r1")
            throttle_mod._get_algorithm("5/minute", route_key="r2")
            throttle_mod._get_algorithm("5/minute", route_key="r3")
            recreated = throttle_mod._get_algorithm("5/minute", route_key="r1")
            assert recreated is not orig
