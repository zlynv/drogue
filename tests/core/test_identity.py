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
    async def test_x_real_ip(self, extractor: RemoteAddressExtractor) -> None:
        context = {
            "client": {"host": "127.0.0.1"},
            "headers": {"x-real-ip": "203.0.113.1"},
        }
        result = await extractor.extract(context)
        assert result == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_x_forwarded_for_single(self, extractor: RemoteAddressExtractor) -> None:
        context = {
            "client": {"host": "127.0.0.1"},
            "headers": {"x-forwarded-for": "203.0.113.1"},
        }
        result = await extractor.extract(context)
        assert result == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_x_forwarded_for_multi_hop(self, extractor: RemoteAddressExtractor) -> None:
        # Client -> Proxy1 -> Proxy2
        context = {
            "client": {"host": "127.0.0.1"},
            "headers": {"x-forwarded-for": "203.0.113.1, 198.51.100.1, 192.168.1.1"},
        }
        result = await extractor.extract(context)
        # Without trusted proxies, returns leftmost (client)
        assert result == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_x_forwarded_for_with_trusted_proxies(
        self,
    ) -> None:
        extractor = RemoteAddressExtractor(
            trusted_proxies=["192.168.1.1", "198.51.100.1"]
        )
        context = {
            "client": {"host": "127.0.0.1"},
            "headers": {"x-forwarded-for": "203.0.113.1, 198.51.100.1, 192.168.1.1"},
        }
        result = await extractor.extract(context)
        # Should return the first non-trusted IP (walking from right)
        assert result == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_no_client(self, extractor: RemoteAddressExtractor) -> None:
        context: dict[str, Any] = {}
        result = await extractor.extract(context)
        assert result == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_bytes_header_value(self, extractor: RemoteAddressExtractor) -> None:
        context = {
            "client": {"host": "127.0.0.1"},
            "headers": {"x-real-ip": b"203.0.113.1"},
        }
        result = await extractor.extract(context)
        assert result == "203.0.113.1"


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
