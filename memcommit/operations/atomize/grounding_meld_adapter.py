"""Operation-owned Meld projection over the Atomize-grounding schema.

Atomize owns decomposition and its durable artifact.  Its selected source
candidate is projected as an ephemeral ``INCOMING`` Context frame, while the
containing Context is projected as the bounded ``BASELINE`` frame.  Reviewer
clarification remains dialogue evidence attached to that directional meld; it
is not promoted into a third Context.

The ephemeral frame is an immutable view, not a mutable ``Context`` instance.
That distinction is intentional: constructing a normal Context would give a
turn-local projection a saveable UID and locator even though it must never be
stored, selected, listed, or checkpointed.  Unary issues therefore behave like
a temporary one-Memory Context without materializing a persistent Context
record.  Pair-shaped issues retain both source Memories in the same frame.

This adapter deliberately adds no serialized field and infers no source
relation from an EDIT or ADD.  Dialogue revision and Memory relation are
different concepts.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Literal

from memcommit.operations.atomize.grounding import (
    AtomizeGroundingSession,
    atomize_grounding_context_digest,
)
from memcommit.context import Context, Memory
from memcommit.meld import MeldError, MeldRevision, meld_canonical_digest


AtomizeMeldFrameRole = Literal["INCOMING", "BASELINE"]
AtomizeMeldFramePersistence = Literal["EPHEMERAL", "BOUND"]
AtomizeMeldFrameKind = Literal[
    "ISSUE_CONTEXT",
    "CONTAINING_CONTEXT",
]


@dataclass(frozen=True)
class AtomizeMeldMemoryView:
    """One source-grounded Memory as ordered inside a projected frame."""

    uid: str
    content: str
    frame_position: int
    source_position: int
    content_digest: str


@dataclass(frozen=True)
class AtomizeMeldFrameView:
    """A non-serializing Context-shaped input to atomize grounding."""

    uid: str
    role: AtomizeMeldFrameRole
    kind: AtomizeMeldFrameKind
    persistence: AtomizeMeldFramePersistence
    source_context_uid: str | None
    source_context_name: str | None
    source_context_digest: str | None
    projection_digest: str
    memories: tuple[AtomizeMeldMemoryView, ...]

    def __post_init__(self) -> None:
        if not self.memories:
            raise MeldError("An atomize meld frame cannot be empty.")
        if [memory.frame_position for memory in self.memories] != list(
            range(len(self.memories))
        ):
            raise MeldError("Invalid atomize meld frame Memory order.")
        if self.persistence == "EPHEMERAL":
            if self.role != "INCOMING":
                raise MeldError(
                    "Only the incoming atomize meld frame is ephemeral."
                )
            if any(
                value is not None
                for value in (
                    self.source_context_uid,
                    self.source_context_name,
                    self.source_context_digest,
                )
            ):
                raise MeldError(
                    "An ephemeral atomize meld frame has no durable Context "
                    "identity or locator."
                )
        elif (
            self.role != "BASELINE"
            or self.source_context_uid is None
            or self.source_context_name is None
            or self.source_context_digest is None
        ):
            raise MeldError(
                "A bound atomize meld baseline requires its durable Context "
                "identity and locator."
            )


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
    frames: tuple[AtomizeMeldFrameView, AtomizeMeldFrameView]
    anchor_issue_uid: str
    anchor_source_uids: tuple[str, ...]
    affected_issue_uids: tuple[str, ...]
    turns: tuple[AtomizeMeldTurnView, ...]
    proposal_operations: tuple[str, ...]
    state: str


def project_atomize_grounding_as_meld(
    session: AtomizeGroundingSession,
    ctx: Context,
) -> AtomizeMeldView:
    """Project one atomize dialogue as two Context-shaped meld frames.

    This pure projection never calls ``MemoryStore``.  Its synthetic frame UID
    is deterministic only so a resumed dialogue reconstructs the same bounded
    input; it is not a durable Context identity or locator.
    """
    if not isinstance(session, AtomizeGroundingSession):
        raise TypeError("Expected an AtomizeGroundingSession.")
    if not isinstance(ctx, Context):
        raise TypeError("Expected a Context.")
    bindings = session.bindings
    if (
        bindings.context_uid != ctx.uid
        or bindings.context_name != ctx.name
        or bindings.context_digest != atomize_grounding_context_digest(ctx)
    ):
        raise MeldError(
            "The atomize meld projection does not match its bound Context."
        )

    direct_memories = [
        (source_position, item)
        for source_position, item in enumerate(ctx.iter_items())
        if isinstance(item, Memory)
    ]
    memory_by_uid = {
        memory.uid: (source_position, memory)
        for source_position, memory in direct_memories
    }
    if any(
        source_uid not in memory_by_uid
        for source_uid in session.anchor.source_uids
    ):
        raise MeldError(
            "The atomize meld issue references a non-direct Memory."
        )

    def memory_view(
        memory: Memory,
        *,
        frame_position: int,
        source_position: int,
    ) -> AtomizeMeldMemoryView:
        return AtomizeMeldMemoryView(
            uid=memory.uid,
            content=memory.content,
            frame_position=frame_position,
            source_position=source_position,
            content_digest=hashlib.sha256(
                memory.content.encode("utf-8")
            ).hexdigest(),
        )

    incoming_memories = tuple(
        memory_view(
            memory_by_uid[source_uid][1],
            frame_position=frame_position,
            source_position=memory_by_uid[source_uid][0],
        )
        for frame_position, source_uid in enumerate(
            session.anchor.source_uids
        )
    )
    baseline_memories = tuple(
        memory_view(
            memory,
            frame_position=frame_position,
            source_position=source_position,
        )
        for frame_position, (source_position, memory) in enumerate(
            direct_memories
        )
    )
    incoming_digest = meld_canonical_digest(
        {
            "kind": "ISSUE_CONTEXT",
            "issue_uid": session.anchor.issue_uid,
            "issue_digest": session.anchor.issue_digest,
            "memories": [
                {
                    "uid": memory.uid,
                    "content": memory.content,
                    "frame_position": memory.frame_position,
                    "source_position": memory.source_position,
                    "content_digest": memory.content_digest,
                }
                for memory in incoming_memories
            ],
        }
    )
    baseline_digest = meld_canonical_digest(
        {
            "kind": "CONTAINING_CONTEXT",
            "source_context_digest": bindings.context_digest,
            "memories": [
                {
                    "uid": memory.uid,
                    "content": memory.content,
                    "frame_position": memory.frame_position,
                    "source_position": memory.source_position,
                    "content_digest": memory.content_digest,
                }
                for memory in baseline_memories
            ],
        }
    )
    session_namespace = uuid.UUID(session.uid)
    incoming = AtomizeMeldFrameView(
        uid=str(
            uuid.uuid5(
                session_namespace,
                f"atomize-incoming:{incoming_digest}",
            )
        ),
        role="INCOMING",
        kind="ISSUE_CONTEXT",
        persistence="EPHEMERAL",
        source_context_uid=None,
        source_context_name=None,
        source_context_digest=None,
        projection_digest=incoming_digest,
        memories=incoming_memories,
    )
    baseline = AtomizeMeldFrameView(
        uid=str(
            uuid.uuid5(
                session_namespace,
                f"atomize-baseline:{baseline_digest}",
            )
        ),
        role="BASELINE",
        kind="CONTAINING_CONTEXT",
        persistence="BOUND",
        source_context_uid=bindings.context_uid,
        source_context_name=bindings.context_name,
        source_context_digest=bindings.context_digest,
        projection_digest=baseline_digest,
        memories=baseline_memories,
    )
    assessment = session.current_assessment
    return AtomizeMeldView(
        session_uid=session.uid,
        authority_mode="DIRECTIONAL",
        scope="ISSUE",
        input_roles=("INCOMING", "BASELINE"),
        frames=(incoming, baseline),
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
