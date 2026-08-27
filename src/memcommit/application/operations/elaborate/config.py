"""Typed semantic limits for Elaborate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ElaborateSemanticConfig:
    """One immutable provider-contract limit snapshot."""

    default_proposal_count: int = 3
    # Proposal count is caller-selected and exact. Ordinary operation leaves
    # it unbounded; an embedding host may still install an explicit one-turn
    # safety ceiling without changing the default CLI/API contract.
    max_rule_proposals: int | None = None
    max_case_proposals: int | None = None
    text_limit: int = 2_000
    rationale_limit: int = 2_000
    overview_limit: int = 2_000
    response_char_limit: int = 50_000

    def __post_init__(self) -> None:
        values = (
            self.default_proposal_count,
            self.text_limit,
            self.rationale_limit,
            self.overview_limit,
            self.response_char_limit,
        )
        if any(type(value) is not int or value <= 0 for value in values):
            raise ValueError("Elaborate semantic limits must be positive integers.")
        maxima = (self.max_rule_proposals, self.max_case_proposals)
        if any(
            maximum is not None
            and (type(maximum) is not int or maximum <= 0)
            for maximum in maxima
        ):
            raise ValueError(
                "Elaborate proposal maxima must be positive integers or None."
            )
        if any(
            maximum is not None
            and self.default_proposal_count > maximum
            for maximum in maxima
        ):
            raise ValueError(
                "Elaborate default proposals must fit each configured maximum."
            )


DEFAULT_ELABORATE_SEMANTIC_CONFIG = ElaborateSemanticConfig()


__all__ = [
    "DEFAULT_ELABORATE_SEMANTIC_CONFIG",
    "ElaborateSemanticConfig",
]
