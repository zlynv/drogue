"""Tests for pipeline-wired defenses: honeypots, probes, trust, sentinel.

Also covers shared-storage (cross-process) ban state.
"""
from __future__ import annotations

import asyncio
import time

from drogue.core.storage.memory import MemoryStorage
from drogue.defense.randomizer import HoneypotManager
from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.pipeline import ProtectionPipeline
from drogue.protection.probes import ProbeDetector
from drogue.protection.sentinel import SentinelDetector
from drogue.protection.trust import TrustLevel, TrustManager


def make_context(path: str = "/api/data", ip: str = "10.0.0.1") -> dict:
    return {"client": {"host": ip}, "path": path, "method": "GET"}


class TestPipelineHoneypot:
    def test_honeypot_hit_denied_404(self) -> None:
        honeypots = HoneypotManager()
        honeypots.register("/admin/backup.sql")
        pipeline = ProtectionPipeline(honeypots=honeypots)

        result = asyncio.run(
            pipeline.check("attacker", make_context(path="/admin/backup.sql"))
        )
        assert result.allowed is False
        assert result.reason == "honeypot"
        assert result.status_code == 404

    def test_honeypot_custom_response_code(self) -> None:
        honeypots = HoneypotManager()
        honeypots.register("/trap", auto_ban=False, response_code=403)
        pipeline = ProtectionPipeline(honeypots=honeypots)

        result = asyncio.run(
            pipeline.check("bot", make_context(path="/trap"))
        )
        assert result.allowed is False
        assert result.status_code == 403

    def test_honeypot_hit_bans_when_configured(self) -> None:
        honeypots = HoneypotManager()
        honeypots.register("/trap", auto_ban=True)
        ban = ProgressiveBanManager(threshold=1, window=60.0)
        pipeline = ProtectionPipeline(ban=ban, honeypots=honeypots)

        result = asyncio.run(
            pipeline.check("bot", make_context(path="/trap"))
        )
        assert result.allowed is False
        assert ban.is_banned("bot") is True

    def test_honeypot_no_ban_when_disabled(self) -> None:
        honeypots = HoneypotManager()
        honeypots.register("/trap", auto_ban=False)
        ban = ProgressiveBanManager(threshold=1, window=60.0)
        pipeline = ProtectionPipeline(ban=ban, honeypots=honeypots)

        asyncio.run(pipeline.check("bot", make_context(path="/trap")))
        assert ban.is_banned("bot") is False

    def test_non_honeypot_path_passes(self) -> None:
        honeypots = HoneypotManager()
        honeypots.register("/trap")
        pipeline = ProtectionPipeline(honeypots=honeypots)

        result = asyncio.run(
            pipeline.check("user", make_context(path="/api/data"))
        )
        assert result.allowed is True

    def test_honeypot_stats_section(self) -> None:
        honeypots = HoneypotManager()
        honeypots.register("/trap")
        pipeline = ProtectionPipeline(honeypots=honeypots)
        assert pipeline.get_stats()["honeypots"]["registered_honeypots"] == 1


class TestPipelineProbes:
    def _probing_pipeline(self) -> tuple[ProtectionPipeline, ProbeDetector]:
        probes = ProbeDetector(
            window=300.0, probe_threshold=3, min_error_rate=0.5,
            max_time_span=60.0,
        )
        return ProtectionPipeline(probes=probes), probes

    def test_probing_client_denied(self) -> None:
        pipeline, probes = self._probing_pipeline()
        for i in range(3):
            probes.record("scanner", f"/secret-{i}", 404)

        result = asyncio.run(
            pipeline.check("scanner", make_context(ip="scanner"))
        )
        assert result.allowed is False
        assert result.reason == "probe_detected"
        assert result.status_code == 429
        assert result.retry_after == 60.0

    def test_clean_client_passes(self) -> None:
        pipeline, probes = self._probing_pipeline()
        probes.record("user", "/api/data", 200)
        probes.record("user", "/api/data", 200)

        result = asyncio.run(
            pipeline.check("user", make_context(ip="user"))
        )
        assert result.allowed is True

    def test_record_response_feeds_detector(self) -> None:
        pipeline, _ = self._probing_pipeline()
        assert pipeline.probes is not None
        for i in range(3):
            pipeline.record_response("scanner", f"/hidden-{i}", 404)
        assert pipeline.probes.is_probing("scanner") is True

    def test_probes_stats_section(self) -> None:
        pipeline, _ = self._probing_pipeline()
        assert "probes" in pipeline.get_stats()


class TestPipelineTrust:
    def test_success_streak_promotes_to_trusted(self) -> None:
        trust = TrustManager()
        pipeline = ProtectionPipeline(
            trust=trust, trust_success_threshold=3
        )
        for _ in range(3):
            pipeline.record_success("good-client")
        assert trust.is_trusted("good-client") is True

    def test_violation_poisons_trust(self) -> None:
        trust = TrustManager()
        pipeline = ProtectionPipeline(
            trust=trust, trust_success_threshold=2
        )
        pipeline.record_success("client")
        pipeline.record_success("client")
        assert trust.is_trusted("client") is True
        pipeline.record_violation("client")
        assert trust.check("client") == TrustLevel.UNKNOWN

    def test_trust_stats_section(self) -> None:
        pipeline = ProtectionPipeline(trust=TrustManager())
        assert "trust" in pipeline.get_stats()

    def test_streak_tracking_bounded(self) -> None:
        trust = TrustManager()
        pipeline = ProtectionPipeline(
            trust=trust, trust_success_threshold=100000,
            trust_max_tracked=10,
        )
        for i in range(25):
            pipeline.record_success(f"client-{i}")
        assert len(pipeline._trust_streaks) <= 10


