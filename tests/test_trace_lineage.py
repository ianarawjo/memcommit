"""Golden and topology contracts for Trace's shared lineage normal form."""

from __future__ import annotations

from dataclasses import replace
import hashlib

from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
    build_history,
)
from memcommit.application.capabilities.history.query.context_history_slicing import (
    slice_context_history_from_graph,
    slice_context_history_from_timeline,
)
from memcommit.application.capabilities.history.reconstruction.history_graph_reconstruction import (
    reconstruct_history_graph,
    reconstruct_history_graph_from_evidence,
)
from memcommit.application.capabilities.history.reconstruction.memory_history_reconstruction import (
    derive_memory_history_events,
)
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    collect_memory_history_candidates,
    reconstruct_memory_history,
)
from memcommit.application.operations.trace.reference_lineage import (
    build_reference_trace,
)
from memcommit.application.capabilities import ops
from memcommit.core.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.persistence.store import MemoryStore


def _saved_memory_history(store: MemoryStore) -> tuple[Context, Memory]:
    context = Context(
        uid="10000000-0000-4000-8000-000000000001",
        name="trace-lineage",
    )
    memory = Memory(
        uid="20000000-0000-4000-8000-000000000002",
        content="first wording",
    )
    context.add(memory)
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"content": memory.content},
            description="Added first wording",
        ),
    )
    ops.edit(context, memory.uid, "second wording")
    store.save(
        context,
        AutoCheckpoint(
            command="edit",
            args={"uid": memory.uid, "content": "second wording"},
            description="Edited to second wording",
        ),
    )
    return context, memory


def test_context_projection_keeps_the_pre_normal_form_json_contract(isolated_store):
    store = MemoryStore()
    context, _memory = _saved_memory_history(store)
    timeline = build_history(store, context.name)

    before = slice_context_history_from_timeline(timeline).to_dict()
    after = slice_context_history_from_graph(
        reconstruct_history_graph(store, context).graph
    ).to_dict()

    assert after == before


def test_memory_projection_keeps_uid_selection_and_json_shape(isolated_store):
    store = MemoryStore()
    context, memory = _saved_memory_history(store)

    report = reconstruct_memory_history(store, context, memory.uid[:8])
    candidates = collect_memory_history_candidates(store, context)
    payload = report.to_dict()
    for event in payload["events"]:
        event["timestamp"] = "<timestamp>"
        event["checkpoint_uid"] = "<checkpoint_uid>"
    first = {
        "uid": memory.uid,
        "content": "first wording",
        "position": 0,
        "content_digest": (
            "4e6b94d2affb532eb2da31da4e90481887b11ccabbe7e2a97f4633eba8583c77"
        ),
    }
    second = {
        "uid": memory.uid,
        "content": "second wording",
        "position": 0,
        "content_digest": (
            "41637d702dfb276be9d59de5d6167f5b8eb156640f1e7079a6148769c223f894"
        ),
    }
    empty_event_evidence = {
        "reason": None,
        "reason_codes": [],
        "operation_id": None,
        "command_operation": None,
        "context_transition": None,
        "child_evidence": [],
        "declared_frame": None,
        "declared_frame_digest": None,
        "uncertainty_reason": None,
        "source_review_uid": None,
        "source_review_digest": None,
        "source_analysis_uid": None,
    }

    assert payload == {
        "context": {"uid": context.uid, "name": context.name},
        "selected_uid": memory.uid,
        "component_uids": [memory.uid],
        "originals": [first],
        "current": [second],
        "events": [
            {
                "kind": "CREATED",
                "evidence": "RECONSTRUCTED",
                "timestamp": "<timestamp>",
                "checkpoint_uid": "<checkpoint_uid>",
                "command": "add",
                "description": "Added first wording",
                "before": [],
                "after": [first],
                "source_occurrence": None,
                **empty_event_evidence,
            },
            {
                "kind": "EDITED",
                "evidence": "RECORDED",
                "timestamp": "<timestamp>",
                "checkpoint_uid": "<checkpoint_uid>",
                "command": "edit",
                "description": "Edited to second wording",
                "before": [first],
                "after": [second],
                "source_occurrence": None,
                **empty_event_evidence,
            },
        ],
        "analyses": [],
        "warnings": [],
    }
    assert [event.kind for event in report.events] == ["CREATED", "EDITED"]
    assert report.originals[0].content == "first wording"
    assert report.current[0].content == "second wording"
    assert [(candidate.uid, candidate.change_count) for candidate in candidates] == [
        (memory.uid, 2)
    ]


