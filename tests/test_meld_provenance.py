"""Focused provenance contracts for applied directional Context melds."""
from __future__ import annotations

from collections.abc import Callable

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.application.operations.meld.runtime import meld_checkpoint_record
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.application.operations.meld.model import (
    MeldChangeSet,
    MeldMember,
    MeldProposal,
    MeldSession,
)
from memcommit.application.capabilities.retained_history.memory_history_reconstruction.memory_history_construction import (
    reconstruct_memory_history,
)
from memcommit.persistence.store import MemoryStore


def _proposal(
    *,
    uid: str,
    operation: str,
    memory_uid: str,
    content: str,
    disposition: str,
    members: tuple[MeldMember, ...],
    reason: str,
    owner: Context,
) -> MeldProposal:
    return MeldProposal.from_dict(
        {
            "uid": uid,
            "operation": operation,
            "disposition": disposition,
            "memory_uid": memory_uid,
            "content": content,
            "reason": reason,
            "relation_uids": [],
            "source_members": [
                member.to_dict() for member in members
            ],
            "grounded_by_turn_uids": [],
            "owner_context": {"uid": owner.uid, "name": owner.name},
        }
    )


def _applied_directional_meld(
    store: MemoryStore,
    *,
    mutate_record: Callable[[dict[str, object]], None] | None = None,
    mutate_post_image: Callable[[Context], None] | None = None,
) -> tuple[Context, Memory, Memory]:
    incoming = ops.init("meld-provenance/incoming")
    incoming_edit = ops.add(
        incoming,
        "The entrance requires a physical NFC card.",
    )
    incoming_add = ops.add(
        incoming,
        "The staff entrance uses the same credential.",
    )
    store.save(incoming)

    baseline = ops.init("meld-provenance/baseline")
    edited = ops.add(
        baseline,
        "The entrance accepts a physical card or the mobile app.",
    )
    untouched = ops.add(baseline, "The rear entrance remains closed.")
    store.save(
        baseline,
        AutoCheckpoint(
            command="add",
            args={},
            description="Stored the baseline Memories.",
        ),
    )

    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()
    incoming_frame, baseline_frame = session.frames
    added = Memory(
        uid="70000000-0000-4000-8000-000000000007",
        content="The staff entrance requires a physical NFC card.",
    )
    proposals = (
        _proposal(
            uid="50000000-0000-4000-8000-000000000005",
            operation="EDIT",
            memory_uid=edited.uid,
            content="The entrance requires a physical NFC card.",
            disposition="SYNTHESIZE",
            members=(
                MeldMember(
                    frame_uid=incoming_frame.uid,
                    memory_uid=incoming_edit.uid,
                ),
                MeldMember(
                    frame_uid=baseline_frame.uid,
                    memory_uid=edited.uid,
                ),
            ),
            reason=(
                "The incoming access rule narrows the authoritative baseline."
            ),
            owner=baseline,
        ),
        _proposal(
            uid="60000000-0000-4000-8000-000000000006",
            operation="ADD",
            memory_uid=added.uid,
            content=added.content,
            disposition="PRESERVE",
            members=(
                MeldMember(
                    frame_uid=incoming_frame.uid,
                    memory_uid=incoming_add.uid,
                ),
            ),
            reason="The incoming staff rule is new to the baseline.",
            owner=baseline,
        ),
    )
    change_set = MeldChangeSet.create(
        session_uid=session.uid,
        turn_uid=session.current_turn.uid,
        mode=session.mode,
        target=session.target,
        frames=session.frames,
        turns=session.turns,
        proposals=proposals,
    )
    record = meld_checkpoint_record(
        session,
        change_set,
        owner=(baseline.uid, baseline.name),
    )
    if mutate_record is not None:
        mutate_record(record)

    baseline.replace(
        Memory(
            uid=edited.uid,
            content="The entrance requires a physical NFC card.",
        )
    )
    baseline.add(added)
    if mutate_post_image is not None:
        mutate_post_image(baseline)
    store.save(
        baseline,
        AutoCheckpoint(
            command="meld",
            args={"meld": record},
            description="Applied the directional Context meld.",
        ),
    )
    current = store.load_direct(baseline.name)
    assert untouched.uid in current.memories
    return current, edited, added


