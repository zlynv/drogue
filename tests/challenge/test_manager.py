"""Tests for the ChallengeManager: cookies, replay, escalation, limits."""
from __future__ import annotations

import asyncio
import contextlib

import pytest

from drogue.challenge.base import (
    ChallengeErrorCode,
    ChallengeUnavailableError,
    ChallengeVerificationError,
    Verification,
    is_visitor_fixable,
)
from drogue.challenge.manager import ChallengeManager
from drogue.core.storage.memory import MemoryStorage

SIGNING = "x" * 32


class StubProvider:
    field_name = "drogue_token"

    def __init__(self, outcome: str = "ok") -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, str | None]] = []

    def render_html(self) -> str:
        return "<widget></widget>"

    async def verify(
        self, token: str, remote_ip: str | None
    ) -> Verification:
        self.calls.append((token, remote_ip))
        if self.outcome == "ok":
            return Verification()
        if self.outcome == "rejected":
            raise ChallengeVerificationError(
                ChallengeErrorCode.REJECTED, provider_codes=["code-x"]
            )
        if self.outcome == "expired":
            raise ChallengeVerificationError(
                ChallengeErrorCode.EXPIRED,
                provider_codes=["timeout-or-duplicate"],
            )
        raise ChallengeUnavailableError(provider_codes=["http-503"])


class FakeBan:
    def __init__(self) -> None:
        self.violations: list[str] = []

    def record_violation(self, key: str) -> None:
        self.violations.append(key)


class FakeTrust:
    def __init__(self) -> None:
        self.poisoned: list[str] = []
        self.updates: list[tuple[str, float]] = []

    def poison(self, key: str) -> bool:
        self.poisoned.append(key)
        return True

    def update(self, key: str, score: float) -> None:
        self.updates.append((key, score))


def make_manager(
    provider: StubProvider | None = None, **kwargs: object
) -> ChallengeManager:
    defaults: dict[str, object] = {
        "signing_key": SIGNING,
        "failure_threshold": 3,
        "challenge_rate_limit": 3,
        "challenge_rate_window": 60.0,
    }
    defaults.update(kwargs)
    return ChallengeManager(
        provider=provider or StubProvider(),
        storage=MemoryStorage(),
        **defaults,  # type: ignore[arg-type]
    )


def test_error_code_parsing() -> None:
    assert (
        ChallengeErrorCode("rejected") is ChallengeErrorCode.REJECTED
    )


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
        ChallengeErrorCode.EXPIRED, provider_codes=["timeout-or-duplicate"]
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


def test_signing_key_requirements() -> None:
    with pytest.raises(ValueError):
        ChallengeManager(
            provider=StubProvider(), storage=MemoryStorage(), signing_key="short"
        )


def test_failure_mode_validation() -> None:
    with pytest.raises(ValueError):
        ChallengeManager(
            provider=StubProvider(),
            storage=MemoryStorage(),
            signing_key=SIGNING,
            failure_mode="yolo",
        )


def test_pass_cookie_roundtrip() -> None:
    manager = make_manager()
    cookie = manager.issue_pass_cookie("1.2.3.4")
    assert manager.has_valid_pass({manager.cookie_name: cookie}, "1.2.3.4")


def test_pass_cookie_rejects_forgery() -> None:
    manager = make_manager()
    cookie = manager.issue_pass_cookie("1.2.3.4")
    forged = cookie[:-4] + "dead"
    assert not manager.has_valid_pass({manager.cookie_name: forged}, "1.2.3.4")


def test_pass_cookie_rejects_other_ip() -> None:
    manager = make_manager()
    cookie = manager.issue_pass_cookie("1.2.3.4")
    assert not manager.has_valid_pass({manager.cookie_name: cookie}, "9.9.9.9")


def test_pass_cookie_rejects_wrong_name() -> None:
    manager = make_manager()
    cookie = manager.issue_pass_cookie("1.2.3.4")
    assert not manager.has_valid_pass(
        {f"{manager.cookie_name}2": cookie}, "1.2.3.4"
    )


def test_pass_cookie_expires() -> None:
    frozen = 1_000_000.0
    manager = make_manager(now=lambda: frozen, cookie_ttl=100.0)
    cookie = manager.issue_pass_cookie("1.2.3.4")
    assert manager.has_valid_pass(
        {manager.cookie_name: cookie}, "1.2.3.4"
    )
    later = ChallengeManager(
        provider=StubProvider(),
        storage=MemoryStorage(),
        signing_key=SIGNING,
        cookie_ttl=100.0,
        now=lambda: frozen + 101.0,
    )
    assert not later.has_valid_pass({manager.cookie_name: cookie}, "1.2.3.4")


def test_replay_claim_single_use() -> None:
    async def run() -> None:
        manager = make_manager()
        assert await manager.claim_token("tok-1")
        assert not await manager.claim_token("tok-1")
        await manager.release_token("tok-1")
        assert await manager.claim_token("tok-1")

    asyncio.run(run())


