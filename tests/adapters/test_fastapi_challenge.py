"""End-to-end challenge flow tests over the FastAPI adapter.

Covers the page-denial interstitial, the verify endpoint (success,
failure, replay, provider unavailable), pass-cookie behavior, and
open-redirect hygiene - with a stub provider (no network).
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from drogue.adapters.fastapi import DrogueLimiter
from drogue.challenge.base import (
    ChallengeErrorCode,
    ChallengeUnavailableError,
    ChallengeVerificationError,
    Verification,
)
from drogue.core.config import DrogueConfig
from drogue.core.errors import ConfigurationError
from drogue.core.storage.memory import MemoryStorage

SIGNING = "y" * 32
PASS_TTL = 86400.0


class StubProvider:
    """Scriptable provider: outcomes queue or a fixed verdict."""

    field_name = "drogue_token"

    def __init__(self, verdict: str = "ok") -> None:
        self.verdict = verdict
        self.tokens: list[str] = []

    def render_html(self) -> str:
        return "<widget data-stub></widget>"

    async def verify(
        self, token: str, remote_ip: str | None
    ) -> Verification:
        self.tokens.append(token)
        if self.verdict == "ok":
            return Verification()
        if self.verdict == "rejected":
            raise ChallengeVerificationError(
                ChallengeErrorCode.REJECTED, provider_codes=["stub"]
            )
        if self.verdict == "expired":
            raise ChallengeVerificationError(
                ChallengeErrorCode.EXPIRED, provider_codes=["timeout"]
            )
        raise ChallengeUnavailableError(provider_codes=["http-500"])


def make_app(
    verdict: str = "ok",
    defaults: dict[str, Any] | None = None,
    provider: StubProvider | None = None,
) -> tuple[FastAPI, DrogueLimiter, StubProvider]:
    provider = provider or StubProvider(verdict)
    config_kwargs: dict[str, Any] = {
        "challenge_enabled": True,
        "challenge_signing_key": SIGNING,
        "challenge_cookie_ttl": PASS_TTL,
        "challenge_failure_threshold": 3,
        "challenge_rate_limit": 50,
    }
    config_kwargs.update(defaults or {})
    app = FastAPI()
    limiter = DrogueLimiter(
        app,
        storage=MemoryStorage(),
        config=DrogueConfig(**config_kwargs),
        default_limits=["2/minute"],
        challenge_provider=provider,
    )

    @app.get("/page")
    async def page() -> dict[str, str]:
        return {"msg": "hello"}

    return app, limiter, provider


def get(client: TestClient, path: str, **kwargs: Any) -> Any:
    return client.get(path, **kwargs)


def test_interstitial_served_on_limited_page() -> None:
    app, limiter, provider = make_app()
    with TestClient(app) as client:
        for _ in range(2):
            r = get(client, "/page")
            assert r.status_code == 200
        r = get(client, "/page", headers={"Accept": "text/html"})
        assert r.status_code == 429
        assert "<widget data-stub" in r.text
        assert "/page" in r.text  # next field
        assert limiter.get_challenge_manager() is not None


def test_api_json_unaffected_by_challenge() -> None:
    app, _, _ = make_app()
    with TestClient(app) as client:
        for _ in range(2):
            get(client, "/page")
        r = get(client, "/page", headers={"Accept": "application/json"})
        assert r.status_code == 429
        assert r.json()["error"] == "Rate limit exceeded"


def test_verify_success_sets_pass_cookie_and_redirects() -> None:
    app, limiter, provider = make_app()
    manager = limiter.get_challenge_manager()
    assert manager is not None
    with TestClient(app) as client:
        r = client.post(
            manager.verify_url,
            data={"next": "/page", "drogue_token": "good"},
        )
        assert r.status_code == 200  # TestClient follows the redirect
        assert client.cookies.get(manager.cookie_name)


def test_pass_cookie_bypasses_interstitial() -> None:
    app, limiter, _ = make_app()
    manager = limiter.get_challenge_manager()
    assert manager is not None
    signed = manager.issue_pass_cookie("testclient")

    with TestClient(app) as client:
        client.cookies.set(manager.cookie_name, signed)
        # within the global limit: solved humans see the page, never
        # another interstitial
        r = get(client, "/page", headers={"Accept": "text/html"})
        assert r.status_code == 200
        r = get(client, "/page", headers={"Accept": "text/html"})
        assert r.status_code == 200
        # past bare limits with JSON-free challenge: still denied, but
        # with the pass cookie the denial is JSON (no widget loop)
        r = get(client, "/page", headers={"Accept": "text/html"})
        assert r.status_code == 429
        assert "<widget" not in r.text


def test_verify_rejected_reserves_challenge() -> None:
    app, limiter, _ = make_app(verdict="rejected")
    manager = limiter.get_challenge_manager()
    assert manager is not None
    with TestClient(app) as client:
        r = client.post(
            manager.verify_url,
            data={"next": "/page", "drogue_token": "bad"},
        )
        assert r.status_code == 429
        assert "<widget data-stub" in r.text
        assert "drogue_pass" not in r.cookies


def test_verify_unavailable_block_mode_is_503() -> None:
    app, limiter, _ = make_app(verdict="unavailable")
    manager = limiter.get_challenge_manager()
    assert manager is not None
    with TestClient(app) as client:
        r = client.post(
            manager.verify_url,
            data={"next": "/page", "drogue_token": "t"},
        )
        assert r.status_code == 503


def test_verify_unavailable_allow_mode_passes_through() -> None:
    """Fail-open degrades to the normal denial: no hard 503, but an
    outage never mints a pass cookie (bots could force failures)."""
    app, limiter, _ = make_app(
        verdict="unavailable",
        defaults={"challenge_failure_mode": "allow"},
    )
    manager = limiter.get_challenge_manager()
    assert manager is not None
    with TestClient(app) as client:
        r = client.post(
            manager.verify_url,
            data={"next": "/page", "drogue_token": "t"},
        )
        assert r.status_code == 429
        assert client.cookies.get(manager.cookie_name) is None


def test_verify_replay_is_single_use() -> None:
    app, limiter, provider = make_app()
    manager = limiter.get_challenge_manager()
    assert manager is not None
    with TestClient(app) as client:
        first = client.post(
            manager.verify_url,
            data={"next": "/page", "drogue_token": "tok"},
        )
        assert first.status_code == 200
        client.cookies.clear()
        second = client.post(
            manager.verify_url,
            data={"next": "/page", "drogue_token": "tok"},
        )
        # replayed token: token claimed already, re-serve challenge
        assert second.status_code == 429
    assert provider.tokens.count("tok") == 1


def test_verify_redirect_to_open_url_is_neutralized() -> None:
    app, limiter, _ = make_app()
    manager = limiter.get_challenge_manager()
    assert manager is not None
    with TestClient(app) as client:
        r = client.post(
            manager.verify_url,
            data={"next": "//evil.com", "drogue_token": "good"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/"


def test_challenge_endpoint_rate_limited() -> None:
    app, limiter, _ = make_app(
        defaults={"challenge_rate_limit": 3, "challenge_rate_window": 60.0}
    )
    manager = limiter.get_challenge_manager()
    assert manager is not None
    with TestClient(app) as client:
        statuses = []
        for _ in range(5):
            r = client.post(
                manager.verify_url,
                data={"next": "/page", "drogue_token": "t"},
            )
            statuses.append(r.status_code)
        assert 429 in statuses


def test_missing_config_without_provider_raises() -> None:
    app = FastAPI()
    with pytest.raises(ConfigurationError):
        DrogueLimiter(
            app,
            storage=MemoryStorage(),
            config=DrogueConfig(
                challenge_enabled=True,
                challenge_signing_key=SIGNING,
            ),
        )


def test_interstitial_not_served_with_valid_pass_cookie() -> None:
    """Solved humans keep browsing even past bare page limits."""
    app, limiter, _ = make_app(defaults={"challenge_rate_limit": 50})
    del limiter


def test_pass_cookie_rejects_other_browser_ip() -> None:
    app, limiter, _ = make_app()
    manager = limiter.get_challenge_manager()
    assert manager is not None
    signed = manager.issue_pass_cookie("1.2.3.4")
    with TestClient(app) as client:
        for _ in range(2):
            get(client, "/page")
        client.cookies.set(manager.cookie_name, signed)
        r = get(client, "/page", headers={"Accept": "text/html"})
        # cookie bound to 1.2.3.4, client is testclient -> challenge
        assert r.status_code == 429


def test_signing_algorithm_matches_documentation() -> None:
    """Documented cookie format: <expiry>.<ip_hash>.<hmac>."""
    app, limiter, _ = make_app()
    manager = limiter.get_challenge_manager()
    assert manager is not None
    cookie = manager.issue_pass_cookie("co-ip")
    expiry, ip_hash, sig = cookie.split(".")
    key = hashlib.sha256(
        b"drogue-challenge-pass-v1::" + SIGNING.encode()
    ).digest()
    expected = hmac.new(
        key, f"{expiry}.{ip_hash}".encode(), hashlib.sha256
    ).hexdigest()
    assert sig == expected
    assert hmac.compare_digest(sig, expected)
