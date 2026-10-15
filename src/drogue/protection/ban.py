"""Progressive auto-ban system.

Automatically bans clients that repeatedly exceed rate limits,
with escalating ban durations: 1min -> 10m -> 1hr -> 24hr.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drogue.core.abstracts import Storage

# TTL used for permanent bans in shared storage (10 years). Backends
# require an expiry; there is no "persist forever" primitive.
_PERMANENT_BAN_TTL = 315360000.0


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

    Shared state: pass a `Storage` (e.g. RedisStorage) to enforce bans
    across processes and hosts. Violation counting then uses a sliding
    window (each violation refreshes the full window TTL) and ban
    expiries use wall-clock time, while the default in-memory mode uses
    a fixed pruning window on monotonic time. Use the `*_async` methods
    with shared storage; the sync methods are in-memory only.

    Usage:
        ban = ProgressiveBanManager()
        ban.record_violation("192.168.1.1")
        if ban.is_banned("192.168.1.1"):
            return 403

    Shared usage:
        from drogue.core.storage.redis import RedisStorage
        storage = RedisStorage(url="redis://localhost:6379")
        await storage.initialize()
        ban = ProgressiveBanManager(storage=storage)
        await ban.record_violation_async("192.168.1.1")
        if await ban.is_banned_async("192.168.1.1"):
            return 403
    """

    escalation: list[float] = field(
        default_factory=lambda: [0, 60, 600, 3600, 86400]
    )
    threshold: int = 5
    window: float = 300.0
    max_violations: int = 20
    storage: Storage | None = None

    _bans: dict[str, BanEntry] = field(default_factory=dict)
    _violations: dict[str, list[float]] = field(default_factory=dict)

    def record_violation(self, key: str) -> int:
        """Record a rate limit violation. Returns the new ban level.

        The current violation is ALWAYS recorded, even when all previous
        violations have aged out of the window - dropping it would reset
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
        # Cap memory per key; the newest violations decide escalation.
        if len(self._violations[key]) > self.max_violations:
            del self._violations[key][:-self.max_violations]
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

    def _violation_key(self, key: str) -> str:
        """Storage key for the shared violation counter."""
        return f"drogue:ban:violations:{key}"

    def _ban_key(self, key: str) -> str:
        """Storage key for the shared ban record."""
        return f"drogue:ban:ban:{key}"

    async def record_violation_async(self, key: str) -> int:
        """Record a violation in shared storage. Returns the ban level.

        Requires `storage`. Counting uses a sliding window: every
        violation refreshes the full window TTL.
        """
        if self.storage is None:
            raise ValueError("record_violation_async requires storage")
        count, _ = await self.storage.increment_by(
            self._violation_key(key), 1, self.window
        )

        if count < self.threshold:
            return 0

        level = self._compute_ban_level(count)
        duration = self._get_duration(level)

        existing = await self.get_ban_level_async(key)
        if existing is not None and level <= existing:
            return level  # only escalate, never downgrade

        if duration > 0:
            await self.storage.set(
                self._ban_key(key),
                f"{level}:{time.time() + duration}",
                duration,
            )
        else:
            await self.storage.set(
                self._ban_key(key), f"{level}:never", _PERMANENT_BAN_TTL
            )
        return level

    async def is_banned_async(self, key: str) -> bool:
        """Check a shared-storage ban. Requires `storage`."""
        return await self.get_ban_level_async(key) is not None

    async def get_ban_level_async(self, key: str) -> int | None:
        """Shared-storage ban level, or None if not banned.

        Requires `storage`. Corrupt records are deleted (fail-open)
        rather than locking a client out forever.
        """
        if self.storage is None:
            raise ValueError("get_ban_level_async requires storage")
        raw = await self.storage.get(self._ban_key(key))
        if raw is None:
            return None
        try:
            level_str, expires_str = str(raw).split(":", 1)
            level = int(level_str)
        except (ValueError, AttributeError):
            await self.storage.delete(self._ban_key(key))
            return None
        if expires_str != "never" and time.time() >= float(expires_str):
            await self.storage.delete(self._ban_key(key))
            return None
        return level

    async def get_retry_after_async(self, key: str) -> float | None:
        """Seconds until a shared ban expires, or None if not banned."""
        if self.storage is None:
            raise ValueError("get_retry_after_async requires storage")
        raw = await self.storage.get(self._ban_key(key))
        if raw is None:
            return None
        try:
            _, expires_str = str(raw).split(":", 1)
        except (ValueError, AttributeError):
            return None
        if expires_str == "never":
            return None
        return max(0.0, float(expires_str) - time.time())

    async def clear_ban_async(self, key: str) -> bool:
        """Clear a shared-storage ban and its violation counter."""
        if self.storage is None:
            raise ValueError("clear_ban_async requires storage")
        had_ban = await self.storage.get(self._ban_key(key)) is not None
        await self.storage.delete(self._ban_key(key))
        await self.storage.delete(self._violation_key(key))
        return had_ban

    def _compute_ban_level(self, violation_count: int) -> int:
        """Compute ban level from violation count."""
        excess = violation_count - self.threshold
        level = 1 + excess // 2  # escalate every 2 violations
        return min(level, len(self.escalation) - 1)

    def _get_duration(self, level: int) -> float:
        """Get ban duration for a level."""
        idx = min(level, len(self.escalation) - 1)
        return self.escalation[idx]
