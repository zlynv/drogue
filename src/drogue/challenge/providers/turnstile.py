"""Cloudflare Turnstile provider.

Implements the :class:`ChallengeProvider` contract for Turnstile:
renders the standard widget and verifies tokens against Cloudflare's
Siteverify endpoint per the official server-side validation flow -
single-use 5-minute tokens, ``remoteip`` forwarding when available,
``action``/``hostname`` checks when configured, 5s default timeout,
and the neutral error taxonomy from ``drogue.challenge.base``.

Requires ``httpx`` (install drogue with the ``turnstile`` extra).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from drogue.challenge.base import (
    ChallengeErrorCode,
    ChallengeUnavailableError,
    ChallengeVerificationError,
    Verification,
)

_SERVER_SECRET_CODES: frozenset[str] = frozenset(
    {
        "missing-input-secret",
        "invalid-input-secret",
    }
)

_EXPIRED_ERROR_CODES: frozenset[str] = frozenset(
    {"timeout-or-duplicate"}
)


def _parse_solve_epoch(raw: Any) -> float | None:
    """Convert the ISO-8601 ``challenge_ts`` to an epoch float."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


class TurnstileProvider:
    """Cloudflare Turnstile verification provider.

    Usage::

        provider = TurnstileProvider(
            site_key="0x4AAAAAAA...",      # public, rendered in HTML
            secret="0x4AAAAAAA...",        # server-side only
        )

        verification = await provider.verify(token, remote_ip)

    For tests, inject ``client=<httpx.AsyncClient(MockTransport=...)>``
    to stub Siteverify without network access.
    """

    field_name = "drogue_token"
    siteverify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    script_url = "https://challenges.cloudflare.com/turnstile/v0/api.js"

    def __init__(
        self,
        site_key: str,
        secret: str,
        *,
        timeout: float = 5.0,
        action: str | None = None,
        expected_hostnames: list[str] | None = None,
        client: Any | None = None,
    ) -> None:
        if not site_key or not secret:
            raise ValueError(
                "TurnstileProvider requires both site_key and secret;"
                " pass secrets from the environment, never from code"
            )
        self.site_key = site_key
        self.secret = secret
        self.timeout = timeout
        self.action = action
        self.expected_hostnames = set(expected_hostnames or [])
        self._client = client

    def render_html(self) -> str:
        """Widget + token field, per Cloudflare's standard embed."""
        return (
            f"<script src=\"{self.script_url}\" async defer></script>"
            "<div class=\"cf-turnstile\""
            f" data-sitekey=\"{self.site_key}\""
            f" data-action=\"{self.action or ''}\""
            " data-theme=\"dark\"></div>"
            f"<input type=\"hidden\" name=\"{self.field_name}\""
            " value=\"\">"
        )

    def _form(self, token: str, remote_ip: str | None) -> dict[str, str]:
        form = {"secret": self.secret, "response": token}
        if remote_ip:
            form["remoteip"] = remote_ip
        return form

    async def _siteverify(
        self, token: str, remote_ip: str | None
    ) -> dict[str, Any]:
        """POST the token to Siteverify, returning the JSON response."""
        if self._client is not None:
            try:
                response = await self._client.post(
                    self.siteverify_url,
                    data=self._form(token, remote_ip),
                )
                return response.json()
            except Exception as exc:
                raise ChallengeUnavailableError(
                    "Siteverify request failed"
                ) from exc

        try:
            import httpx
        except ImportError as exc:
            raise ChallengeUnavailableError(
                "httpx is required for the Turnstile provider;"
                " install with: pip install drogue[turnstile]"
            ) from exc

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.siteverify_url,
                    data=self._form(token, remote_ip),
                )
                return response.json()
        except Exception as exc:
            raise ChallengeUnavailableError(
                "Siteverify request failed"
            ) from exc

    async def verify(
        self, token: str, remote_ip: str | None = None
    ) -> Verification:
        if not token:
            raise ChallengeVerificationError(
                ChallengeErrorCode.MISSING_TOKEN
            )
        if len(token) > 2048:
            raise ChallengeVerificationError(
                ChallengeErrorCode.REJECTED,
                provider_codes=["oversized-token"],
            )

        result = await self._siteverify(token, remote_ip)

        if not isinstance(result, dict) or "success" not in result:
            raise ChallengeUnavailableError(
                "Siteverify returned an unexpected response",
                provider_codes=["bad-response"],
            )

        provider_codes: list[str] = list(result.get("error-codes") or [])

        if not result["success"]:
            if not provider_codes or any(
                code in _SERVER_SECRET_CODES for code in provider_codes
            ):
                raise ChallengeUnavailableError(
                    "Siteverify rejected the configuration",
                    provider_codes=provider_codes or ["bad-secret"],
                )
            code = (
                ChallengeErrorCode.EXPIRED
                if any(c in _EXPIRED_ERROR_CODES for c in provider_codes)
                else ChallengeErrorCode.REJECTED
            )
            raise ChallengeVerificationError(
                code, provider_codes=provider_codes
            )

        hostname = result.get("hostname")
        if self.expected_hostnames and hostname not in self.expected_hostnames:
            raise ChallengeVerificationError(
                ChallengeErrorCode.REJECTED,
                message=f"hostname mismatch: {hostname}",
                provider_codes=["hostname-mismatch"],
            )
        action = result.get("action")
        if self.action and action != self.action:
            raise ChallengeVerificationError(
                ChallengeErrorCode.REJECTED,
                message=f"action mismatch: {action!r}",
                provider_codes=["action-mismatch"],
            )

        return Verification(
            action=action,
            hostname=hostname,
            solve_epoch=_parse_solve_epoch(result.get("challenge_ts")),
        )
