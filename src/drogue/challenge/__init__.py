"""Challenge escalation: CAPTCHA/PoW interstitials for page traffic.

When a human-visitable page exhausts its limits, serve an interactive
challenge instead of a bare 429. API traffic (and every request that
cannot render an interstitial) keeps the normal denial.

The provider abstraction is intentionally thin: a provider renders the
widget HTML and verifies a token server-side through the provider's
siteverify endpoint. The manager owns everything security-critical:
replay protection, signed pass cookies, failure escalation, and
challenge-endpoint rate limiting.
"""
from __future__ import annotations

from drogue.challenge.base import (
    ChallengeErrorCode,
    ChallengeProvider,
    ChallengeUnavailableError,
    ChallengeVerificationError,
    Verification,
)
from drogue.challenge.manager import ChallengeManager
from drogue.challenge.providers.turnstile import TurnstileProvider

__all__ = [
    "ChallengeErrorCode",
    "ChallengeProvider",
    "ChallengeUnavailableError",
    "ChallengeVerificationError",
    "ChallengeManager",
    "TurnstileProvider",
    "Verification",
]
