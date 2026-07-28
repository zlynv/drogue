"""Tests for rate limit rules and parsing."""
from __future__ import annotations

import pytest

from drogue.core.rules.rule import (
    AlgorithmType,
    RateLimitRule,
    parse_rule_string,
)


class TestRateLimitRule:
    """Tests for RateLimitRule dataclass."""

    def test_basic_rule(self) -> None:
        rule = RateLimitRule(limit=100, window=60.0)
        assert rule.limit == 100
        assert rule.window == 60.0
        assert rule.algorithm == AlgorithmType.TOKEN_BUCKET

    def test_custom_algorithm(self) -> None:
        rule = RateLimitRule(
            limit=10,
            window=1.0,
            algorithm=AlgorithmType.SLIDING_WINDOW,
        )
        assert rule.algorithm == AlgorithmType.SLIDING_WINDOW

    def test_invalid_limit(self) -> None:
        with pytest.raises(ValueError, match="limit must be >= 0"):
            RateLimitRule(limit=-1, window=60.0)

    def test_invalid_window(self) -> None:
        with pytest.raises(ValueError, match="window must be > 0"):
            RateLimitRule(limit=10, window=0)

    def test_frozen(self) -> None:
        rule = RateLimitRule(limit=10, window=1.0)
        with pytest.raises(AttributeError):
            rule.limit = 20  # type: ignore[misc]


class TestParseRuleString:
    """Tests for rate string parsing."""

    def test_parse_minute(self) -> None:
        rule = parse_rule_string("100/minute")
        assert rule.limit == 100
        assert rule.window == 60.0

    def test_parse_second(self) -> None:
        rule = parse_rule_string("10/second")
        assert rule.limit == 10
        assert rule.window == 1.0

    def test_parse_hour(self) -> None:
        rule = parse_rule_string("1000/hour")
        assert rule.limit == 1000
        assert rule.window == 3600.0

    def test_parse_day(self) -> None:
        rule = parse_rule_string("10000/day")
        assert rule.limit == 10000
        assert rule.window == 86400.0

    def test_parse_shorthand_s(self) -> None:
        rule = parse_rule_string("5/s")
        assert rule.limit == 5
        assert rule.window == 1.0

    def test_parse_shorthand_m(self) -> None:
        rule = parse_rule_string("5/m")
        assert rule.limit == 5
        assert rule.window == 60.0

    def test_parse_shorthand_h(self) -> None:
        rule = parse_rule_string("5/h")
        assert rule.limit == 5
        assert rule.window == 3600.0

    def test_parse_shorthand_d(self) -> None:
        rule = parse_rule_string("5/d")
        assert rule.limit == 5
        assert rule.window == 86400.0

    def test_parse_case_insensitive(self) -> None:
        rule = parse_rule_string("100/MINUTE")
        assert rule.limit == 100
        assert rule.window == 60.0

    def test_parse_with_spaces(self) -> None:
        rule = parse_rule_string("  100/minute  ")
        assert rule.limit == 100

    def test_parse_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid rate string"):
            parse_rule_string("invalid")

    def test_parse_invalid_unit(self) -> None:
        with pytest.raises(ValueError, match="Invalid rate string"):
            parse_rule_string("100/week")

    def test_parse_with_algorithm(self) -> None:
        rule = parse_rule_string(
            "100/minute",
            algorithm=AlgorithmType.FIXED_WINDOW,
        )
        assert rule.algorithm == AlgorithmType.FIXED_WINDOW

    def test_parse_with_block(self) -> None:
        rule = parse_rule_string("100/minute", block=True)
        assert rule.block is True
