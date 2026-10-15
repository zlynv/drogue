"""Unified protection pipeline for adapters.

Runs ban, honeypot, probe, DDoS, sentinel, and circuit breaker checks
in sequence before rate limiting, and records violations/trust after
the response.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from drogue.defense.randomizer import HoneypotManager
    from drogue.protection.ban import ProgressiveBanManager
    from drogue.protection.circuit import CircuitBreaker
    from drogue.protection.ddos import DDoSDetector
    from drogue.protection.probes import ProbeDetector
    from drogue.protection.sentinel import SentinelDetector
    from drogue.protection.trust import TrustManager

logger = logging.getLogger("drogue.pipeline")


@dataclass
class PipelineResult:
    """Result of a pipeline check."""

    allowed: bool
    reason: str | None = None
    status_code: int = 200
    retry_after: float | None = None
    stats: dict[str, Any] = field(default_factory=dict)


class ProtectionPipeline:
    """Unified protection pipeline.

    Runs checks in order:
        1. Honeypot - did the client touch a trap path?
        2. Ban check - is this client banned?
        3. Probe detection - is this client reconnoitering?
        4. DDoS detection - is this client anomalous?
        5. Sentinel - does this request look anomalous (sampled)?
        6. Circuit breaker - is the service in degraded mode?

    Trust never blocks: it tracks success streaks per key and promotes
    clean clients to TRUSTED so adapters can reward them with higher
    limits. Any violation poisons trust immediately.

    After rate limiting, call record_violation() or record_success()
    to update ban, trust, and circuit breaker state, and record_probe()
    (or record_response()) once the response status is known so probe
    detection sees real error rates.

    Usage:
        from drogue.protection import (
            ProtectionPipeline, DDoSDetector, ProgressiveBanManager,
            CircuitBreaker, ProbeDetector, TrustManager,
        )

        pipeline = ProtectionPipeline(
            ddos=DDoSDetector(),
            ban=ProgressiveBanManager(),
            circuit=CircuitBreaker(),
            probes=ProbeDetector(),
            trust=TrustManager(),
        )

        # In middleware:
        result = await pipeline.check(key, context)
        if not result.allowed:
            return JSONResponse(status_code=result.status_code, ...)

        # After rate limit rejection:
        pipeline.record_violation(key)

        # After successful response (status known):
        pipeline.record_success(key)
        pipeline.record_response(key, path="/api/data", status_code=200)
    """

    def __init__(
        self,
        *,
        ddos: DDoSDetector | None = None,
        ban: ProgressiveBanManager | None = None,
        circuit: CircuitBreaker | None = None,
        probes: ProbeDetector | None = None,
        trust: TrustManager | None = None,
        sentinel: SentinelDetector | None = None,
        honeypots: HoneypotManager | None = None,
        probes_retry_after: float = 60.0,
        trust_success_threshold: int = 100,
        trust_max_tracked: int = 100000,
        sentinel_sample_rate: float = 0.01,
        sentinel_block: bool = False,
        feature_fn: Callable[[dict[str, Any]], list[float]] | None = None,
    ) -> None:
        self.ddos = ddos
        self.ban = ban
        self.circuit = circuit
        self.probes = probes
        self.trust = trust
        self.sentinel = sentinel
        self.honeypots = honeypots
        self.probes_retry_after = probes_retry_after
        self.trust_success_threshold = trust_success_threshold
        self.trust_max_tracked = trust_max_tracked
        self.sentinel_sample_rate = sentinel_sample_rate
        self.sentinel_block = sentinel_block
        self.feature_fn = feature_fn
        self._trust_streaks: dict[str, int] = {}
        self._rng = random.Random()

    async def check(
        self,
        key: str,
        context: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Run all protection checks in sequence.

        Returns PipelineResult with allowed=True if all checks pass.
        """
        ctx = context or {}
        client_ip = ctx.get("client", {}).get("host", key)
        path = ctx.get("path", "") or ""

        # 1. Honeypot trap paths
        if self.honeypots and path and self.honeypots.is_honeypot(path):
            config = self.honeypots.record_hit(path, key)
            response_code = 404
            if config:
                response_code = int(config.get("response_code", 404))
                if config.get("auto_ban", True) and self.ban is not None:
                    await self._ban_record(key)
            logger.info(
                "pipeline: client %s hit honeypot %s (response=%d)",
                key, path, response_code,
            )
            return PipelineResult(
                allowed=False,
                reason="honeypot",
                status_code=response_code,
            )

        # 2. Ban check
        if self.ban and await self._ban_is_banned(key):
            retry_after = await self._ban_retry_after(key)
            logger.info("pipeline: client %s is banned (retry_after=%.1f)", key, retry_after or 0)
            return PipelineResult(
                allowed=False,
                reason="banned",
                status_code=403,
                retry_after=retry_after,
            )

        # 3. Probe detection (reconnaissance early warning)
        if self.probes and self.probes.is_probing(client_ip):
            logger.info("pipeline: client %s flagged as probing", key)
            return PipelineResult(
                allowed=False,
                reason="probe_detected",
                status_code=429,
                retry_after=self.probes_retry_after,
            )

        # 4. DDoS detection
        if self.ddos:
            self.ddos.record(client_ip)
            if self.ddos.is_anomalous(client_ip):
                logger.info("pipeline: client %s flagged as anomalous by DDoS detector", key)
                return PipelineResult(
                    allowed=False,
                    reason="ddos_anomalous",
                    status_code=429,
                    retry_after=5.0,
                    stats=self.ddos.get_stats(),
                )

        # 5. Sentinel anomaly detection (sampled: scoring every request
        # at high throughput would dominate CPU)
        if self.sentinel and self._rng.random() < self.sentinel_sample_rate:
            try:
                fn = self.feature_fn
                if fn is None:
                    from drogue.protection.sentinel import extract_features as fn  # type: ignore[no-redef]
                if self.sentinel.analyze(fn(ctx)):
                    logger.info("pipeline: sentinel flagged request from %s", key)
                    if self.sentinel_block:
                        return PipelineResult(
                            allowed=False,
                            reason="sentinel_anomaly",
                            status_code=429,
                            retry_after=5.0,
                        )
            except Exception:
                logger.warning("pipeline: sentinel scoring failed", exc_info=True)

        # 6. Circuit breaker
        if self.circuit and not self.circuit.allow_request():
            status = self.circuit.get_status()
            logger.info("pipeline: circuit breaker open (status=%s)", status)
            return PipelineResult(
                allowed=False,
                reason="circuit_open",
                status_code=503,
                retry_after=self.circuit.recovery_timeout,
            )

        return PipelineResult(allowed=True)

    def record_violation(self, key: str) -> None:
        """Record a rate limit violation for ban tracking.

        Poisons trust and resets the key's success streak. Ban managers
        with shared storage are updated via a background bridge so this
        stays synchronous for callers.
        """
        if self.ban:
            if getattr(self.ban, "storage", None) is not None:
                from drogue.utils.async_utils import run_async

                run_async(self.ban.record_violation_async(key))
            else:
                self.ban.record_violation(key)
        if self.trust:
            self.trust.poison(key)
        self._trust_streaks.pop(key, None)

    def record_success(self, key: str) -> None:
        """Record a successful request for circuit breaker and trust tracking."""
        if self.circuit:
            self.circuit.record_success()
        if self.trust:
            streak = self._trust_streaks.get(key, 0) + 1
            if streak >= self.trust_success_threshold:
                self.trust.update(key, 0.0)
                self._trust_streaks.pop(key, None)
            else:
                if len(self._trust_streaks) >= self.trust_max_tracked and key not in self._trust_streaks:
                    self._trust_streaks.pop(next(iter(self._trust_streaks)))
                self._trust_streaks[key] = streak

    def record_probe(
        self,
        key: str,
        path: str,
        status_code: int,
        method: str = "GET",
    ) -> None:
        """Record a completed response for probe detection."""
        if self.probes:
            self.probes.record(key, path, status_code, method=method)

    def record_response(
        self,
        key: str,
        path: str,
        status_code: int,
        method: str = "GET",
    ) -> None:
        """Alias for record_probe: feed a finished response back.

        Trust promotion is handled by record_success(); call both after
        a successful response.
        """
        self.record_probe(key, path, status_code, method=method)

    def record_failure(self, key: str) -> None:
        """Record a failed request for circuit breaker tracking."""
        if self.circuit:
            self.circuit.record_failure()

    async def _ban_is_banned(self, key: str) -> bool:
        """Ban check that works with in-memory and shared-storage bans."""
        assert self.ban is not None
        if getattr(self.ban, "storage", None) is not None:
            return await self.ban.is_banned_async(key)
        return self.ban.is_banned(key)

    async def _ban_retry_after(self, key: str) -> float | None:
        """Retry-after that works with in-memory and shared-storage bans."""
        assert self.ban is not None
        if getattr(self.ban, "storage", None) is not None:
            return await self.ban.get_retry_after_async(key)
        return self.ban.get_retry_after(key)

    async def _ban_record(self, key: str) -> None:
        """Violation recording for in-memory and shared-storage bans."""
        assert self.ban is not None
        if getattr(self.ban, "storage", None) is not None:
            await self.ban.record_violation_async(key)
        else:
            self.ban.record_violation(key)

    def get_stats(self) -> dict[str, Any]:
        """Get combined protection stats."""
        stats: dict[str, Any] = {}
        if self.ddos:
            stats["ddos"] = self.ddos.get_stats()
        if self.ban:
            stats["ban"] = {
                "active_bans": len(self.ban.get_active_bans()),
            }
        if self.circuit:
            stats["circuit"] = self.circuit.get_status()
        if self.probes:
            stats["probes"] = self.probes.get_stats()
        if self.trust:
            stats["trust"] = self.trust.get_stats()
        if self.sentinel:
            stats["sentinel"] = self.sentinel.get_stats()
        if self.honeypots:
            stats["honeypots"] = self.honeypots.get_stats()
        return stats