class TestPipelineSentinel:
    def test_detect_only_never_blocks(self) -> None:
        sentinel = SentinelDetector(random_state=42)
        pipeline = ProtectionPipeline(
            sentinel=sentinel, sentinel_sample_rate=1.0,
            sentinel_block=False,
        )
        for _ in range(30):
            result = asyncio.run(pipeline.check("k", make_context()))
            assert result.allowed is True
        assert pipeline.get_stats()["sentinel"]["total_count"] == 30

    def test_block_mode_denies_anomaly(self) -> None:
        import random as _random

        warmup_rng = _random.Random(7)
        sentinel = SentinelDetector(random_state=42)
        for _ in range(300):
            sentinel.analyze(
                [warmup_rng.uniform(0.5, 1.5) for _ in range(5)]
            )
        pipeline = ProtectionPipeline(
            sentinel=sentinel, sentinel_sample_rate=1.0,
            sentinel_block=True,
            feature_fn=lambda ctx: [1000.0, 0.0, 0.0, 1.0, 5000.0],
        )
        result = asyncio.run(pipeline.check("attacker", make_context()))
        assert result.allowed is False
        assert result.reason == "sentinel_anomaly"
        assert result.status_code == 429

    def test_scoring_failure_fails_open(self) -> None:
        sentinel = SentinelDetector(n_features=5, random_state=1)
        pipeline = ProtectionPipeline(
            sentinel=sentinel, sentinel_sample_rate=1.0,
            sentinel_block=True,
            feature_fn=lambda ctx: [1.0, 2.0],  # wrong width
        )
        result = asyncio.run(pipeline.check("k", make_context()))
        assert result.allowed is True


class TestSharedStorageBans:
    def test_ban_shared_across_managers(self) -> None:
        storage = MemoryStorage()
        writer = ProgressiveBanManager(
            threshold=3, window=60.0, storage=storage
        )
        reader = ProgressiveBanManager(
            threshold=3, window=60.0, storage=storage
        )

        async def run() -> None:
            for _ in range(3):
                await writer.record_violation_async("shared-key")

        asyncio.run(run())
        assert asyncio.run(reader.is_banned_async("shared-key")) is True
        assert asyncio.run(writer.is_banned_async("shared-key")) is True

    def test_shared_ban_expires(self) -> None:
        storage = MemoryStorage()
        ban = ProgressiveBanManager(
            threshold=1, window=60.0, escalation=[0, 0.05],
            storage=storage,
        )
        asyncio.run(ban.record_violation_async("temp"))
        assert asyncio.run(ban.is_banned_async("temp")) is True
        retry_after = asyncio.run(ban.get_retry_after_async("temp"))
        assert retry_after is not None and retry_after > 0
        time.sleep(0.07)
        assert asyncio.run(ban.is_banned_async("temp")) is False

    def test_shared_ban_escalates_not_downgrades(self) -> None:
        storage = MemoryStorage()
        ban = ProgressiveBanManager(
            threshold=2, window=60.0, storage=storage
        )
        asyncio.run(ban.record_violation_async("k"))
        asyncio.run(ban.record_violation_async("k"))
        first = asyncio.run(ban.get_ban_level_async("k"))
        asyncio.run(ban.record_violation_async("k"))
        asyncio.run(ban.record_violation_async("k"))
        second = asyncio.run(ban.get_ban_level_async("k"))
        assert first is not None and second is not None
        assert second >= first

    def test_shared_clear_ban(self) -> None:
        storage = MemoryStorage()
        ban = ProgressiveBanManager(
            threshold=1, window=60.0, storage=storage
        )
        asyncio.run(ban.record_violation_async("k"))
        assert asyncio.run(ban.clear_ban_async("k")) is True
        assert asyncio.run(ban.is_banned_async("k")) is False
        assert asyncio.run(ban.clear_ban_async("k")) is False

    def test_async_requires_storage(self) -> None:
        ban = ProgressiveBanManager()
        for coro in (
            ban.record_violation_async("k"),
            ban.is_banned_async("k"),
            ban.get_ban_level_async("k"),
            ban.get_retry_after_async("k"),
            ban.clear_ban_async("k"),
        ):
            try:
                asyncio.run(coro)
            except ValueError:
                pass
            else:
                raise AssertionError("expected ValueError without storage")

    def test_pipeline_uses_shared_ban(self) -> None:
        storage = MemoryStorage()
        ban = ProgressiveBanManager(
            threshold=2, window=60.0, storage=storage
        )
        pipeline = ProtectionPipeline(ban=ban)

        async def run() -> None:
            await ban.record_violation_async("k")
            await ban.record_violation_async("k")
            result = await pipeline.check("k", make_context())
            assert result.allowed is False
            assert result.reason == "banned"

        asyncio.run(run())
