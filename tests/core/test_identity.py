"""Tests for identity extraction."""
from __future__ import annotations

from typing import Any

import pytest

from drogue.core.abstracts import CompositeExtractor
from drogue.core.identity.key import (
    HeaderExtractor,
    RemoteAddressExtractor,
    StaticKeyExtractor,
    UserExtractor,
)


class TestRemoteAddressExtractor:
    """Tests for IP-based identity extraction."""

    @pytest.fixture
    def extractor(self) -> RemoteAddressExtractor:
        return RemoteAddressExtractor()

    @pytest.mark.asyncio
    async def test_client_host(self, extractor: RemoteAddressExtractor) -> None:
        context = {"client": {"host": "192.168.1.1"}}
        result = await extractor.extract(context)
        assert result == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_x_real_ip_ignored_without_trusted_proxies(
        self, extractor: RemoteAddressExtractor
    ) -> None:
        # SECURITY: forwarded headers are attacker-controlled when no
        # trusted proxies are configured - must never be used as identity.
        context = {
            "client": {"host": "127.0.0.1"},
            "headers": {"x-real-ip": "203.0.113.1"},
        }
        result = await extractor.extract(context)
        assert result == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_x_forwarded_for_ignored_without_trusted_proxies(
        self, extractor: RemoteAddressExtractor
    ) -> None:
        context = {
            "client": {"host": "127.0.0.1"},
            "headers": {"x-forwarded-for": "203.0.113.1"},
        }
        result = await extractor.extract(context)
        assert result == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_spoofed_header_from_untrusted_peer(self) -> None:
        # SECURITY: peer is NOT in trusted_proxies - spoofed X-Real-IP ignored
        extractor = RemoteAddressExtractor(trusted_proxies=["10.0.0.5"])
        context = {
            "client": {"host": "6.6.6.6"},
            "headers": {"x-real-ip": "1.2.3.4"},
        }
        result = await extractor.extract(context)
        assert result == "6.6.6.6"

    @pytest.mark.asyncio
    async def test_x_forwarded_for_with_trusted_proxies(
        self,
    ) -> None:
        extractor = RemoteAddressExtractor(
            trusted_proxies=["192.168.1.1", "198.51.100.1"]
        )
        # The direct peer must be a trusted proxy for headers to be honored
        context = {
            "client": {"host": "192.168.1.1"},
            "headers": {"x-forwarded-for": "203.0.113.1, 198.51.100.1, 192.168.1.1"},
        }
        result = await extractor.extract(context)
        # Should return the first non-trusted IP (walking from right)
        assert result == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_x_real_ip_with_trusted_proxies(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["10.0.0.5"])
        context = {
            "client": {"host": "10.0.0.5"},
            "headers": {"x-real-ip": "203.0.113.1"},
        }
        result = await extractor.extract(context)
        assert result == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_invalid_ip_header_falls_back_to_peer(self) -> None:
        # SECURITY: junk header values must not poison storage keys
        extractor = RemoteAddressExtractor(trusted_proxies=["10.0.0.5"])
        context = {
            "client": {"host": "10.0.0.5"},
            "headers": {"x-real-ip": "not-an-ip<script>"},
        }
        result = await extractor.extract(context)
        assert result == "10.0.0.5"

    @pytest.mark.asyncio
    async def test_no_client(self, extractor: RemoteAddressExtractor) -> None:
        context: dict[str, Any] = {}
        result = await extractor.extract(context)
        assert result == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_bytes_header_value(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["10.0.0.5"])
        context = {
            "client": {"host": "10.0.0.5"},
            "headers": {"x-real-ip": b"203.0.113.1"},
        }
        result = await extractor.extract(context)
        assert result == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_cidr_trusted_proxy_honors_xff(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["192.168.1.0/24"])
        context = {
            "client": {"host": "192.168.1.42"},
            "headers": {"x-forwarded-for": "203.0.113.9, 192.168.1.42"},
        }
        result = await extractor.extract(context)
        assert result == "203.0.113.9"

    @pytest.mark.asyncio
    async def test_mapped_ipv6_peer_matches_cidr(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["10.0.0.0/24"])
        context = {
            "client": {"host": "::ffff:10.0.0.7"},
            "headers": {"x-real-ip": "203.0.113.9"},
        }
        result = await extractor.extract(context)
        assert result == "203.0.113.9"

    @pytest.mark.asyncio
    async def test_off_cidr_mapped_ipv6_peer_untrusted(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["10.0.0.0/24"])
        context = {
            "client": {"host": "::ffff:10.0.1.7"},
            "headers": {"x-real-ip": "203.0.113.9"},
        }
        result = await extractor.extract(context)
        assert result == "::ffff:10.0.1.7"

    @pytest.mark.asyncio
    async def test_unknown_string_entry_still_string_matches(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["edge-proxy-1"])
        context = {"client": {"host": "edge-proxy-1"}}
        result = await extractor.extract(context)
        # No headers follow, so the trusted proxy's own address is returned
        assert result == "edge-proxy-1"

    @pytest.mark.asyncio
    async def test_unknown_string_entry_does_not_match_other_peer(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["edge-proxy-1"])
        context = {
            "client": {"host": "10.0.0.5"},
            "headers": {"x-real-ip": "203.0.113.9"},
        }
        result = await extractor.extract(context)
        assert result == "10.0.0.5"

    @pytest.mark.asyncio
    async def test_invalid_trusted_entry_ignored(self) -> None:
        extractor = RemoteAddressExtractor(
            trusted_proxies=["not~an~ip!", "10.0.0.5"]
        )
        context = {
            "client": {"host": "10.0.0.5"},
            "headers": {"x-real-ip": "203.0.113.9"},
        }
        result = await extractor.extract(context)
        assert result == "203.0.113.9"

    @pytest.mark.asyncio
    async def test_invalid_entry_alone_does_not_trust_everything(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["not~an~ip!"])
        context = {
            "client": {"host": "10.0.0.5"},
            "headers": {"x-real-ip": "203.0.113.9"},
        }
        result = await extractor.extract(context)
        assert result == "10.0.0.5"

    @pytest.mark.asyncio
    async def test_xff_hop_cidr_trusted(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["198.51.100.0/24"])
        context = {
            "client": {"host": "198.51.100.7"},
            "headers": {"x-forwarded-for": "203.0.113.9, 198.51.100.8"},
        }
        result = await extractor.extract(context)
        assert result == "203.0.113.9"

    @pytest.mark.asyncio
    async def test_xff_all_hops_trusted_returns_leftmost(self) -> None:
        extractor = RemoteAddressExtractor(trusted_proxies=["198.51.100.0/24"])
        context = {
            "client": {"host": "198.51.100.7"},
            "headers": {"x-forwarded-for": "198.51.100.8"},
        }
        result = await extractor.extract(context)
        assert result == "198.51.100.8"


