"""Tests for the challenge error taxonomy and provider contract."""
from __future__ import annotations

import pytest

from drogue.challenge.base import (
    ChallengeErrorCode,
    ChallengeProvider,
    ChallengeUnavailableError,
    ChallengeVerificationError,
    Verification,
    is_visitor_fixable,
)


class _FakeProvider:
    field_name = "token"

    def render_html(self) -> str:
        return "<widget></widget>"

    async def verify(
        self, token: str, remote_ip: str | None
    ) -> Verification:
        return Verification()


def test_visitor_fixable_split() -> None:
    visitor = ChallengeVerificationError(
        ChallengeErrorCode.REJECTED, provider_codes=["invalid-input-response"]
    )
    dead = ChallengeUnavailableError()
    assert is_visitor_fixable(visitor)
    assert not is_visitor_fixable(dead)
    assert dead.code is ChallengeErrorCode.UNAVAILABLE


def test_provider_codes_carried() -> None:
    exc = ChallengeVerificationError(
        ChallengeErrorCode.EXPIRED,
        provider_codes=["timeout-or-duplicate"],
    )
    assert exc.provider_codes == ["timeout-or-duplicate"]
    assert exc.code is ChallengeErrorCode.EXPIRED


def test_code_accepts_raw_strings() -> None:
    assert ChallengeVerificationError("low-score").code is (
        ChallengeErrorCode.LOW_SCORE
    )


def test_unknown_code_raises() -> None:
    with pytest.raises(ValueError):
        ChallengeVerificationError("not-a-code")


def test_protocol_runtime_checkable() -> None:
    assert isinstance(_FakeProvider(), ChallengeProvider)


def test_unavailable_carries_provider_codes() -> None:
    dead = ChallengeUnavailableError(provider_codes=["oh-no"])
    assert dead.provider_codes == ["oh-no"]
    assert dead.code is ChallengeErrorCode.UNAVAILABLE