def test_directional_meld_trace_records_edit_and_add_evidence(
    isolated_store,
):
    store = MemoryStore()
    current, edited, added = _applied_directional_meld(store)

    edited_trace = reconstruct_memory_history(store, current, edited.uid)
    edit_event = next(
        event
        for event in edited_trace.events
        if event.command == "meld"
    )
    assert edit_event.kind == "EDITED"
    assert edit_event.evidence == "RECORDED"
    assert edit_event.before[0].content.endswith("or the mobile app.")
    assert edit_event.after[0].content.endswith("physical NFC card.")
    assert edit_event.reason_codes == ("MELD", "EDIT", "SYNTHESIZE")
    assert "INCOMING meld-provenance/incoming#" in (
        edit_event.declared_frame or ""
    )
    assert "BASELINE meld-provenance/baseline#" in (
        edit_event.declared_frame or ""
    )

    added_trace = reconstruct_memory_history(store, current, added.uid)
    add_event = next(
        event
        for event in added_trace.events
        if event.command == "meld"
    )
    assert add_event.kind == "MELDED"
    assert add_event.evidence == "RECORDED"
    assert add_event.reason_codes == ("MELD", "ADD", "PRESERVE")
    assert "INCOMING meld-provenance/incoming#" in (
        add_event.declared_frame or ""
    )


@pytest.mark.parametrize("tamper", ["operation", "role", "post_image"])
def test_directional_meld_trace_rejects_untrusted_v2_evidence(
    isolated_store,
    tamper,
):
    def mutate_record(record: dict[str, object]) -> None:
        if tamper == "operation":
            results = record["results"]
            assert isinstance(results, list)
            results[0]["operation"] = "ADD"
        elif tamper == "role":
            sources = record["sources"]
            assert isinstance(sources, list)
            sources[0]["role"] = "BASELINE"

    def mutate_post_image(ctx: Context) -> None:
        if tamper != "post_image":
            return
        untouched = tuple(ctx.iter_items())[1]
        assert isinstance(untouched, Memory)
        ctx.replace(
            Memory(
                uid=untouched.uid,
                content="An unrecorded change altered the post-image.",
            )
        )

    store = MemoryStore()
    current, edited, _added = _applied_directional_meld(
        store,
        mutate_record=mutate_record,
        mutate_post_image=mutate_post_image,
    )

    trace = reconstruct_memory_history(store, current, edited.uid)
    event = next(
        item for item in trace.events if item.command == "meld"
    )
    assert event.kind == "EDITED"
    assert event.evidence == "RECONSTRUCTED"
    assert event.reason is None
    assert event.declared_frame is None
    assert any(
        "results were reconstructed from snapshots" in warning
        for warning in trace.warnings
    )


def test_directional_zero_change_receipt_accepts_an_unchanged_post_image(
    isolated_store,
):
    store = MemoryStore()
    incoming = ops.init("meld-provenance/duplicate-incoming")
    ops.add(incoming, "The rear entrance remains closed.")
    store.save(incoming)
    baseline = ops.init("meld-provenance/unchanged-baseline")
    retained = ops.add(baseline, "The rear entrance remains closed.")
    store.save(
        baseline,
        AutoCheckpoint(
            command="add",
            args={},
            description="Stored the unchanged baseline.",
        ),
    )
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()
    change_set = MeldChangeSet.create(
        session_uid=session.uid,
        turn_uid=session.current_turn.uid,
        mode=session.mode,
        target=session.target,
        frames=session.frames,
        turns=session.turns,
        proposals=(),
    )
    record = meld_checkpoint_record(
        session,
        change_set,
        owner=(baseline.uid, baseline.name),
    )

    store.save(
        baseline,
        AutoCheckpoint(
            command="meld",
            args={"meld": record},
            description="Accepted a no-change directional meld.",
        ),
    )
    current = store.load_direct(baseline.name)
    trace = reconstruct_memory_history(store, current, retained.uid)

    assert not any(event.command == "meld" for event in trace.events)
    assert not any(
        "meld" in warning.casefold() for warning in trace.warnings
    )