def test_verify_success_trust_reward_and_cookie() -> None:
    async def run() -> None:
        provider = StubProvider()
        trust = FakeTrust()
        manager = make_manager(provider, trust=trust)
        ok = await manager.verify("tok", "1.2.3.4", "key-1")
        assert ok
        assert trust.updates == [("key-1", 1.0)]
        assert provider.calls == [("tok", "1.2.3.4")]
        stats = manager.get_stats()
        assert stats["passed"] == 1

    asyncio.run(run())


def test_verify_rejected_counts_failure_then_bans() -> None:
    async def run() -> tuple[ChallengeVerificationError | None, FakeBan]:
        provider = StubProvider("rejected")
        ban = FakeBan()
        manager = make_manager(provider, ban=ban, failure_threshold=3)
        err: ChallengeVerificationError | None = None
        # fresh token per attempt: rejected tokens stay single-use
        for i in range(3):
            try:
                await manager.verify(f"tok-{i}", "1.2.3.4", "1.2.3.4")
            except ChallengeVerificationError as exc:
                err = exc
        return err, ban

    err, ban = asyncio.run(run())
    assert err is not None
    assert err.code is ChallengeErrorCode.REJECTED
    assert ban.violations == ["1.2.3.4"]


def test_verify_replay_rejected_without_provider_call() -> None:
    async def run() -> int:
        provider = StubProvider()
        manager = make_manager(provider)
        assert await manager.claim_token("dup")
        with contextlib.suppress(ChallengeVerificationError):
            await manager.verify("dup", None, "1.2.3.4")
        return len(provider.calls)

    assert asyncio.run(run()) == 0


def test_verify_unavailable_releases_token() -> None:
    async def run() -> bool:
        provider = StubProvider("unavailable")
        manager = make_manager(provider)
        with contextlib.suppress(ChallengeUnavailableError):
            await manager.verify("tok", None, "1.2.3.4")
        # released: the token is claimable again
        return await manager.claim_token("tok")

    assert asyncio.run(run())


def test_verify_unavailable_fail_open() -> None:
    async def run() -> bool:
        provider = StubProvider("unavailable")
        manager = make_manager(provider, failure_mode="allow")
        allowed = await manager.verify("tok", None, "1.2.3.4")
        return allowed is False

    assert asyncio.run(run())


def test_verify_unavailable_fail_closed() -> None:
    async def run() -> bool:
        provider = StubProvider("unavailable")
        manager = make_manager(provider, failure_mode="block")
        try:
            await manager.verify("tok", None, "1.2.3.4")
        except ChallengeUnavailableError:
            return True
        return False

    assert asyncio.run(run())


def test_verify_rate_limited() -> None:
    async def run() -> None:
        manager = make_manager()
        seen_denied = False
        for _ in range(5):  # limit is 3
            if not await manager.allow_verify_request("1.2.3.4"):
                seen_denied = True
        assert seen_denied

    asyncio.run(run())


def test_verify_rate_limit_is_per_key() -> None:
    async def run() -> None:
        manager = make_manager()
        for _ in range(3):
            await manager.allow_verify_request("1.2.3.4")
        assert await manager.allow_verify_request("9.9.9.9")

    asyncio.run(run())


def test_should_serve_rules() -> None:
    assert ChallengeManager.should_serve(
        "GET", "text/html,application/xhtml+xml"
    )
    assert ChallengeManager.should_serve("get", "*/*")
    assert not ChallengeManager.should_serve("GET", "application/json")
    assert not ChallengeManager.should_serve("POST", "text/html")
    assert not ChallengeManager.should_serve("GET", None)


def test_sanitize_next_blocks_open_redirect() -> None:
    manager = make_manager()
    assert manager.sanitize_next("/page") == "/page"
    assert manager.sanitize_next("https://evil.com") == "/"
    assert manager.sanitize_next("//evil.com") == "/"
    assert manager.sanitize_next("") == "/"


def test_page_html_embeds_widget_and_next() -> None:
    manager = make_manager()
    page = manager.page_html("/reviews")
    assert "<widget>" in page
    assert "/reviews" in page
    assert manager.verify_url in page


def test_stats_track_flow() -> None:
    async def run() -> dict[str, int]:
        manager = make_manager()
        manager.page_html("/x")
        manager.issue_pass_cookie("1.1.1.1")
        await manager.verify("tk", None, "k")
        return manager.get_stats()

    stats = asyncio.run(run())
    assert stats["issued"] == 1
    assert stats["passed"] == 1


@pytest.mark.parametrize("attr", ["provider", "storage", "signing_key"])
def test_manager_requires_core_attrs(attr: str) -> None:
    manager = make_manager()
    assert hasattr(manager, attr)
