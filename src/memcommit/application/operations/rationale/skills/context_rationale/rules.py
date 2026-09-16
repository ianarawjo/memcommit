"""Versioned Context Rationale rules loaded as operation-owned skill data."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from importlib import resources

from memcommit.application.operations.rationale.model import RationaleRulesError
from memcommit.application.operations.rationale.skills.memory_documents import (
    read_memory_document,
)

CONTEXT_RATIONALE_RULESET_VERSION = "context-rationale-v1"


@lru_cache(maxsize=1)
def _loaded_ruleset() -> dict[str, object]:
    try:
        raw = read_memory_document(
            resources.files(__package__).joinpath("rule_context"),
            memory_uids=set(),
        )
    except (OSError, ValueError) as error:
        raise RationaleRulesError(
            "Could not load the Context Rationale ruleset."
        ) from error
    if (
        not isinstance(raw, dict)
        or set(raw) != {"version", "invariants"}
        or raw["version"] != CONTEXT_RATIONALE_RULESET_VERSION
        or not isinstance(raw["invariants"], list)
        or not raw["invariants"]
        or any(
            not isinstance(rule, str) or not rule.strip() for rule in raw["invariants"]
        )
    ):
        raise RationaleRulesError("Invalid Context Rationale ruleset.")
    return raw


def context_rationale_ruleset() -> dict[str, object]:
    """Return isolated rules in their original provider-visible order."""
    return deepcopy(_loaded_ruleset())
