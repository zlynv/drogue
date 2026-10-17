"""Tests for the Turnstile provider against a stubbed Siteverify API."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import pytest

from drogue.challenge.base import (
    ChallengeErrorCode,
    ChallengeUnavailableError,
    ChallengeVerificationError,
    Verification,
)
from drogue.challenge.providers.turnstile import TurnstileProvider

_EXPECTED_TS = datetime(2026, 10, 17, 10, 0, tzinfo=UTC).timestamp()


def transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    """MockTransport serving queued responses per request."""

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.pop(0)
        response.request = request
        return response

    return httpx.MockTransport(handler)


def make_provider(
    responses: list[httpx.Response], **kwargs: object
) -> TurnstileProvider:
    client = httpx.AsyncClient(transport=transport(responses))
    defaults: dict[str, object] = {
        "site_key": "site",
        "secret": "secret",
        "client": client,
    }
    defaults.update(kwargs)
    return TurnstileProvider(**defaults)  # type: ignore[arg-type]


def ok_response(**overrides: object) -> httpx.Response:
    body: dict[str, object] = {
        "success": True,
        "challenge_ts": "2026-10-17T10:00:00.000Z",
        "hostname": "example.com",
        "action": "browse",
        "error-codes": [],
    }
    body.update(overrides)  # type: ignore[arg-type]
    return httpx.Response(200, json=body)


def failed_response(codes: list[str]) -> httpx.Response:
    return httpx.Response(
        200, json={"success": False, "error-codes": codes}
    )


def run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


def test_requires_credentials() -> None:
    with pytest.raises(ValueError):
        TurnstileProvider(site_key="", secret="s")
    with pytest.raises(ValueError):
        TurnstileProvider(site_key="k", secret="")


def test_render_html_embeds_site_key() -> None:
    provider = make_provider([])
    page = provider.render_html()
    assert provider.site_key in page
    assert provider.field_name in page
    assert "challenges.cloudflare.com" in page


def test_verify_empty_token_raises() -> None:
    provider = make_provider([])
    with pytest.raises(ChallengeVerificationError) as exc:
        run(provider.verify("", None))
    assert exc.value.code is ChallengeErrorCode.MISSING_TOKEN


def test_verify_oversized_token_rejected() -> None:
    provider = make_provider([])
    with pytest.raises(ChallengeVerificationError) as exc:
        run(provider.verify("t" * 2049, None))
    assert exc.value.code is ChallengeErrorCode.REJECTED

def test_verify_success() -> None:
    provider = make_provider([ok_response()])
    verification = run(provider.verify("tok", "1.2.3.4"))
    assert isinstance(verification, Verification)
    assert verification.hostname == "example.com"
    assert verification.action == "browse"
    assert verification.solve_epoch == _EXPECTED_TS


def test_verify_sends_secret_and_remote_ip() -> None:
    calls: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.update(
            {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        )
        response = ok_response()
        response.request = request
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = TurnstileProvider("site", "secret", client=client)
    run(provider.verify("tok", "1.2.3.4"))
    assert calls["secret"] == "secret"
    assert calls["response"] == "tok"
    assert calls["remoteip"] == "1.2.3.4"


def test_verify_remote_ip_omitted_when_none() -> None:
    calls: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.update(
            {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        )
        response = ok_response()
        response.request = request
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = TurnstileProvider("site", "secret", client=client)
    run(provider.verify("tok", None))
    assert "remoteip" not in calls


def test_verify_invalid_token_rejected() -> None:
    provider = make_provider([failed_response(["invalid-input-response"])])
    with pytest.raises(ChallengeVerificationError) as exc:
        run(provider.verify("tok", None))
    assert exc.value.code is ChallengeErrorCode.REJECTED
    assert exc.value.provider_codes == ["invalid-input-response"]


def test_verify_expired_token() -> None:
    provider = make_provider([failed_response(["timeout-or-duplicate"])])
    with pytest.raises(ChallengeVerificationError) as exc:
        run(provider.verify("tok", None))
    assert exc.value.code is ChallengeErrorCode.EXPIRED


def test_verify_bad_secret_is_unavailable() -> None:
    provider = make_provider([failed_response(["invalid-input-secret"])])
    with pytest.raises(ChallengeUnavailableError):
        run(provider.verify("tok", None))


def test_verify_hostname_mismatch_rejected() -> None:
    provider = make_provider(
        [ok_response()],
        expected_hostnames=["other.com"],
    )
    with pytest.raises(ChallengeVerificationError) as exc:
        run(provider.verify("tok", None))
    assert exc.value.provider_codes == ["hostname-mismatch"]


def test_verify_hostname_ok() -> None:
    provider = make_provider(
        [ok_response()], expected_hostnames=["example.com"]
    )
    verification = run(provider.verify("tok", None))
    assert verification.hostname == "example.com"


def test_verify_action_mismatch_rejected() -> None:
    provider = make_provider([ok_response()], action="strict-action")
    with pytest.raises(ChallengeVerificationError) as exc:
        run(provider.verify("tok", None))
    assert exc.value.provider_codes == ["action-mismatch"]


def test_verify_action_ok() -> None:
    provider = make_provider([ok_response()], action="browse")
    verification = run(provider.verify("tok", None))
    assert verification.action == "browse"


def test_verify_network_error_unavailable() -> None:
    provider = make_provider([])  # empty queue for the handler -> KeyError
    with pytest.raises(ChallengeUnavailableError):
        run(provider.verify("tok", None))


def test_verify_bad_response_shape_unavailable() -> None:
    provider = make_provider([httpx.Response(200, json={"weird": 1})])
    with pytest.raises(ChallengeUnavailableError):
        run(provider.verify("tok", None))


def test_solve_epoch_parses_iso() -> None:
    from drogue.challenge.providers.turnstile import _parse_solve_epoch

    assert _parse_solve_epoch("2026-10-17T10:00:00.000Z") == _EXPECTED_TS
    assert _parse_solve_epoch("garbage") is None
    assert _parse_solve_epoch(None) is None