def test_operation_identity_and_memory_component_do_not_parse_description_text(
    isolated_store,
):
    store = MemoryStore()
    context = Context(
        uid="30000000-0000-4000-8000-000000000003",
        name="typed-lineage",
    )
    source = Memory(
        uid="40000000-0000-4000-8000-000000000004",
        content="source",
    )
    context.add(source)
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"content": source.content},
            description="arbitrary creation prose",
        ),
    )
    context.remove(source.uid)
    child = Memory(
        uid="50000000-0000-4000-8000-000000000005",
        content="child",
    )
    context.add(child)
    store.save(
        context,
        AutoCheckpoint(
            command="atomize",
            args={
                "trace": {
                    "schema_version": 1,
                    "operation_id": "typed-operation-uid",
                    "changes": [
                        {
                            "kind": "SPLIT",
                            "source_uids": [source.uid],
                            "result_uids": [child.uid],
                            "reason": "typed receipt reason",
                            "reason_codes": ["TYPED"],
                        }
                    ],
                }
            },
            description="this text never says split",
        ),
    )
    timeline = build_history(store, context.name)
    events, warnings, frames = derive_memory_history_events(store, context)
    assembly = reconstruct_history_graph_from_evidence(
        timeline=timeline,
        memory_events=events,
        memory_frames=frames,
        memory_warnings=warnings,
    )
    rewritten_events = tuple(
        replace(event, description="completely unrelated display payload")
        for event in events
    )
    rewritten_timeline = replace(
        timeline,
        checkpoints=tuple(
            replace(checkpoint, description="unrelated checkpoint payload")
            for checkpoint in timeline.checkpoints
        ),
        transitions=tuple(
            replace(transition, description="unrelated transition payload")
            for transition in timeline.transitions
        ),
    )
    rewritten = reconstruct_history_graph_from_evidence(
        timeline=rewritten_timeline,
        memory_events=rewritten_events,
        memory_frames=frames,
        memory_warnings=warnings,
    )
    grouped = reconstruct_history_graph_from_evidence(
        timeline=timeline,
        memory_events=(
            replace(events[0], operation_id="typed-operation-uid"),
            *events[1:],
        ),
        memory_frames=frames,
        memory_warnings=warnings,
    )

    operation = next(
        node
        for node in assembly.graph.operations
        if node.operation_uid == "typed-operation-uid"
    )
    assert operation.checkpoint_uids
    grouped_operation = next(
        node
        for node in grouped.graph.operations
        if node.operation_uid == "typed-operation-uid"
    )
    assert grouped_operation.checkpoint_uids == tuple(
        dict.fromkeys(
            event.checkpoint_uid
            for event in grouped.memory_events
            if event.operation_id == "typed-operation-uid"
            and event.checkpoint_uid is not None
        )
    )
    assert len(grouped_operation.checkpoint_uids) == 2
    assert assembly.graph.memory_component(child.uid) == {source.uid, child.uid}
    assert rewritten.graph.memory_component(child.uid) == {source.uid, child.uid}
    assert [node.node_id for node in rewritten.graph.operations] == [
        node.node_id for node in assembly.graph.operations
    ]
    assert [
        (relation.kind, relation.source_node_id, relation.target_node_id)
        for relation in rewritten.graph.relations
    ] == [
        (relation.kind, relation.source_node_id, relation.target_node_id)
        for relation in assembly.graph.relations
    ]


def test_embed_and_reference_are_typed_relations_not_uid_lineage(isolated_store):
    store = MemoryStore()
    source = Context(
        uid="60000000-0000-4000-8000-000000000006",
        name="embed-source",
    )
    source_memory = Memory(
        uid="70000000-0000-4000-8000-000000000007",
        content="source content",
    )
    source.add(source_memory)
    store.save(source)
    owner = Context(
        uid="80000000-0000-4000-8000-000000000008",
        name="embed-owner",
    )
    reference = MemoryRef(
        uid="90000000-0000-4000-8000-000000000009",
        target_context_uid=source.uid,
        target_context_name=source.name,
        target_memory_uid=source_memory.uid,
        target=source_memory,
    )
    owner.add(reference)
    snapshot_reference = MemoryRef(
        uid="a0000000-0000-4000-8000-00000000000a",
        target_context_uid=source.uid,
        target_context_name=source.name,
        target_memory_uid=source_memory.uid,
        target=source_memory,
        snapshot_content_sha256=hashlib.sha256(
            source_memory.content.encode("utf-8")
        ).hexdigest(),
    )
    owner.add(snapshot_reference)
    store.save(
        owner,
        AutoCheckpoint(
            command="embed",
            args={"source": source.name},
            description="Attached a live Memory relation",
        ),
    )

    assembly = reconstruct_history_graph(store, owner)
    lineage = assembly.graph
    report = build_reference_trace(store, owner, reference.uid)
    snapshot_report = build_reference_trace(
        store,
        owner,
        snapshot_reference.uid,
    )

    embed = next(relation for relation in lineage.relations if relation.kind == "EMBEDS")
    assert lineage.occurrence(embed.source_node_id).kind == "MEMORY_REFERENCE"
    target = lineage.occurrence(embed.target_node_id)
    assert target.kind == "MEMORY"
    assert target.subject_uid == source_memory.uid
    assert target.selectable is False
    snapshot_edge = next(
        relation for relation in lineage.relations if relation.kind == "REFERENCES"
    )
    assert lineage.occurrence(snapshot_edge.source_node_id).subject_uid == (
        snapshot_reference.uid
    )
    assert source_memory.uid not in lineage.known_memory_uids()
    assert lineage.memory_component(reference.uid) == {reference.uid}
    assert report.selected_uid == reference.uid
    assert report.current is True
    assert report.events
    assert snapshot_report.target_history_status == "SNAPSHOT_FIXED"
    assert any(effect.channel == "REFERENCE" for effect in lineage.effects)
    assert slice_context_history_from_graph(lineage).to_dict() == (
        slice_context_history_from_timeline(assembly.timeline).to_dict()
    )
