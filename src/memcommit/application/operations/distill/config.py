"""Typed semantic limits for Distill.

The values live outside the operation decoder so public adapters can freeze one
configuration snapshot and tests can exercise smaller bounds without patching
module globals.  Provider credentials, endpoints, and model selection remain
owned by provider infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DistillSemanticConfig:
    """One validated, interface-independent Distill limit snapshot."""

    # Distill must recover the complete supported Rule set. A caller may
    # install an explicit safety/test ceiling, but the ordinary contract must
    # not turn an arbitrary round number into a semantic stopping condition.
    max_rules: int | None = None
    rule_text_limit: int = 4_000
    rationale_limit: int = 4_000
    overview_limit: int = 4_000
    response_char_limit: int = 100_000

    def __post_init__(self) -> None:
        values = {
            "rule_text_limit": self.rule_text_limit,
            "rationale_limit": self.rationale_limit,
            "overview_limit": self.overview_limit,
            "response_char_limit": self.response_char_limit,
        }
        if any(type(value) is not int or value <= 0 for value in values.values()):
            raise ValueError("Distill semantic limits must be positive integers.")
        if self.max_rules is not None and (
            type(self.max_rules) is not int or self.max_rules <= 0
        ):
            raise ValueError(
                "Distill max_rules must be a positive integer or None."
            )


DEFAULT_DISTILL_SEMANTIC_CONFIG = DistillSemanticConfig()


__all__ = [
    "DEFAULT_DISTILL_SEMANTIC_CONFIG",
    "DistillSemanticConfig",
]
