"""Provider contract and error taxonomy for challenges.

Every provider implements the one ``ChallengeProvider`` protocol, so
the manager, the adapter wiring and tests work identically over all of
them (Turnstile, reCAPTCHA, hCaptcha, Altcha, proof-of-work, ...).

The error taxonomy separates what the visitor can fix from what the
provider broke:

- ``rejected`` / ``expired`` / ``low-score`` / ``missing-token`` are
  visitor conditions - re-serve the challenge page.
- ``unavailable`` is a provider or network condition - follow the
  configured failure mode (block by default; low-value paths may
  opt into fail-open).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from drogue.core.errors import DrogueError


class ChallengeErrorCode(str, Enum):
    """Machine-readable verification failure categories."""

    # Conditions the visitor can fix by retrying the challenge.
    MISSING_TOKEN = "missing-token"
    REJECTED = "rejected"
    EXPIRED = "expired"
    LOW_SCORE = "low-score"

    # Conditions the visitor cannot fix: provider outage,
    # network failure, or a misconfigured server secret.
    UNAVAILABLE = "unavailable"


VISITOR_FIXABLE_CODES: frozenset[ChallengeErrorCode] = frozenset(
    {
        ChallengeErrorCode.MISSING_TOKEN,
        ChallengeErrorCode.REJECTED,
        ChallengeErrorCode.EXPIRED,
        ChallengeErrorCode.LOW_SCORE,
    }
)


class ChallengeVerificationError(DrogueError):  # noqa: N818
    """A challenge token failed verification.

    Carries the neutral :class:`ChallengeErrorCode` so callers can tell
    a retryable visitor condition from a provider outage without
    parsing provider-specific strings, plus the raw provider error
    codes for logging.
    """

    def __init__(
        self,
        code: ChallengeErrorCode | str,
        message: str = "Challenge verification failed",
        provider_codes: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = (
            code
            if isinstance(code, ChallengeErrorCode)
            else ChallengeErrorCode(code)
        )
        self.provider_codes = provider_codes or []


class ChallengeUnavailableError(ChallengeVerificationError):  # noqa: N818
    """The provider could not be reached or failed server-side.

    Raised for network errors, HTTP failures, timeouts, and invalid
    server-side secret configurations. Verification was not decided:
    the token should be released from the replay cache and the request
    handled by the configured failure mode.
    """

    def __init__(
        self,
        message: str = "Challenge provider unavailable",
        provider_codes: list[str] | None = None,
    ) -> None:
        super().__init__(
            ChallengeErrorCode.UNAVAILABLE,
            message=message,
            provider_codes=provider_codes,
        )


@dataclass(frozen=True)
class Verification:
    """Successful server-side verification result."""

    action: str | None = None
    hostname: str | None = None
    solve_epoch: float | None = None


@runtime_checkable
class ChallengeProvider(Protocol):
    """One contract for every challenge provider.

    Implement the protocol attribute and the two methods; the manager
    handles everything else (cookies, replay, escalation, rate
    limiting of the verify endpoint).
    """

    # Form field name the client widget submits the token in.
    field_name: str

    def render_html(self) -> str:
        """Return the widget HTML snippet for embedding in a form."""
        ...

    async def verify(
        self, token: str, remote_ip: str | None
    ) -> Verification:
        """Verify a token server-side.

        Returns a :class:`Verification` on success. Raises
        :class:`ChallengeVerificationError` (with a visitor-fixable
        code) for invalid, expired or low-scoring tokens, and
        :class:`ChallengeUnavailableError` when the provider could not
        decide (network, outage, server-side secret problems).
        """
        ...


def is_visitor_fixable(exc: ChallengeVerificationError) -> bool:
    """Whether re-serving the challenge can resolve the failure."""
    return exc.code in VISITOR_FIXABLE_CODES
