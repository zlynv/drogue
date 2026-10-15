"""Tests for auto-wired defenses in the FastAPI adapter.

Covers config-driven pipeline auto-building, honeypot traps, trust
limit rewards, probe-driven blocking, session jitter, and
detect-only sentinel scoring over HTTP.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.config import DrogueConfig
from drogue.core.storage.memory import MemoryStorage
from drogue.defense.randomizer import HoneypotManager
from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.pipeline import ProtectionPipeline


def make_app(config: DrogueConfig, pipeline=None) -> tuple[FastAPI, DrogueLimiter]:
    app = FastAPI()
    limiter = DrogueLimiter(
        app, storage=MemoryStorage(), config=config, pipeline=pipeline
    )
    return app, limiter


class TestAutoBuiltPipeline:
    def test_no_flags_no_pipeline(self) -> None:
        _, limiter = make_app(DrogueConfig())
        assert limiter.get_pipeline() is None

    def test_flags_build_pipeline(self) -> None:
        _, limiter = make_app(DrogueConfig(probes_enabled=True))
        pipeline = limiter.get_pipeline()
        assert isinstance(pipeline, ProtectionPipeline)
        assert pipeline.probes is not None
        assert pipeline.trust is None

    def test_explicit_pipeline_kept(self) -> None:
        mine = ProtectionPipeline()
        _, limiter = make_app(DrogueConfig(probes_enabled=True), pipeline=mine)
        assert limiter.get_pipeline() is mine
        assert limiter.get_trust_manager() is None


class TestHoneypotHttp:
    def test_trap_path_returns_trap_code(self) -> None:
        app, _ = make_app(DrogueConfig(honeypot_paths=["/trap"]))
        client = TestClient(app)
        response = client.get("/trap")
        assert response.status_code == 404
        assert response.json()["error"] == "honeypot"

    def test_normal_path_unaffected(self) -> None:
        app, limiter = make_app(DrogueConfig(honeypot_paths=["/trap"]))

        @app.get("/real")
        @limiter.limit("100/minute")
        async def real():
            return {"ok": True}

        assert TestClient(app).get("/real").status_code == 200

    def test_trap_hit_bans_through_pipeline(self) -> None:
        ban = ProgressiveBanManager(threshold=1, window=60.0)
        honeypots = HoneypotManager()
        honeypots.register("/trap", auto_ban=True)
        pipeline = ProtectionPipeline(ban=ban, honeypots=honeypots)
        app, limiter = make_app(DrogueConfig(), pipeline=pipeline)

        @app.get("/trap")
        @limiter.limit("100/minute")
        async def trap():
            return {"ok": True}  # pragma: no cover - never reached

        @app.get("/real")
        @limiter.limit("100/minute")
        async def real():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/trap").status_code == 404
        assert ban.is_banned("testclient") is True
        response = client.get("/real")
        assert response.status_code == 403
        assert response.json()["error"] == "banned"


class TestTrustRewardHttp:
    def test_trusted_client_earns_higher_limit(self) -> None:
        config = DrogueConfig(
            trust_enabled=True,
            trust_success_threshold=2,
            trust_limit_multiplier=2.0,
        )
        app, limiter = make_app(config)

        @app.get("/rewarded")
        @limiter.limit("2/minute")
        async def rewarded():
            return {"ok": True}

        client = TestClient(app)
        first = client.get("/rewarded")
        assert first.status_code == 200
        assert first.headers["X-RateLimit-Limit"] == "2"

        assert client.get("/rewarded").status_code == 200  # promotes
        assert limiter.get_trust_manager() is not None
        assert limiter.get_trust_manager().is_trusted("testclient") is True

        # New 4-token bucket after promotion
        third = client.get("/rewarded")
        assert third.status_code == 200
        assert third.headers["X-RateLimit-Limit"] == "4"
        assert client.get("/rewarded").status_code == 200
        assert client.get("/rewarded").status_code == 200
        assert client.get("/rewarded").status_code == 200
        assert client.get("/rewarded").status_code == 429

    def test_multiplier_one_disables_reward(self) -> None:
        config = DrogueConfig(
            trust_enabled=True,
            trust_success_threshold=1,
            trust_limit_multiplier=1.0,
        )
        app, limiter = make_app(config)

        @app.get("/plain")
        @limiter.limit("1/minute")
        async def plain():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/plain").status_code == 200
        assert client.get("/plain").status_code == 429


class TestProbesHttp:
    def test_recon_gets_blocked(self) -> None:
        app, _ = make_app(DrogueConfig(probes_enabled=True))

        @app.get("/valid")
        async def valid():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/missing-1").status_code == 404
        assert client.get("/missing-2").status_code == 404
        assert client.get("/missing-3").status_code == 404

        response = client.get("/valid")
        assert response.status_code == 429
        assert response.json()["error"] == "probe_detected"


class TestRandomizerHttp:
    def test_no_session_header_uses_base_limit(self) -> None:
        app, limiter = make_app(DrogueConfig(randomizer_enabled=True))

        @app.get("/jittered")
        @limiter.limit("10/minute")
        async def jittered():
            return {"ok": True}

        response = TestClient(app).get("/jittered")
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "10"

    def test_session_limit_stable_and_in_range(self) -> None:
        app, limiter = make_app(DrogueConfig(randomizer_enabled=True))

        @app.get("/jittered")
        @limiter.limit("10/minute")
        async def jittered():
            return {"ok": True}

        client = TestClient(app)
        headers = {"x-session-id": "session-abc"}
        first = client.get("/jittered", headers=headers)
        second = client.get("/jittered", headers=headers)
        assert first.status_code == 200
        limit_value = int(first.headers["X-RateLimit-Limit"])
        assert 8 <= limit_value <= 12
        assert second.headers["X-RateLimit-Limit"] == first.headers["X-RateLimit-Limit"]


class TestSentinelHttp:
    def test_detect_only_scores_without_blocking(self) -> None:
        config = DrogueConfig(
            sentinel_enabled=True,
            sentinel_sample_rate=1.0,
            sentinel_block=False,
        )
        app, limiter = make_app(config)

        @app.get("/watched")
        @limiter.limit("100/minute")
        async def watched():
            return {"ok": True}

        client = TestClient(app)
        for _ in range(5):
            assert client.get("/watched").status_code == 200
        stats = limiter.get_pipeline().get_stats()
        assert stats["sentinel"]["total_count"] == 5
