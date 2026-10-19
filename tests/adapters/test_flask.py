"""Tests for the Flask adapter."""
from __future__ import annotations

from flask import Flask

from drogue.adapters.flask import DrogueLimiter
from drogue.core.storage.memory import MemoryStorage


class TestStackedLimits:
    """Stacked @limiter.limit decorators must each count only their own tier."""

    def test_stacked_decorators_single_counted(self) -> None:
        app = Flask(__name__)
        limiter = DrogueLimiter(app, storage=MemoryStorage())

        @app.route("/stacked")
        @limiter.limit("4/minute")
        @limiter.limit("2/minute")
        def stacked():
            return {"ok": True}

        client = app.test_client()
        first = client.get("/stacked")
        second = client.get("/stacked")
        # With the bug each wrapper re-checked the whole rule list, so
        # every tier lost two tokens per request and request 2 was
        # already denied. Single counting keeps both tiers alive until
        # the strict one exhausts.
        assert first.status_code == 200
        assert second.status_code == 200
        third = client.get("/stacked")
        # Now the strict 2/minute tier denies, exactly once.
        assert third.status_code == 429

    def test_non_stacked_decorator_unaffected(self) -> None:
        app = Flask(__name__)
        limiter = DrogueLimiter(app, storage=MemoryStorage())

        @app.route("/single")
        @limiter.limit("3/minute")
        def single():
            return {"ok": True}

        client = app.test_client()
        # Exactly 3 allowed at limit=3: proves no double consumption.
        assert client.get("/single").status_code == 200
        assert client.get("/single").status_code == 200
        assert client.get("/single").status_code == 200
        assert client.get("/single").status_code == 429
