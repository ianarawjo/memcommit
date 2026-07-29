"""Lossless meld projection over the existing atomize-grounding schema.

Atomize owns decomposition and its durable artifact.  Once a reviewer supplies
or selects an interpretation, the grounding dialogue is an issue-scoped
directional meld: CLARIFICATION evidence is incorporated into a bounded
BASELINE frame, downstream effects are recomputed, and exact EDIT/ADD
proposals require explicit acceptance.

This adapter deliberately adds no serialized field and infers no source
relation from an EDIT or ADD.  Dialogue revision and Memory relation are
different concepts.
"""
from __future__ import annotations

from dataclasses import dataclass

from memcommit.atomize_grounding import AtomizeGroundingSession
from memcommit.meld import MeldRevision


@dataclass(frozen=True)
class AtomizeMeldTurnView:
    uid: str
    sequence: int
    revision: MeldRevision
    comment: str
    revises_turn_uids: tuple[str, ...]
    assessed: bool


@dataclass(frozen=True)
class AtomizeMeldView:
    """Shared-controller metadata for one existing atomize dialogue."""

    session_uid: str
    authority_mode: str
    scope: str
    input_roles: tuple[str, str]
    anchor_issue_uid: str
    anchor_source_uids: tuple[str, ...]
    affected_issue_uids: tuple[str, ...]
    turns: tuple[AtomizeMeldTurnView, ...]
    proposal_operations: tuple[str, ...]
    state: str


def project_atomize_grounding_as_meld(
    session: AtomizeGroundingSession,
) -> AtomizeMeldView:
    """Project, without mutating or widening, one atomize meld adapter."""
    if not isinstance(session, AtomizeGroundingSession):
        raise TypeError("Expected an AtomizeGroundingSession.")
    assessment = session.current_assessment
    return AtomizeMeldView(
        session_uid=session.uid,
        authority_mode="DIRECTIONAL",
        scope="ISSUE",
        input_roles=("CLARIFICATION", "BASELINE"),
        anchor_issue_uid=session.anchor.issue_uid,
        anchor_source_uids=session.anchor.source_uids,
        affected_issue_uids=(
            tuple(effect.issue_uid for effect in assessment.downstream)
            if assessment is not None
            else ()
        ),
        turns=tuple(
            AtomizeMeldTurnView(
                uid=turn.uid,
                sequence=turn.sequence,
                revision=turn.revision,
                comment=turn.comment,
                revises_turn_uids=turn.revises_turn_uids,
                assessed=turn.assessment is not None,
            )
            for turn in session.turns
        ),
        proposal_operations=(
            tuple(proposal.operation for proposal in assessment.proposals)
            if assessment is not None
            else ()
        ),
        state=session.state,
    )
