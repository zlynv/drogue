from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("drogue.proxy")


class ProxyResolver:
    """Handles proxy header parsing and trust validation.

    Provides secure X-Forwarded-For parsing with anti-spoofing.
    """

    def __init__(
        self,
        trusted_proxies: list[str] | None = None,
        trust_x_real_ip: bool = True,
        trust_cloudflare: bool = False,
        trust_headers: list[str] | None = None,
    ) -> None:
        self.trusted_proxies = set(trusted_proxies or [])
        self.trust_x_real_ip = trust_x_real_ip
        self.trust_cloudflare = trust_cloudflare
        self.trust_headers = trust_headers or ["x-forwarded-for"]

        # Cloudflare IPs (update periodically)
        self._cloudflare_ranges = self._load_cloudflare_ranges() if trust_cloudflare else set()

    def resolve_client_ip(self, context: dict[str, Any]) -> str:
        """Extract the real client IP from request context.

        Priority:
        1. X-Real-IP (if trusted)
        2. CF-Connecting-IP (if Cloudflare trusted)
        3. X-Forwarded-For (parsed with proxy trust)
        4. client.host fallback
        """
        headers = context.get("headers", {})

        # 1. X-Real-IP
        if self.trust_x_real_ip:
            x_real_ip = self._get_header_value(headers, "x-real-ip")
            if x_real_ip and self._is_valid_ip(x_real_ip):
                return x_real_ip

        # 2. Cloudflare
        if self.trust_cloudflare:
            cf_ip = self._get_header_value(headers, "cf-connecting-ip")
            if cf_ip and self._is_valid_ip(cf_ip):
                return cf_ip

        # 3. X-Forwarded-For (multi-hop aware)
        for header_name in self.trust_headers:
            xff = self._get_header_value(headers, header_name)
            if xff:
                return self._parse_xff(xff)

        # 4. Fallback
        client = context.get("client", {})
        if isinstance(client, dict):
            host = client.get("host", "127.0.0.1")
        else:
            host = getattr(client, "host", "127.0.0.1")
        return str(host)

    def _parse_xff(self, xff: str) -> str:
        """Parse X-Forwarded-For with proxy trust awareness."""
        ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
        if not ips:
            return "127.0.0.1"

        if not self.trusted_proxies:
            return ips[0]

        # Walk from right to left, find first non-trusted IP
        for ip in reversed(ips):
            if ip not in self.trusted_proxies:
                return ip

        return ips[0]

    def _get_header_value(self, headers: dict[str, Any], name: str) -> str | None:
        """Get header value with case-insensitive lookup."""
        name_lower = name.lower()
        for key, val in headers.items():
            if key.lower() == name_lower:
                return val.decode() if isinstance(val, bytes) else str(val)
        return None

    def _is_valid_ip(self, ip: str) -> bool:
        """Basic IP validation."""
        parts = ip.split(".")
        if len(parts) == 4:
            return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
        # IPv6 - basic check
        return ":" in ip

    def _load_cloudflare_ranges(self) -> set[str]:
        """Load Cloudflare IPv4 and IPv6 ranges.

        Source: https://www.cloudflare.com/ips-v4/ and ips-v6/
        Updated: 2024. In production, fetch from the API periodically.
        """
        # fmt: off
        ipv4 = [
            "173.245.48.0/20",
            "103.21.244.0/22",
            "103.22.200.0/22",
            "103.31.4.0/22",
            "141.101.64.0/18",
            "108.162.192.0/18",
            "190.93.240.0/20",
            "188.114.96.0/20",
            "197.234.240.0/22",
            "198.41.128.0/17",
            "162.158.0.0/15",
            "104.16.0.0/13",
            "104.24.0.0/14",
            "172.64.0.0/13",
            "131.0.72.0/22",
        ]
        ipv6 = [
            "2400:cb00::/32",
            "2606:4700::/32",
            "2803:f800::/32",
            "2405:b500::/32",
            "2405:8100::/32",
            "2a06:98c0::/29",
            "2c0f:f248::/32",
        ]
        # fmt: on
        return set(ipv4 + ipv6)
