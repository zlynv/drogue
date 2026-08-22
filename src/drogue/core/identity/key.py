from __future__ import annotations

import ipaddress
from typing import Any

from drogue.core.abstracts import IdentityExtractor


def _is_valid_ip(value: str) -> bool:
    """Check whether a string parses as an IP address (v4 or v6)."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


class RemoteAddressExtractor(IdentityExtractor):
    """Extract rate limit key by client IP address.

    Security model:
    - Forwarded headers (X-Forwarded-For, X-Real-IP) are ONLY trusted when
      the direct peer address is in ``trusted_proxies``. Without trusted
      proxies configured, the connecting peer address is always used —
      clients can never spoof their own identity.
    - Extracted values must parse as valid IP addresses; otherwise the peer
      address is used, preventing bucket-poisoning with junk headers.
    """

    def __init__(
        self,
        trusted_proxies: list[str] | None = None,
        proxy_header: str = "x-forwarded-for",
        trust_x_real_ip: bool = True,
    ) -> None:
        self.trusted_proxies = set(trusted_proxies or [])
        self.proxy_header = proxy_header.lower()
        self.trust_x_real_ip = trust_x_real_ip

    async def extract(self, context: dict[str, Any]) -> str:
        client = context.get("client", {})
        host = (
            client.get("host")
            if isinstance(client, dict)
            else getattr(client, "host", None)
        )
        peer = str(host) if host else "127.0.0.1"

        # Only honor forwarded headers when the direct peer is a proxy we
        # trust. With no trusted proxies configured, header values are
        # attacker-controlled and must never be used as identity.
        if not self.trusted_proxies or peer not in self.trusted_proxies:
            return peer

        # Peer is a trusted proxy: resolve the real client from headers.
        headers = context.get("headers", {})

        # Try X-Forwarded-For first (richest signal, multi-hop aware)
        xff = self._get_header(headers, self.proxy_header)
        if xff:
            candidate = self._parse_xff(xff)
            if _is_valid_ip(candidate):
                return candidate

        # Fall back to X-Real-IP (single value set by the edge proxy)
        if self.trust_x_real_ip:
            real_ip = self._get_header(headers, "x-real-ip")
            if real_ip and _is_valid_ip(real_ip.strip()):
                return real_ip.strip()

        # Headers absent or invalid: trust the proxy's own address
        return peer

    def _parse_xff(self, xff: str) -> str:
        """Parse X-Forwarded-For header, handling multi-hop proxies.

        Returns the leftmost (client) IP, or the first trusted proxy's IP
        if the client is not trusted.
        """
        ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
        if not ips:
            return "127.0.0.1"

        # If no trusted proxies configured, return the leftmost IP
        if not self.trusted_proxies:
            return ips[0]

        # Walk from right to left, find the last untrusted IP
        # (the one closest to the client that isn't a known proxy)
        for ip in reversed(ips):
            if ip not in self.trusted_proxies:
                return ip

        # All IPs are trusted proxies; return the leftmost (original client)
        return ips[0]

    def _get_header(self, headers: dict[str, Any], name: str) -> str | None:
        """Get header value, handling both dict and ASGI header formats."""
        # ASGI format: lowercase keys, bytes values
        if name in headers:
            val = headers[name]
            return val.decode() if isinstance(val, bytes) else str(val)

        # Also try case-insensitive lookup
        name_lower = name.lower()
        for key, val in headers.items():
            if key.lower() == name_lower:
                return val.decode() if isinstance(val, bytes) else str(val)

        return None


class UserExtractor(IdentityExtractor):
    """Extract rate limit key by authenticated user ID."""

    def __init__(self, user_id_key: str = "user_id", anonymous_value: str = "anonymous") -> None:
        self.user_id_key = user_id_key
        self.anonymous_value = anonymous_value

    async def extract(self, context: dict[str, Any]) -> str:
        # Check user_id in state or directly in context
        user_id = context.get(self.user_id_key)
        if user_id is None:
            state = context.get("state", {})
            user_id = state.get(self.user_id_key)
        if user_id is None:
            request = context.get("request")
            if request is not None:
                state = getattr(request, "state", None)
                if state is not None:
                    user_id = getattr(state, self.user_id_key, None)

        if user_id is not None:
            return str(user_id)
        return self.anonymous_value


class HeaderExtractor(IdentityExtractor):
    """Extract rate limit key from a specific header."""

    def __init__(self, header_name: str, fallback: str = "anonymous") -> None:
        self.header_name = header_name.lower()
        self.fallback = fallback

    async def extract(self, context: dict[str, Any]) -> str:
        headers = context.get("headers", {})
        for key, val in headers.items():
            if key.lower() == self.header_name:
                return val.decode() if isinstance(val, bytes) else str(val)
        return self.fallback


class PathExtractor(IdentityExtractor):
    """Extract rate limit key by request path (for per-path limiting)."""

    async def extract(self, context: dict[str, Any]) -> str:
        path = context.get("path", "/")
        if path is None:
            request = context.get("request")
            if request is not None:
                path = getattr(request, "url", None)
                if path is not None:
                    path = getattr(path, "path", "/")
        return str(path)


class StaticKeyExtractor(IdentityExtractor):
    """Returns a fixed key (for global rate limiting)."""

    def __init__(self, key: str = "global") -> None:
        self.key = key

    async def extract(self, context: dict[str, Any]) -> str:
        return self.key
