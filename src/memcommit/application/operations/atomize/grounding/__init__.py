"""Non-mutating conversational state for Atomize Grounding.

The package preserves the historical ``atomize.grounding`` API while assigning
frozen bindings, semantic review, exact changes, and session lifecycle to
explicit Grounding-owned modules.
"""

from .bindings import (
    ATOMIZE_GROUNDING_ID_LIMIT,
    ATOMIZE_GROUNDING_LEGACY_SCHEMA_VERSION,
    ATOMIZE_GROUNDING_NAME_LIMIT,
    ATOMIZE_GROUNDING_SCHEMA_VERSION,
    ATOMIZE_GROUNDING_TEXT_LIMIT,
    AtomizeGroundingAnchor,
    AtomizeGroundingArity,
    AtomizeGroundingBindings,
    AtomizeGroundingDecisionAction,
    AtomizeGroundingEffectKind,
    AtomizeGroundingError,
    AtomizeGroundingIssueKind,
    AtomizeGroundingProposalNecessity,
    AtomizeGroundingProposalOperation,
    AtomizeGroundingQuestionKind,
    AtomizeGroundingQuestionPriority,
    AtomizeGroundingResolution,
    AtomizeGroundingRevision,
    AtomizeGroundingState,
    atomize_grounding_canonical_digest,
    atomize_grounding_context_digest,
)
from .changes import AtomizeGroundingApplication, AtomizeGroundingChangeSet
from .review import (
    AtomizeGroundingAssessment,
    AtomizeGroundingDecision,
    AtomizeGroundingDirectOutcome,
    AtomizeGroundingDownstreamEffect,
    AtomizeGroundingFollowUp,
    AtomizeGroundingProposal,
    AtomizeGroundingTurn,
)
from .session import AtomizeGroundingSession, prepare_atomize_grounding_changes

__all__ = (
    "ATOMIZE_GROUNDING_ID_LIMIT",
    "ATOMIZE_GROUNDING_LEGACY_SCHEMA_VERSION",
    "ATOMIZE_GROUNDING_NAME_LIMIT",
    "ATOMIZE_GROUNDING_SCHEMA_VERSION",
    "ATOMIZE_GROUNDING_TEXT_LIMIT",
    "AtomizeGroundingAnchor",
    "AtomizeGroundingApplication",
    "AtomizeGroundingArity",
    "AtomizeGroundingAssessment",
    "AtomizeGroundingBindings",
    "AtomizeGroundingChangeSet",
    "AtomizeGroundingDecision",
    "AtomizeGroundingDecisionAction",
    "AtomizeGroundingDirectOutcome",
    "AtomizeGroundingDownstreamEffect",
    "AtomizeGroundingEffectKind",
    "AtomizeGroundingError",
    "AtomizeGroundingFollowUp",
    "AtomizeGroundingIssueKind",
    "AtomizeGroundingProposal",
    "AtomizeGroundingProposalNecessity",
    "AtomizeGroundingProposalOperation",
    "AtomizeGroundingQuestionKind",
    "AtomizeGroundingQuestionPriority",
    "AtomizeGroundingResolution",
    "AtomizeGroundingRevision",
    "AtomizeGroundingSession",
    "AtomizeGroundingState",
    "AtomizeGroundingTurn",
    "atomize_grounding_canonical_digest",
    "atomize_grounding_context_digest",
    "prepare_atomize_grounding_changes",
)
