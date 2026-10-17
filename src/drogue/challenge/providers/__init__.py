"""Bundled :class:`ChallengeProvider` implementations.

Each provider ships as a separate extra to keep the core dependency
free: ``drogue[turnstile]``, ``drogue[recaptcha]``, ...
"""
from __future__ import annotations

from drogue.challenge.providers.turnstile import TurnstileProvider

__all__ = ["TurnstileProvider"]
