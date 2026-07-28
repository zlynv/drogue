"""Defense Randomizer for adversarial game-theoretic defense.

Randomizes defense parameters per-session to prevent attackers
from learning and adapting to exact thresholds.

Instead of fixed rate limits (e.g., exactly 100/min), each session
gets a randomized limit within a range (e.g., 80-120/min). This
creates uncertainty for attackers probing the system's boundaries.

Impact: Attackers can't optimize because every session has
different limits. Staying "just under the known limit" no longer
works when the limit varies.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("drogue.randomizer")


class ChallengeType(Enum):
    """Types of challenges that can be issued."""

    JS_POW = "js_pow"
    COOKIE = "cookie"
    CAPTCHA = "captcha"
    CANARY = "canary"


@dataclass
class SessionParams:
    """Randomized defense parameters for a session."""

    session_id: str
    rate_limit_multiplier: float
    challenge_type: ChallengeType
    pow_difficulty: int
    jitter_ms: int
    created_at: float = field(default_factory=time.monotonic)


class DefenseRandomizer:
    """Randomize defense parameters per-session.

    Prevents attackers from learning exact thresholds by assigning
    slightly different limits to each session.

    Usage:
        randomizer = DefenseRandomizer(
            rate_limit_range=(80, 120),
            challenge_types=[ChallengeType.JS_POW, ChallengeType.COOKIE],
            pow_difficulty_range=(18, 24),
            response_jitter_range=(0, 200),
        )

        # Get randomized params for session
        params = randomizer.get_session_params("session_abc123")

        # Apply to rate limit
        effective_limit = base_limit * params.rate_limit_multiplier

        # Apply jitter to suspicious responses
        randomizer.apply_jitter("session_abc123", response)
    """

    def __init__(
        self,
        rate_limit_range: tuple[int, int] = (80, 120),
        challenge_types: list[ChallengeType] | None = None,
        pow_difficulty_range: tuple[int, int] = (18, 24),
        response_jitter_range: tuple[int, int] = (0, 200),
        session_ttl: float = 3600.0,
        max_sessions: int = 100_000,
    ):
        """Initialize the defense randomizer.

        Args:
            rate_limit_range: Min/max rate limit multiplier (percentage).
            challenge_types: Available challenge types.
            pow_difficulty_range: Min/max PoW difficulty (bits).
            response_jitter_range: Min/max response jitter (ms).
            session_ttl: How long to remember session params (seconds).
            max_sessions: Maximum sessions to track.
        """
        self.rate_limit_range = rate_limit_range
        self.challenge_types = challenge_types or [ChallengeType.JS_POW]
        self.pow_difficulty_range = pow_difficulty_range
        self.response_jitter_range = response_jitter_range
        self.session_ttl = session_ttl
        self.max_sessions = max_sessions

        self._lock = threading.RLock()
        self._sessions: dict[str, SessionParams] = {}
        self._rng = random.Random()

    def get_session_params(self, session_id: str) -> SessionParams:
        """Get or create randomized params for a session.

        Args:
            session_id: Session identifier.

        Returns:
            Randomized defense parameters.
        """
        with self._lock:
            if session_id in self._sessions:
                params = self._sessions[session_id]
                # Check if expired
                if time.monotonic() - params.created_at > self.session_ttl:
                    del self._sessions[session_id]
                else:
                    return params

            # Create new params
            multiplier = self._rng.randint(*self.rate_limit_range) / 100.0
            challenge = self._rng.choice(self.challenge_types)
            difficulty = self._rng.randint(*self.pow_difficulty_range)
            jitter = self._rng.randint(*self.response_jitter_range)

            params = SessionParams(
                session_id=session_id,
                rate_limit_multiplier=multiplier,
                challenge_type=challenge,
                pow_difficulty=difficulty,
                jitter_ms=jitter,
            )

            self._sessions[session_id] = params

            # Evict if over capacity
            if len(self._sessions) > self.max_sessions:
                self._evict_oldest()

            return params

    def get_effective_limit(self, session_id: str, base_limit: int) -> int:
        """Get the effective rate limit for a session.

        Args:
            session_id: Session identifier.
            base_limit: Base rate limit.

        Returns:
            Randomized effective limit.
        """
        params = self.get_session_params(session_id)
        effective = int(base_limit * params.rate_limit_multiplier)
        return max(1, effective)

    def get_challenge_type(self, session_id: str) -> ChallengeType:
        """Get the challenge type for a session."""
        params = self.get_session_params(session_id)
        return params.challenge_type

    def get_pow_difficulty(self, session_id: str) -> int:
        """Get the PoW difficulty for a session."""
        params = self.get_session_params(session_id)
        return params.pow_difficulty

    def get_jitter_ms(self, session_id: str) -> int:
        """Get the response jitter for a session."""
        params = self.get_session_params(session_id)
        return params.jitter_ms

    def apply_jitter(self, session_id: str, response: Any) -> None:
        """Apply response jitter if configured.

        Args:
            session_id: Session identifier.
            response: Response object with headers dict.
        """
        params = self.get_session_params(session_id)
        if params.jitter_ms > 0 and hasattr(response, "headers"):
            response.headers["X-Drogue-Jitter"] = str(params.jitter_ms)

    def clear_session(self, session_id: str) -> bool:
        """Clear params for a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def clear_all(self) -> int:
        """Clear all sessions. Returns count cleared."""
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def get_stats(self) -> dict[str, Any]:
        """Get randomizer statistics."""
        with self._lock:
            return {
                "active_sessions": len(self._sessions),
                "max_sessions": self.max_sessions,
                "rate_limit_range": self.rate_limit_range,
                "challenge_types": [c.value for c in self.challenge_types],
                "pow_difficulty_range": self.pow_difficulty_range,
                "jitter_range": self.response_jitter_range,
            }

    def _evict_oldest(self) -> None:
        """Evict oldest sessions."""
        if not self._sessions:
            return

        # Sort by creation time
        sorted_sessions = sorted(
            self._sessions.items(),
            key=lambda x: x[1].created_at,
        )

        # Remove oldest 10%
        count = max(1, len(sorted_sessions) // 10)
        for session_id, _ in sorted_sessions[:count]:
            del self._sessions[session_id]


class HoneypotManager:
    """Manage honeypot endpoints that auto-ban bots.

    Honeypots are invisible trap endpoints that only bots reach.
    Any client that hits a honeypot is instantly classified as a bot.

    Usage:
        honeypots = HoneypotManager()

        # Register honeypot paths
        honeypots.register("/admin/backup.sql", auto_ban=True)
        honeypots.register("/honeypot/hidden-link", auto_ban=True)

        # Check if request hit a honeypot
        if honeypots.is_honeypot("/admin/backup.sql"):
            # Auto-ban the client
            ban_manager.record_violation(client_id)
    """

    def __init__(self):
        self._honeypots: dict[str, dict[str, Any]] = {}
        self._hits: dict[str, list[float]] = {}

    def register(
        self,
        path: str,
        auto_ban: bool = True,
        ban_duration: float = 86400.0,
        response_code: int = 404,
    ) -> None:
        """Register a honeypot endpoint.

        Args:
            path: The honeypot path.
            auto_ban: Whether to auto-ban on hit.
            ban_duration: Ban duration in seconds.
            response_code: Response code to return.
        """
        self._honeypots[path] = {
            "auto_ban": auto_ban,
            "ban_duration": ban_duration,
            "response_code": response_code,
        }

    def is_honeypot(self, path: str) -> bool:
        """Check if a path is a honeypot."""
        return path in self._honeypots

    def record_hit(self, path: str, client_id: str) -> dict[str, Any] | None:
        """Record a honeypot hit.

        Args:
            path: The honeypot path.
            client_id: Client identifier.

        Returns:
            Honeypot config if hit, None otherwise.
        """
        config = self._honeypots.get(path)
        if config is None:
            return None

        # Record hit
        if client_id not in self._hits:
            self._hits[client_id] = []
        self._hits[client_id].append(time.monotonic())

        logger.info("honeypot_hit path=%s client=%s", path, client_id)

        return config

    def get_hits(self, client_id: str) -> list[float]:
        """Get all honeypot hits for a client."""
        return self._hits.get(client_id, [])

    def is_bot(self, client_id: str) -> bool:
        """Check if a client has hit any honeypot."""
        return client_id in self._hits

    def clear_client(self, client_id: str) -> bool:
        """Clear hits for a client."""
        if client_id in self._hits:
            del self._hits[client_id]
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get honeypot statistics."""
        return {
            "registered_honeypots": len(self._honeypots),
            "clients_botted": len(self._hits),
            "total_hits": sum(len(hits) for hits in self._hits.values()),
        }
