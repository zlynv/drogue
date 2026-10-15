"""Tests for DrogueConfig defaults and validation."""
from __future__ import annotations

import pytest

from drogue.core.config import DrogueConfig


def test_defaults_keep_new_defenses_off() -> None:
    config = DrogueConfig()
    assert config.probes_enabled is False
    assert config.trust_enabled is False
    assert config.sentinel_enabled is False
    assert config.randomizer_enabled is False
    assert config.honeypot_paths == []
    assert config.trust_limit_multiplier == 1.0
    assert config.sentinel_sample_rate == 0.01


def test_probes_retry_after_negative_rejected() -> None:
    with pytest.raises(ValueError):
        DrogueConfig(probes_retry_after=-1.0)


def test_trust_threshold_rejected() -> None:
    with pytest.raises(ValueError):
        DrogueConfig(trust_success_threshold=0)


def test_trust_multiplier_below_one_rejected() -> None:
    with pytest.raises(ValueError):
        DrogueConfig(trust_limit_multiplier=0.5)


@pytest.mark.parametrize("rate", [0.0, -0.5, 1.5])
def test_sentinel_sample_rate_out_of_range_rejected(rate: float) -> None:
    with pytest.raises(ValueError):
        DrogueConfig(sentinel_sample_rate=rate)


def test_randomizer_empty_header_rejected() -> None:
    with pytest.raises(ValueError):
        DrogueConfig(randomizer_session_header="")
