from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DrogueConfig:
    """Global configuration for drogue."""

    # Default behavior
    default_algorithm: str = "token_bucket"
    default_fail_closed: bool = True
    default_headers: bool = True
    default_retry_after: bool = True

    # Proxy handling
    trusted_proxies: list[str] = field(default_factory=list)
    proxy_header: str = "x-forwarded-for"
    trust_x_real_ip: bool = True

    # Ban settings
    ban_enabled: bool = False
    ban_threshold: int = 5
    ban_window: float = 300.0
    ban_escalation: list[float] = field(
        default_factory=lambda: [0, 60, 600, 3600, 86400]
    )

    # DDoS detection
    ddos_enabled: bool = False
    ddos_z_score_threshold: float = 3.0
    ddos_min_clients: int = 10
    ddos_window: float = 60.0

    # Circuit breaker
    circuit_breaker_enabled: bool = False
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 30.0
    circuit_jitter: float = 0.2

    # Storage
    storage_backend: str = "memory"
    redis_url: str = "redis://localhost:6379"

    # Shadow mode
    shadow_enabled: bool = False

    # CIDR filtering
    cidr_allowlist: list[str] = field(default_factory=list)
    cidr_denylist: list[str] = field(default_factory=list)

    # Adaptive rate limiting
    adaptive_enabled: bool = False
    adaptive_cpu_threshold: float = 0.8
    adaptive_memory_threshold: float = 0.8
    adaptive_latency_threshold: float = 1.0
    adaptive_check_interval: float = 5.0

    # Observability
    metrics_enabled: bool = False
    logging_enabled: bool = True
    log_level: str = "warning"

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.ban_threshold < 1:
            raise ValueError("ban_threshold must be >= 1")
        if self.ddos_z_score_threshold <= 0:
            raise ValueError("ddos_z_score_threshold must be > 0")
        if self.circuit_failure_threshold < 1:
            raise ValueError("circuit_failure_threshold must be >= 1")
