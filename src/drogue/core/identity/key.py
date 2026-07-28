from __future__ import annotations

from typing import Any

from drogue.core.abstracts import IdentityExtractor


class RemoteAddressExtractor(IdentityExtractor):
    """Extract rate limit key by client IP address.

    Respects X-Forwarded-For and X-Real-IP headers when configured.
    Handles multi-hop proxy chains correctly.
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
        # Try X-Real-IP first (simpler, single value)
        if self.trust_x_real_ip:
            headers = context.get("headers", {})
            x_real_ip = self._get_header(headers, "x-real-ip")
            if x_real_ip:
                return x_real_ip.strip()

        # Try X-Forwarded-For (may have multiple IPs)
        headers = context.get("headers", {})
        xff = self._get_header(headers, self.proxy_header)
        if xff:
            return self._parse_xff(xff)

        # Fall back to client.host
        client = context.get("client", {})
        host = client.get("host") if isinstance(client, dict) else getattr(client, "host", None)

        if host:
            return host

        return "127.0.0.1"

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
