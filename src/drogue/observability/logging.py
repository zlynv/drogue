"""Structured logging for rate limiting events.

Provides structured log output for rate limit checks, bans,
DDoS detections, and circuit breaker events.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StructuredRateLimitLogger:
    """Structured logger for rate limiting events.

    Outputs JSON-structured log lines for easy parsing by
    log aggregators (ELK, Datadog, CloudWatch, etc.).

    Usage:
        logger = StructuredRateLimitLogger("drogue")

        logger.log_allowed(key="192.168.1.1", route="/api/data", remaining=95)
        logger.log_rejected(key="192.168.1.1", route="/api/data", retry_after=30.0)
        logger.log_ban(key="192.168.1.1", level=2, expires_in=600)
        logger.log_ddos(key="192.168.1.1", z_score=4.2)
        logger.log_circuit_break(state="open")
    """

    logger_name: str = "drogue"
    level: int = logging.INFO

    _logger: logging.Logger = field(init=False)

    def __post_init__(self) -> None:
        self._logger = logging.getLogger(self.logger_name)

    def log_allowed(
        self,
        key: str,
        route: str,
        remaining: int,
        limit: int,
        latency_ms: float | None = None,
    ) -> None:
        """Log an allowed request."""
        self._log(
            "rate_limit_allowed",
            key=key,
            route=route,
            remaining=remaining,
            limit=limit,
            latency_ms=latency_ms,
        )

    def log_rejected(
        self,
        key: str,
        route: str,
        retry_after: float,
        limit: int,
        remaining: int = 0,
    ) -> None:
        """Log a rejected request."""
        self._log(
            "rate_limit_rejected",
            key=key,
            route=route,
            retry_after=retry_after,
            limit=limit,
            remaining=remaining,
        )

    def log_ban(
        self,
        key: str,
        level: int,
        expires_in: float | None = None,
        reason: str = "rate_limit_violations",
    ) -> None:
        """Log a ban event."""
        self._log(
            "ban_issued",
            key=key,
            level=level,
            expires_in=expires_in,
            reason=reason,
        )

    def log_ban_expired(self, key: str, level: int) -> None:
        """Log a ban expiry."""
        self._log("ban_expired", key=key, level=level)

    def log_ddos(
        self,
        key: str,
        z_score: float,
        global_rate: float,
        client_rate: float,
    ) -> None:
        """Log a DDoS detection."""
        self._log(
            "ddos_detected",
            key=key,
            z_score=z_score,
            global_rate=global_rate,
            client_rate=client_rate,
        )

    def log_circuit_break(
        self,
        state: str,
        failure_count: int = 0,
        success_count: int = 0,
    ) -> None:
        """Log a circuit breaker state change."""
        self._log(
            "circuit_breaker",
            state=state,
            failure_count=failure_count,
            success_count=success_count,
        )

    def log_error(
        self,
        message: str,
        error: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Log an error."""
        data: dict[str, Any] = {"message": message, **kwargs}
        if error is not None:
            data["error_type"] = type(error).__name__
            data["error_message"] = str(error)
        self._log("error", **data)

    def _log(self, event: str, **data: Any) -> None:
        """Emit a structured log line."""
        record = {
            "timestamp": time.time(),
            "event": event,
            **data,
        }
        self._logger.log(self.level, json.dumps(record, default=str))
