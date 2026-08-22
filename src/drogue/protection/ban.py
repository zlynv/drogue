"""Progressive auto-ban system.

Automatically bans clients that repeatedly exceed rate limits,
with escalating ban durations: 1min -> 10min -> 1hr -> 24hr.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class BanEntry:
    """A ban record for a client."""

    key: str
    level: int
    banned_at: float
    expires_at: float | None
    violation_count: int


@dataclass
class ProgressiveBanManager:
    """Manages progressive bans for repeat offenders.

    Ban escalation levels:
        0: Warning (no ban)
        1: 1 minute
        2: 10 minutes
        3: 1 hour
        4: 24 hours

    Usage:
        ban = ProgressiveBanManager()
        ban.record_violation("192.168.1.1")
        if ban.is_banned("192.168.1.1"):
            return 403
    """

    escalation: list[float] = field(
        default_factory=lambda: [0, 60, 600, 3600, 86400]
    )
    threshold: int = 5
    window: float = 300.0
    max_violations: int = 20

    _bans: dict[str, BanEntry] = field(default_factory=dict)
    _violations: dict[str, list[float]] = field(default_factory=dict)

    def record_violation(self, key: str) -> int:
        """Record a rate limit violation. Returns the new ban level.

        The current violation is ALWAYS recorded, even when all previous
        violations have aged out of the window — dropping it would reset
        escalation progress for repeat offenders.
        """
        now = time.monotonic()

        # Clean old violations outside the window (but keep the current one)
        if key in self._violations:
            self._violations[key] = [
                t for t in self._violations[key] if now - t < self.window
            ]
        else:
            self._violations[key] = []

        self._violations[key].append(now)
        violation_count = len(self._violations[key])

        # Check if should ban
        if violation_count >= self.threshold:
            level = self._compute_ban_level(violation_count)
            duration = self._get_duration(level)
            expires_at = now + duration if duration > 0 else None

            existing = self._bans.get(key)
            # Only escalate, never downgrade
            if existing is None or level > existing.level:
                self._bans[key] = BanEntry(
                    key=key,
                    level=level,
                    banned_at=now,
                    expires_at=expires_at,
                    violation_count=violation_count,
                )

            return level

        return 0

    def is_banned(self, key: str) -> bool:
        """Check if a client is currently banned."""
        entry = self._bans.get(key)
        if entry is None:
            return False

        # Permanent ban
        if entry.expires_at is None:
            return True

        # Check expiry
        now = time.monotonic()
        if now >= entry.expires_at:
            # Ban expired, remove
            del self._bans[key]
            return False

        return True

    def get_ban(self, key: str) -> BanEntry | None:
        """Get the ban entry for a client, if any."""
        entry = self._bans.get(key)
        if entry is None:
            return None

        if entry.expires_at is not None:
            now = time.monotonic()
            if now >= entry.expires_at:
                del self._bans[key]
                return None

        return entry

    def get_retry_after(self, key: str) -> float | None:
        """Get seconds until ban expires, or None if not banned."""
        entry = self._bans.get(key)
        if entry is None or entry.expires_at is None:
            return None
        remaining = entry.expires_at - time.monotonic()
        return max(0.0, remaining)

    def get_ban_level(self, key: str) -> int:
        """Get the current ban level for a key (0 = not banned)."""
        entry = self.get_ban(key)
        return entry.level if entry else 0

    def clear_ban(self, key: str) -> bool:
        """Manually clear a ban. Returns True if there was a ban to clear."""
        if key in self._bans:
            del self._bans[key]
            return True
        return False

    def clear_all(self) -> int:
        """Clear all bans. Returns count of bans cleared."""
        count = len(self._bans)
        self._bans.clear()
        self._violations.clear()
        return count

    def get_active_bans(self) -> dict[str, BanEntry]:
        """Get all currently active bans."""
        now = time.monotonic()
        active = {}
        expired = []
        for key, entry in self._bans.items():
            if entry.expires_at is None or now < entry.expires_at:
                active[key] = entry
            else:
                expired.append(key)
        for key in expired:
            del self._bans[key]
        return active

    def _compute_ban_level(self, violation_count: int) -> int:
        """Compute ban level from violation count."""
        excess = violation_count - self.threshold
        level = 1 + excess // 2  # escalate every 2 violations
        return min(level, len(self.escalation) - 1)

    def _get_duration(self, level: int) -> float:
        """Get ban duration for a level."""
        idx = min(level, len(self.escalation) - 1)
        return self.escalation[idx]