class TestUserExtractor:
    """Tests for user-based identity extraction."""

    @pytest.fixture
    def extractor(self) -> UserExtractor:
        return UserExtractor()

    @pytest.mark.asyncio
    async def test_user_id_in_context(self, extractor: UserExtractor) -> None:
        context = {"user_id": "user-123"}
        result = await extractor.extract(context)
        assert result == "user-123"

    @pytest.mark.asyncio
    async def test_user_id_in_state(self, extractor: UserExtractor) -> None:
        context = {"state": {"user_id": "user-456"}}
        result = await extractor.extract(context)
        assert result == "user-456"

    @pytest.mark.asyncio
    async def test_anonymous(self, extractor: UserExtractor) -> None:
        context: dict[str, Any] = {}
        result = await extractor.extract(context)
        assert result == "anonymous"


class TestHeaderExtractor:
    """Tests for header-based identity extraction."""

    @pytest.mark.asyncio
    async def test_extract_api_key(self) -> None:
        extractor = HeaderExtractor("x-api-key")
        context = {"headers": {"x-api-key": "my-secret-key"}}
        result = await extractor.extract(context)
        assert result == "my-secret-key"

    @pytest.mark.asyncio
    async def test_missing_header(self) -> None:
        extractor = HeaderExtractor("x-api-key")
        context: dict[str, Any] = {}
        result = await extractor.extract(context)
        assert result == "anonymous"

    @pytest.mark.asyncio
    async def test_clamps_value_to_256_chars(self) -> None:
        extractor = HeaderExtractor("x-api-key")
        context = {"headers": {"x-api-key": "A" * 300}}
        result = await extractor.extract(context)
        assert result == "A" * 256

    @pytest.mark.asyncio
    async def test_drops_non_printable_ascii(self) -> None:
        extractor = HeaderExtractor("x-api-key")
        context = {"headers": {"x-api-key": "he\xffllo\nwo\u00e9rld"}}
        result = await extractor.extract(context)
        assert result == "helloworld"

    @pytest.mark.asyncio
    async def test_bytes_value_sanitized(self) -> None:
        extractor = HeaderExtractor("x-api-key")
        context = {"headers": {"x-api-key": b"\x01key\r"}}
        result = await extractor.extract(context)
        assert result == "key"

    @pytest.mark.asyncio
    async def test_all_non_printable_falls_back(self) -> None:
        extractor = HeaderExtractor("x-api-key", fallback="anonymous")
        context = {"headers": {"x-api-key": "\u4e2d\u6587"}}
        result = await extractor.extract(context)
        assert result == "anonymous"


class TestStaticKeyExtractor:
    """Tests for static key extraction."""

    @pytest.mark.asyncio
    async def test_default_key(self) -> None:
        extractor = StaticKeyExtractor()
        result = await extractor.extract({})
        assert result == "global"

    @pytest.mark.asyncio
    async def test_custom_key(self) -> None:
        extractor = StaticKeyExtractor("my-endpoint")
        result = await extractor.extract({})
        assert result == "my-endpoint"


class TestCompositeExtractor:
    """Tests for composite extraction."""

    @pytest.mark.asyncio
    async def test_first_non_anonymous_wins(self) -> None:
        user_ext = UserExtractor()
        ip_ext = RemoteAddressExtractor()
        composite = CompositeExtractor(user_ext, ip_ext)

        context = {"user_id": "user-123", "client": {"host": "192.168.1.1"}}
        result = await composite.extract(context)
        assert result == "user-123"

    @pytest.mark.asyncio
    async def test_fallback_to_second(self) -> None:
        user_ext = UserExtractor()
        ip_ext = RemoteAddressExtractor()
        composite = CompositeExtractor(user_ext, ip_ext)

        context: dict[str, Any] = {"client": {"host": "192.168.1.1"}}
        result = await composite.extract(context)
        assert result == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_all_anonymous(self) -> None:
        user_ext = UserExtractor()
        header_ext = HeaderExtractor("x-custom")
        composite = CompositeExtractor(user_ext, header_ext)

        context: dict[str, Any] = {}
        result = await composite.extract(context)
        assert result == "anonymous"

    @pytest.mark.asyncio
    async def test_add_operator(self) -> None:
        ext1 = UserExtractor()
        ext2 = RemoteAddressExtractor()
        composite = ext1 + ext2

        assert isinstance(composite, CompositeExtractor)
