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

    # Probe detection (reconnaissance early warning)
    probes_enabled: bool = False
    probes_retry_after: float = 60.0

    # Trust fast-path (verified clients earn higher limits)
    trust_enabled: bool = False
    trust_success_threshold: int = 100
    trust_limit_multiplier: float = 1.0

    # Sentinel anomaly detection (streaming Half-Space Trees)
    sentinel_enabled: bool = False
    sentinel_sample_rate: float = 0.01
    sentinel_block: bool = False

    # Defense randomization (per-session limit jitter)
    randomizer_enabled: bool = False
    randomizer_session_header: str = "x-session-id"

    # Honeypot trap paths
    honeypot_paths: list[str] = field(default_factory=list)
    honeypot_ban: bool = True

    # Challenge escalation (CAPTCHA/PoW interstitials for page traffic)
    challenge_enabled: bool = False
    challenge_signing_key: str = ""
    challenge_cookie_name: str = "drogue_pass"
    challenge_cookie_ttl: float = 86400.0
    challenge_token_ttl: float = 300.0
    challenge_failure_mode: str = "block"
    challenge_failure_threshold: int = 3
    challenge_rate_limit: int = 20
    challenge_rate_window: float = 60.0
    challenge_verify_url: str = "/drogue/verify"
    # Provider credentials (for config-driven provider auto-build).
    # Provide these from the environment, never from committed code.
    challenge_site_key: str = ""
    challenge_secret: str = ""
    challenge_action: str | None = None

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.ban_threshold < 1:
            raise ValueError("ban_threshold must be >= 1")
        if self.ddos_z_score_threshold <= 0:
            raise ValueError("ddos_z_score_threshold must be > 0")
        if self.circuit_failure_threshold < 1:
            raise ValueError("circuit_failure_threshold must be >= 1")
        if self.probes_retry_after < 0:
            raise ValueError("probes_retry_after must be >= 0")
        if self.trust_success_threshold < 1:
            raise ValueError("trust_success_threshold must be >= 1")
        if self.trust_limit_multiplier < 1.0:
            raise ValueError("trust_limit_multiplier must be >= 1.0")
        if not 0.0 < self.sentinel_sample_rate <= 1.0:
            raise ValueError("sentinel_sample_rate must be in (0, 1]")
        if not self.randomizer_session_header:
            raise ValueError("randomizer_session_header must not be empty")
        if self.challenge_failure_mode not in ("block", "allow"):
            raise ValueError(
                "challenge_failure_mode must be 'block' or 'allow'"
            )
        if self.challenge_cookie_ttl <= 0:
            raise ValueError("challenge_cookie_ttl must be > 0")
        if self.challenge_token_ttl <= 0:
            raise ValueError("challenge_token_ttl must be > 0")
        if self.challenge_failure_threshold < 1:
            raise ValueError("challenge_failure_threshold must be >= 1")
        if self.challenge_rate_limit < 1:
            raise ValueError("challenge_rate_limit must be >= 1")
        if self.challenge_enabled and len(self.challenge_signing_key) < 32:
            raise ValueError(
                "challenge_signing_key must be at least 32 characters when"
                " the challenge is enabled; use a dedicated secret"
                " (openssl rand -hex 32)"
            )
