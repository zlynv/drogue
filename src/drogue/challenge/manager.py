"""Challenge manager: the security-critical side of challenge flows.

Owns everything providers must not be trusted with:

- signed pass cookies (HMAC-SHA256, expiry + client binding so a
  solved cookie cannot be shared or forged across a farm),
- single-use token claims (replay protection via storage
  compare-and-swap, claimed before the provider round-trip),
- failed-verification counters with escalation to the ban manager
  and trust poisoning,
- rate limiting of the verify endpoint itself, so the challenge page
  cannot become the DoS vector,
- serving rules: interstitials only for GET requests that accept
  HTML ``text/html``.
"""
from __future__ import annotations

import hashlib
import hmac
import html as html_escape
import logging
import time
from typing import TYPE_CHECKING, Any

from drogue.challenge.base import (
    ChallengeErrorCode,
    ChallengeProvider,
    ChallengeUnavailableError,
    ChallengeVerificationError,
    is_visitor_fixable,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from drogue.core.abstracts import Storage

logger = logging.getLogger("drogue.challenge")

_PROTOCOL_PREFIX = b"drogue-challenge-pass-v1::"
_TOKEN_KEY_PREFIX = "drogue:challenge:token:"
_FAILURE_KEY_PREFIX = "drogue:challenge:failures:"
_REQUEST_KEY_PREFIX = "drogue:challenge:requests:"


class ChallengeManager:
    """Flow manager for CAPTCHA/PoW challenges on page traffic.

    Usage::

        from drogue.challenge import ChallengeManager, TurnstileProvider

        manager = ChallengeManager(
            provider=TurnstileProvider(site_key, secret),
            storage=limiter.storage,
            signing_key=app_secret,  # dedicated, >= 32 chars
        )

        # In the page-denial path:
        if not manager.has_valid_pass(cookies, client_ip):
            return HTMLResponse(manager.page_html(...), status_code=429)

        # In the verify endpoint:
        claimed = await manager.claim_token(token)
        ...
    """

    def __init__(
        self,
        provider: ChallengeProvider,
        storage: Storage,
        *,
        signing_key: str,
        cookie_name: str = "drogue_pass",
        cookie_ttl: float = 86400.0,
        token_ttl: float = 300.0,
        failure_mode: str = "block",
        failure_threshold: int = 3,
        failure_window: float = 300.0,
        challenge_rate_limit: int = 20,
        challenge_rate_window: float = 60.0,
        verify_url: str = "/drogue/verify",
        page_title: str = "Are you human?",
        page_message: str = (
            "Too many requests from your network. Please complete the"
            " check below to continue."
        ),
        ban: Any | None = None,
        trust: Any | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        if not signing_key or len(signing_key) < 32:
            raise ValueError(
                "signing_key must be at least 32 characters; use a secret"
                " separate from the provider secret (openssl rand -hex 32)"
            )
        if failure_mode not in ("block", "allow"):
            raise ValueError("failure_mode must be 'block' or 'allow'")
        self.provider = provider
        self.storage = storage
        self.signing_key = signing_key
        self.cookie_name = cookie_name
        self.cookie_ttl = cookie_ttl
        self.token_ttl = token_ttl
        self.failure_mode = failure_mode
        self.failure_threshold = failure_threshold
        self.failure_window = failure_window
        self.challenge_rate_limit = challenge_rate_limit
        self.challenge_rate_window = challenge_rate_window
        self.verify_url = verify_url
        self.page_title = page_title
        self.page_message = page_message
        self._ban = ban
        self._trust = trust
        self._now = now or time.time
        self._cookie_key = hashlib.sha256(_PROTOCOL_PREFIX + signing_key.encode()).digest()
        self._stats: dict[str, int] = {
            "issued": 0,
            "passed": 0,
            "failed": 0,
            "banned": 0,
            "rate_limited": 0,
        }

    # ------------------------------------------------------------------
    # Serving rules
    # ------------------------------------------------------------------

    @staticmethod
    def should_serve(method: str, accept: str | None) -> bool:
        """Whether this request can be answered with an interstitial.

        Only GET requests whose Accept header invites HTML can render a
        challenge page; everything else (POST bodies, CORS preflights,
        API clients) must keep the normal denial.
        """
        if method.upper() != "GET":
            return False
        if not accept:
            return False
        accept = accept.lower()
        return "text/html" in accept or "*/*" in accept

    # ------------------------------------------------------------------
    # Signed pass cookies
    # ------------------------------------------------------------------

    def _ip_hash(self, client_ip: str) -> str:
        return hashlib.sha256(client_ip.encode()).hexdigest()[:16]

    def _sign(self, expiry: int, ip_hash: str) -> str:
        message = f"{expiry}.{ip_hash}".encode()
        return hmac.new(
            self._cookie_key, message, hashlib.sha256
        ).hexdigest()

    def issue_pass_cookie(self, client_ip: str) -> str:
        """Return the signed pass-cookie value for this client."""
        expiry = int(self._now()) + int(self.cookie_ttl)
        ip_hash = self._ip_hash(client_ip)
        return f"{expiry}.{ip_hash}.{self._sign(expiry, ip_hash)}"

    def has_valid_pass(
        self, cookies: Mapping[str, str] | None, client_ip: str
    ) -> bool:
        """Validate a pass cookie against signature, expiry and binding."""
        if not cookies:
            return False
        raw = cookies.get(self.cookie_name)
        if not raw:
            return False
        parts = raw.split(".", 2)
        if len(parts) != 3:
            return False
        expiry_str, cookie_ip_hash, provided_sig = parts
        try:
            expiry = int(expiry_str)
        except ValueError:
            return False
        if expiry < int(self._now()):
            return False
        ip_hash = self._ip_hash(client_ip)
        if not hmac.compare_digest(ip_hash, cookie_ip_hash):
            return False
        expected = self._sign(expiry, ip_hash)
        return hmac.compare_digest(expected, provided_sig)

    # ------------------------------------------------------------------
    # Replay claims (single-use tokens)
    # ------------------------------------------------------------------

    def _token_key(self, token: str) -> str:
        digest = hashlib.sha256(token.encode()).hexdigest()
        return f"{_TOKEN_KEY_PREFIX}{digest}"

    async def claim_token(self, token: str) -> bool:
        """Claim a token before the provider round-trip.

        Returns False when the token was already used, which rejects a
        concurrent replay before both callers could hit the provider.
        """
        return await self.storage.compare_and_swap(
            self._token_key(token), None, "1", self.token_ttl
        )

    async def release_token(self, token: str) -> None:
        """Release a claim after an undecided provider failure.

        Only for ``ChallengeUnavailableError``: provider-rejected
        tokens stay claimed, they are dead for the whole TTL.
        """
        await self.storage.delete(self._token_key(token))

    # ------------------------------------------------------------------
    # Failure escalation
    # ------------------------------------------------------------------

    async def record_failure(self, key: str) -> None:
        """Count a failed verification, escalate past the threshold."""
        self._stats["failed"] += 1
        storage_key = f"{_FAILURE_KEY_PREFIX}{key}"
        failures, _ = await self.storage.increment_by(
            storage_key, 1, self.failure_window
        )
        if failures < self.failure_threshold:
            return
        self._stats["banned"] += 1
        if self._ban is not None:
            self._ban.record_violation(key)
        if self._trust is not None:
            self._trust.poison(key)

    # ------------------------------------------------------------------
    # Verify-endpoint rate limiting
    # ------------------------------------------------------------------

    async def allow_verify_request(self, key: str) -> bool:
        """Whether this client may attempt a verification now.

        Protects the challenge endpoint itself from becoming a flood
        vector: unsolved and failed attempts are cheap to generate.
        """
        storage_key = f"{_REQUEST_KEY_PREFIX}{key}"
        requests, _ = await self.storage.increment_by(
            storage_key, 1, self.challenge_rate_window
        )
        allowed = requests <= self.challenge_rate_limit
        if not allowed:
            self._stats["rate_limited"] += 1
        return allowed

    # ------------------------------------------------------------------
    # Page rendering
    # ------------------------------------------------------------------

    def sanitize_next(self, raw: str) -> str:
        """Validate a client-supplied redirect target.

        Only same-site relative paths survive: absolute URLs (open
        redirects) and protocol-relative (``//evil.com``) collapse to
        ``/``.
        """
        if (
            not raw
            or not raw.startswith("/")
            or raw.startswith("//")
            or "\\" in raw
        ):
            return "/"
        return raw

    def page_html(self, next_url: str = "/") -> str:
        """Full interstitial HTML for the challenge page."""
        self._stats["issued"] += 1
        next_url = self.sanitize_next(next_url)
        return (
            "<!DOCTYPE html>"
            "<html>"
            "<head>"
            "<meta charset=\"utf-8\">"
            f"<title>{html_escape.escape(self.page_title)}</title>"
            "<style>"
            "body{font-family:system-ui,sans-serif;margin:0;"
            "background:#0b0f14;color:#e5e7eb;"
            "display:flex;align-items:center;justify-content:center;"
            "min-height:100vh}"
            ".card{background:#111827;border:1px solid #1f2937;"
            "border-radius:12px;padding:32px;max-width:360px;"
            "text-align:center}"
            "h1{font-size:20px;margin:0 0 8px;color:#fff}"
            "p{font-size:14px;color:#9ca3af;margin:0 0 24px}"
            "form{display:flex;flex-direction:column;align-items:center;"
            "gap:16px}"
            "button{background:#3b82f6;border:0;border-radius:6px;"
            "color:#fff;cursor:pointer;font-weight:600;padding:10px 24px}"
            "</style>"
            "</head>"
            "<body>"
            "<div class=\"card\">"
            f"<h1>{html_escape.escape(self.page_title)}</h1>"
            f"<p>{html_escape.escape(self.page_message)}</p>"
            f"<form method=\"POST\" action=\"{html_escape.escape(self.verify_url)}\">"
            f"<input type=\"hidden\" name=\"next\" value=\"{html_escape.escape(next_url)}\">"
            f"{self.provider.render_html()}"
            "<button type=\"submit\">Continue</button>"
            "</form>"
            "</div>"
            "</body>"
            "</html>"
        )

    # ------------------------------------------------------------------
    # Verification pipeline
    # ------------------------------------------------------------------

    async def verify(
        self, token: str, remote_ip: str | None, key: str
    ) -> bool:
        """Run the full verification pipeline for one token.

        Claims the token (replay protection), calls the provider,
        escalates failures, and returns ``True`` on success. Raises
        :class:`ChallengeVerificationError` on failure - catch and
        re-serve the challenge page, or short-circuit unavailable
        failures through ``failure_mode``.
        """
        if not token:
            raise ChallengeVerificationError(
                ChallengeErrorCode.MISSING_TOKEN
            )
        if not await self.claim_token(token):
            raise ChallengeVerificationError(
                ChallengeErrorCode.MISSING_TOKEN,
                message="Challenge token already used",
                provider_codes=["replay"],
            )
        try:
            await self.provider.verify(token, remote_ip)
        except ChallengeUnavailableError:
            await self.release_token(token)
            if self.failure_mode == "block":
                raise
            logger.warning(
                "challenge: provider unavailable in fail-open mode,"
                " allowing %s flagged",
                key,
            )
            return False
        except ChallengeVerificationError as exc:
            await self.record_failure(key)
            if not is_visitor_fixable(exc):
                raise
            logger.info("challenge: verification failed for %s: %s", key, exc.code)
            raise
        self._stats["passed"] += 1
        if self._trust is not None:
            self._trust.update(key, 1.0)
        return True

    def get_stats(self) -> dict[str, int]:
        """Aggregated challenge-flow counters."""
        return dict(self._stats)
