from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from drogue.core.rules.rule import RateLimitRule


class RuleResolver:
    """Resolves which rules apply to a given request context."""

    def __init__(self) -> None:
        self._rules: list[RateLimitRule] = []
        self._path_rules: dict[str, list[RateLimitRule]] = {}
        self._method_rules: dict[str, list[RateLimitRule]] = {}

    def add_rule(
        self,
        rule: RateLimitRule,
        paths: list[str] | None = None,
        methods: list[str] | None = None,
    ) -> None:
        """Register a rate limit rule."""
        self._rules.append(rule)
        if paths:
            for path in paths:
                self._path_rules.setdefault(path, []).append(rule)
        if methods:
            for method in methods:
                self._method_rules.setdefault(method.upper(), []).append(rule)

    def resolve(
        self,
        path: str,
        method: str = "GET",
    ) -> list[RateLimitRule]:
        """Find all rules that apply to the given path/method."""
        applicable: list[RateLimitRule] = []

        # Global rules
        for rule in self._rules:
            if rule.scope == "global" and self._matches(rule, path, method):
                applicable.append(rule)

        # Path-specific rules
        if path in self._path_rules:
            for rule in self._path_rules[path]:
                if self._matches(rule, path, method):
                    applicable.append(rule)

        # Method-specific rules
        method_upper = method.upper()
        if method_upper in self._method_rules:
            for rule in self._method_rules[method_upper]:
                if rule not in applicable and self._matches(rule, path, method):
                    applicable.append(rule)

        return applicable

    def _matches(self, rule: RateLimitRule, path: str, method: str) -> bool:
        """Check if a rule matches the given path/method."""
        if rule.methods and method.upper() not in [m.upper() for m in rule.methods]:
            return False
        if rule.paths and path not in rule.paths:
            return False
        return path not in rule.exempt_paths


class CostResolver:
    """Resolves the cost of a request based on rule configuration."""

    @staticmethod
    async def resolve_cost(
        rule: RateLimitRule,
        context: dict[str, Any] | None = None,
    ) -> int:
        """Calculate the cost for a request."""
        if callable(rule.cost):
            result = rule.cost(context or {})
            if hasattr(result, "__await__"):
                result = await result
            return max(1, int(result))
        return max(1, int(rule.cost))
