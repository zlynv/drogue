"""Bundled :class:`ChallengeProvider` implementations.

The Turnstile provider ships as its own extra (``drogue[turnstile]``)
to keep the core dependency free; see ``drogue.challenge.base`` for
the protocol when writing your own.
"""
from __future__ import annotations

from drogue.challenge.providers.turnstile import TurnstileProvider

__all__ = ["TurnstileProvider"]
