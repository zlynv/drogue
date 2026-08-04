"""Unified protection pipeline for adapters.

Runs ban, DDoS, and circuit breaker checks in sequence before rate
limiting, and records violations/trust after the response.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from drogue.protection.ban import ProgressiveBanManager
    from drogue.protection.circuit import CircuitBreaker
    from drogue.protection.ddos import DDoSDetector

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
        1. Ban check — is this client banned?
        2. DDoS detection — is this client anomalous?
        3. Circuit breaker — is the service in degraded mode?

    After rate limiting, call record_violation() or record_success()
    to update ban and circuit breaker state.

    Usage:
        from drogue.protection import ProtectionPipeline, DDoSDetector, ProgressiveBanManager, CircuitBreaker

        pipeline = ProtectionPipeline(
            ddos=DDoSDetector(),
            ban=ProgressiveBanManager(),
            circuit=CircuitBreaker(),
        )

        # In middleware:
        result = await pipeline.check(key, context)
        if not result.allowed:
            return JSONResponse(status_code=result.status_code, ...)

        # After rate limit rejection:
        pipeline.record_violation(key)

        # After successful response:
        pipeline.record_success(key)
    """

    def __init__(
        self,
        *,
        ddos: DDoSDetector | None = None,
        ban: ProgressiveBanManager | None = None,
        circuit: CircuitBreaker | None = None,
    ) -> None:
        self.ddos = ddos
        self.ban = ban
        self.circuit = circuit

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

        # 1. Ban check
        if self.ban and self.ban.is_banned(key):
            retry_after = self.ban.get_retry_after(key)
            logger.info("pipeline: client %s is banned (retry_after=%.1f)", key, retry_after or 0)
            return PipelineResult(
                allowed=False,
                reason="banned",
                status_code=403,
                retry_after=retry_after,
            )

        # 2. DDoS detection
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

        # 3. Circuit breaker
        if self.circuit and not self.circuit.allow_request():
            status = self.circuit.get_status()
            logger.info("pipeline: circuit breaker open (status=%s)", status)
            return PipelineResult(
                allowed=False,
                reason="circuit_open",
                status_code=503,
                retry_after=self.circuit._recovery_timeout if hasattr(self.circuit, '_recovery_timeout') else 5.0,
            )

        return PipelineResult(allowed=True)

    def record_violation(self, key: str) -> None:
        """Record a rate limit violation for ban tracking."""
        if self.ban:
            self.ban.record_violation(key)

    def record_success(self, key: str) -> None:
        """Record a successful request for circuit breaker tracking."""
        if self.circuit:
            self.circuit.record_success()

    def record_failure(self, key: str) -> None:
        """Record a failed request for circuit breaker tracking."""
        if self.circuit:
            self.circuit.record_failure()

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
        return stats
