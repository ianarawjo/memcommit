"""Freeze whether authored calibration examples enter semantic prompts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.profile_config import (
    ProfileRegistry,
    load_profile_registry,
    study_run_identity,
)


GENERAL_PROMPT_POLICY_ID = "general-authored-examples-v1"
STUDY_PROMPT_POLICY_ID = "study-rules-only-v1"

PromptPolicyScope = Literal["GENERAL", "STUDY"]


@dataclass(frozen=True)
class SemanticPromptPolicy:
    """One active-Profile projection of the authored-example boundary."""

    policy_id: str
    scope: PromptPolicyScope
    include_authored_examples: bool

    def to_prompt_record(self) -> dict[str, object]:
        """Return provider-visible policy identity without Profile metadata."""

        return {
            "policy_id": self.policy_id,
            "authored_examples": (
                "INCLUDED" if self.include_authored_examples else "OMITTED"
            ),
        }


GENERAL_SEMANTIC_PROMPT_POLICY = SemanticPromptPolicy(
    policy_id=GENERAL_PROMPT_POLICY_ID,
    scope="GENERAL",
    include_authored_examples=True,
)
STUDY_SEMANTIC_PROMPT_POLICY = SemanticPromptPolicy(
    policy_id=STUDY_PROMPT_POLICY_ID,
    scope="STUDY",
    include_authored_examples=False,
)


def resolve_semantic_prompt_policy(
    *,
    registry: ProfileRegistry | None = None,
) -> SemanticPromptPolicy:
    """Resolve one policy from the same stable Study provenance as routing.

    The Profile name is deliberately irrelevant: imported or renamed ordinary
    Profiles keep general production prompts, while both members of an
    ``init-study`` pair use the rules-only projection.
    """

    frozen_registry = registry or load_profile_registry()
    if study_run_identity(frozen_registry.active) is not None:
        return STUDY_SEMANTIC_PROMPT_POLICY
    return GENERAL_SEMANTIC_PROMPT_POLICY


__all__ = [
    "GENERAL_PROMPT_POLICY_ID",
    "GENERAL_SEMANTIC_PROMPT_POLICY",
    "STUDY_PROMPT_POLICY_ID",
    "STUDY_SEMANTIC_PROMPT_POLICY",
    "SemanticPromptPolicy",
    "resolve_semantic_prompt_policy",
]
