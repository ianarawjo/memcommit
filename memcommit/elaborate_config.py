"""Typed semantic limits for Elaborate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ElaborateSemanticConfig:
    """One immutable provider-contract limit snapshot."""

    default_proposal_count: int = 3
    max_rule_proposals: int = 4
    max_case_proposals: int = 3
    text_limit: int = 2_000
    rationale_limit: int = 2_000
    overview_limit: int = 2_000
    response_char_limit: int = 50_000

    def __post_init__(self) -> None:
        values = (
            self.default_proposal_count,
            self.max_rule_proposals,
            self.max_case_proposals,
            self.text_limit,
            self.rationale_limit,
            self.overview_limit,
            self.response_char_limit,
        )
        if any(type(value) is not int or value <= 0 for value in values):
            raise ValueError("Elaborate semantic limits must be positive integers.")
        if self.default_proposal_count > min(
            self.max_rule_proposals,
            self.max_case_proposals,
        ):
            raise ValueError(
                "Elaborate default proposals must fit both directional maxima."
            )


DEFAULT_ELABORATE_SEMANTIC_CONFIG = ElaborateSemanticConfig()


__all__ = [
    "DEFAULT_ELABORATE_SEMANTIC_CONFIG",
    "ElaborateSemanticConfig",
]
