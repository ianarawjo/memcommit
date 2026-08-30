"""Per-Memory trace and evidence-layered rationale contracts."""

from __future__ import annotations

import copy
import json
import shutil

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.add import command as add_command
from memcommit.core.context import AutoCheckpoint, Memory
from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityFinding,
    AmbiguityReport,
)
from memcommit.application.capabilities.retained_history.memory_history_reconstruction.memory_history_construction import (
    reconstruct_memory_history,
)
from memcommit.application.operations.rationale.model import build_rationale
from memcommit.application.operations.rationale.semantic import (
    rationale_provenance_payload,
)
from memcommit.application.operations.review.model import create_ambiguity_review
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.update.model import plan_update


runner = CliRunner()


def invoke(*args: str, stdin: str | None = None):
    return runner.invoke(app, list(args), input=stdin)


class UpdatePlanProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "update planning"
        assert output_schema is not None
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_id = payload["source"]["memories"][0]["source_id"]
        target = payload["target"]["memories"][0]
        return json.dumps(
            {
                "edits": [
                    {
                        "target_id": target["target_id"],
                        "new_content": "Updated from the intended source.",
                        "source_ids": [source_id],
                        "reason": "The source provides the current wording.",
                    }
                ],
                "additions": [],
                "removals": [],
            }
        )


def test_trace_shows_newest_operation_first_with_forward_row_arrows(
    isolated_store,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "draft").exit_code == 0
    store = MemoryStore()
    memory = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    assert invoke("edit", memory.uid, "revision one").exit_code == 0
    assert invoke("edit", memory.uid, "revision two").exit_code == 0

    result = invoke("trace", memory.uid[:8])

    assert result.exit_code == 0
    rows = [
        line
        for line in result.output.splitlines()
        if line.startswith("[") and "[CHECKPOINT " in line
    ]
    assert [
        next(action for action in ("[edit]", "[add]") if action in row) for row in rows
    ] == ["[edit]", "[edit]", "[add]"]
    assert "  − [" in result.output
    assert "@1 revision one\n  + [" in result.output
    assert "@1 revision two" in result.output
    assert "@1 draft\n  + [" in result.output
    assert "  − ∅" not in result.output
    assert "LATEST FIRST" in result.output
    assert "NOW\n" not in result.output
    assert "[MEMORY " in result.output
    assert "Checkpoint:" not in result.output


@pytest.mark.parametrize(
    "branch_command",
    [
        ("branch", "practice/2"),
        ("checkout", "-b", "practice/2"),
    ],
)
def test_trace_records_unchanged_memory_route_for_branch_entry_points(
    isolated_store,
    branch_command,
):
    assert invoke("init", "practice/1").exit_code == 0
    assert invoke("add", "a is apple").exit_code == 0
    store = MemoryStore()
    source = store.load_current_direct()
    memory = next(item for item in source.iter_items() if isinstance(item, Memory))

    branched = invoke(*branch_command)

    assert branched.exit_code == 0, branched.output
    target = store.load_direct("practice/2")
    target_memory = next(
        item for item in target.iter_items() if isinstance(item, Memory)
    )
    assert target_memory.uid != memory.uid
    report = reconstruct_memory_history(store, target, target_memory.uid)
    assert [event.kind for event in report.events] == ["CREATED", "BRANCHED"]
    assert report.warnings == ()
    branch_event = report.events[-1]
    assert branch_event.evidence == "RECORDED"
    assert branch_event.operation_id is not None
    assert branch_event.operation_id.startswith("branch:")
    assert branch_event.context_transition is not None
    assert branch_event.context_transition.to_dict() == {
        "source": {"uid": source.uid, "name": "practice/1"},
        "target": {"uid": target.uid, "name": "practice/2"},
    }
    assert [state.uid for state in branch_event.before] == [memory.uid]
    assert [state.uid for state in branch_event.after] == [target_memory.uid]
    assert branch_event.before[0].content == branch_event.after[0].content
    rationale_request = rationale_provenance_payload(report)["request"]
    assert rationale_request["selected_context"] == "practice/2"
    assert rationale_request["warnings"] == []
    assert rationale_request["events"][-1]["context_transition"] == {
        "source": "practice/1",
        "target": "practice/2",
    }

    rendered = invoke("trace", f"practice/2:{target_memory.uid}")
    assert rendered.exit_code == 0, rendered.output
    assert "[branch]" in rendered.output
    assert "practice/1 → practice/2 · Memory content unchanged" in rendered.output
    assert "Source Context: practice/1" in rendered.output
    assert "Target Context: practice/2" in rendered.output
    assert "branch creation event was not recorded" not in rendered.output

    structured = invoke("trace", f"practice/2:{target_memory.uid}", "--json")
    assert structured.exit_code == 0, structured.output
    assert json.loads(structured.output)["events"][-1]["context_transition"] == {
        "source": {"uid": source.uid, "name": "practice/1"},
        "target": {"uid": target.uid, "name": "practice/2"},
    }


def test_merge_lineage_connects_source_and_fresh_target_trace_both_directions(
    isolated_store,
):
    assert invoke("init", "merge-lineage/source").exit_code == 0
    assert invoke("add", "Audit draft: construction dates.").exit_code == 0
    store = MemoryStore()
    source = store.load_current_direct()
    source_memory = next(
        item for item in source.iter_items() if isinstance(item, Memory)
    )
    assert (
        invoke(
            "edit",
            source_memory.uid,
            "Wiki update draft: construction dates.",
        ).exit_code
        == 0
    )
    source = store.load_direct(source.name)
    assert invoke("init", "merge-lineage/target").exit_code == 0

    merged = invoke("merge", source.name)

    assert merged.exit_code == 0, merged.output
    target = store.load_current_direct()
    target_memory = next(
        item for item in target.iter_items() if isinstance(item, Memory)
    )
    assert target_memory.uid != source_memory.uid

    for owner, selected_uid in (
        (source, source_memory.uid),
        (target, target_memory.uid),
    ):
        report = reconstruct_memory_history(store, owner, selected_uid)
        assert [event.kind for event in report.events] == [
            "CREATED",
            "EDITED",
            "MERGED_IN",
        ]
        merge_event = report.events[-1]
        assert merge_event.evidence == "RECORDED"
        assert merge_event.reason_codes == ("MERGE", "NEW")
        assert merge_event.context_transition is not None
        assert merge_event.context_transition.to_dict() == {
            "source": {"uid": source.uid, "name": source.name},
            "target": {"uid": target.uid, "name": target.name},
        }
        assert [state.uid for state in merge_event.before] == [source_memory.uid]
        assert [state.uid for state in merge_event.after] == [target_memory.uid]
        assert {state.uid for state in report.current} == {
            source_memory.uid,
            target_memory.uid,
        }
        request = rationale_provenance_payload(report)["request"]
        assert request["events"][-1]["reason_codes"] == ["MERGE", "NEW"]
        assert request["events"][-1]["context_transition"] == {
            "source": source.name,
            "target": target.name,
        }

    rendered = invoke("trace", source_memory.uid, "--all")
    assert rendered.exit_code == 0, rendered.output
    assert "[merge] [CHECKPOINT " in rendered.output
    assert "[MEMORIES 2]" in rendered.output
    assert (
        f"{source.name} → {target.name} · Memory content unchanged" in rendered.output
    )
    assert f"Source: [{source_memory.uid[:8]}] Wiki update draft" in rendered.output
    assert f"Target: [{target_memory.uid[:8]}] Wiki update draft" in rendered.output


def test_trace_does_not_connect_a_tampered_merge_lineage_receipt(
    isolated_store,
):
    assert invoke("init", "invalid-merge/source").exit_code == 0
    assert invoke("add", "Exact copied value.").exit_code == 0
    store = MemoryStore()
    source = store.load_current_direct()
    source_memory = next(
        item for item in source.iter_items() if isinstance(item, Memory)
    )
    assert invoke("init", "invalid-merge/target").exit_code == 0
    assert invoke("merge", source.name).exit_code == 0
    target = store.load_current_direct()
    target_memory = next(
        item for item in target.iter_items() if isinstance(item, Memory)
    )
    checkpoint = store.list_checkpoints(target.name)[0]
    checkpoint_path = next(
        store._checkpoints_dir(target.name).glob(f"*-{checkpoint['uid'][:8]}.json")
    )
    record = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    record["args"]["memory_lineage"]["edges"][0]["target_content_sha256"] = "0" * 64
    checkpoint_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    source_report = reconstruct_memory_history(store, source, source_memory.uid)
    target_report = reconstruct_memory_history(store, target, target_memory.uid)

    assert not any(event.kind == "MERGED_IN" for event in source_report.events)
    assert not any(
        event.context_transition is not None for event in target_report.events
    )
    assert any(
        "Source and Target histories were not connected" in warning
        for warning in target_report.warnings
    )


def test_merge_trace_preserves_keep_target_and_take_source_dispositions(
    isolated_store,
):
    assert invoke("init", "merge-decisions/main").exit_code == 0
    assert invoke("add", "Main wording.").exit_code == 0
    store = MemoryStore()
    main = store.load_current_direct()
    main_memory = next(item for item in main.iter_items() if isinstance(item, Memory))
    assert invoke("branch", "merge-decisions/feature").exit_code == 0
    feature = store.load_current_direct()
    feature_memory = next(
        item for item in feature.iter_items() if isinstance(item, Memory)
    )
    assert invoke("edit", feature_memory.uid, "Feature wording.").exit_code == 0
    assert invoke("switch", main.name).exit_code == 0

    kept = invoke("merge", feature.name, "--keep-target-all")
    taken = invoke("merge", feature.name, "--take-source-all")

    assert kept.exit_code == 0, kept.output
    assert taken.exit_code == 0, taken.output
    report = reconstruct_memory_history(
        store, store.load_direct(main.name), main_memory.uid
    )
    dispositions = [
        event.reason_codes[-1] for event in report.events if event.kind == "MERGED_IN"
    ]
    assert dispositions == ["KEEP_TARGET", "TAKE_SOURCE"]
    kept_event, taken_event = [
        event for event in report.events if event.kind == "MERGED_IN"
    ]
    assert [state.content for state in kept_event.before] == [
        "Feature wording.",
        "Main wording.",
    ]
    assert kept_event.after[0].content == "Main wording."
    assert [state.content for state in taken_event.before] == [
        "Feature wording.",
        "Main wording.",
    ]
    assert taken_event.after[0].content == "Feature wording."

    rendered = invoke("trace", main_memory.uid, "--all")
    assert rendered.exit_code == 0, rendered.output
    assert "Target retained; Source not materialized" in rendered.output
    assert "Target content replaced from Source" in rendered.output
    assert "Target before:" in rendered.output


def test_trace_keeps_one_legacy_warning_when_no_branch_receipt_exists(
    isolated_store,
):
    assert invoke("init", "legacy/source").exit_code == 0
    assert invoke("add", "legacy inherited fact").exit_code == 0
    store = MemoryStore()
    source = store.load_current_direct()
    memory = next(item for item in source.iter_items() if isinstance(item, Memory))
    # Model a pre-lineage-receipt Branch that retained the Source UID.
    target = ops.init("legacy/target")
    target.add(Memory(uid=memory.uid, content=memory.content))
    store.save(target)
    source_checkpoints = store._checkpoints_dir(source.name)
    target_checkpoints = store._checkpoints_dir(target.name)
    target_checkpoints.mkdir(parents=True, exist_ok=True)
    for path in source_checkpoints.glob("*.json"):
        shutil.copy2(path, target_checkpoints / path.name)

    report = reconstruct_memory_history(
        store, store.load_direct(target.name), memory.uid
    )

    assert [event.kind for event in report.events] == ["CREATED"]
    assert len(report.warnings) == 1
    assert "inherited from 'legacy/source'" in report.warnings[0]
    assert "branch creation event was not recorded" in report.warnings[0]


def test_trace_retains_each_recorded_context_route_across_nested_branches(
    isolated_store,
):
    assert invoke("init", "nested/0").exit_code == 0
    assert invoke("add", "stable through both branches").exit_code == 0
    store = MemoryStore()
    source_memory = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    assert invoke("branch", "nested/1").exit_code == 0
    middle_memory = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    assert invoke("branch", "nested/2").exit_code == 0
    target_memory = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    assert len({source_memory.uid, middle_memory.uid, target_memory.uid}) == 3

    report = reconstruct_memory_history(
        store, store.load_direct("nested/2"), target_memory.uid
    )

    assert report.warnings == ()
    routes = [
        (
            event.context_transition.source.name,
            event.context_transition.target.name,
        )
        for event in report.events
        if event.kind == "BRANCHED" and event.context_transition is not None
    ]
    assert routes == [("nested/0", "nested/1"), ("nested/1", "nested/2")]


def test_trace_does_not_trust_invalid_branch_creation_metadata(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "invalid/source").exit_code == 0
    assert invoke("add", "must not receive forged provenance").exit_code == 0
    store = MemoryStore()
    memory = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    assert invoke("branch", "invalid/target").exit_code == 0
    retained = copy.deepcopy(store.list_checkpoints("invalid/target"))
    branch_entry = next(entry for entry in retained if entry["command"] == "branch")
    branch_entry["args"]["branch_tree"]["operation_uid"] = "forged"
    monkeypatch.setattr(store, "list_checkpoints", lambda _name: retained)

    report = reconstruct_memory_history(
        store, store.load_direct("invalid/target"), memory.uid
    )

    assert not any(event.kind == "BRANCHED" for event in report.events)
    assert any("invalid Branch creation metadata" in item for item in report.warnings)
    assert any(
        "branch creation event was not recorded" in item for item in report.warnings
    )


def test_trace_resolves_removed_historical_memory(isolated_store):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "temporary").exit_code == 0
    store = MemoryStore()
    memory = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    assert invoke("remove", memory.uid[:8]).exit_code == 0

    result = invoke("trace", memory.uid[:8])

    assert result.exit_code == 0
    assert "[add]" in result.output
    assert "[remove]" in result.output
    assert 'removed "temporary"' in result.output
    assert "  − " not in result.output
    assert "  + " not in result.output
    assert "NOW" not in result.output


def test_trace_reconstructs_legacy_chunk_lineage_both_directions(
    isolated_store,
):
    assert invoke("init", "chunks").exit_code == 0
    assert invoke("add", "First block.\n\nSecond block.").exit_code == 0
    store = MemoryStore()
    parent = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    chunked = invoke(
        "chunk",
        parent.uid[:8],
        "--method",
        "paragraphs",
        stdin="y\n",
    )
    assert chunked.exit_code == 0
    children = [
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    ]
    assert len(children) == 2

    from_parent = invoke("trace", parent.uid[:8], "--verbose")
    from_child = invoke("trace", children[1].uid[:8], "--verbose")

    for result in (from_parent, from_child):
        assert result.exit_code == 0
        assert "[chunk] [CHECKPOINT " in result.output
        assert "  − [" in result.output
        assert "  + [" in result.output
        assert "RECONSTRUCTED" in result.output
        assert r"First block.\n\nSecond block." in result.output
        assert parent.uid[:8] in result.output


def test_explicit_lineage_tracks_identical_fresh_child_then_current_edit(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("atomized")
    source = ops.add(ctx, "Same wording.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="add",
            args={"content": source.content},
            description="Added source",
        ),
    )

    source_position = ctx.ordered_uids().index(source.uid)
    ctx.remove(source.uid)
    child = Memory(uid="10000000-0000-4000-8000-000000000001", content=source.content)
    unrelated = Memory(
        uid="20000000-0000-4000-8000-000000000002",
        content=source.content,
    )
    ctx.add(child, position=source_position)
    ctx.add(unrelated)
    store.save(
        ctx,
        AutoCheckpoint(
            command="atomize",
            args={
                "trace": {
                    "schema_version": 1,
                    "operation_id": "atomize-operation",
                    "changes": [
                        {
                            "kind": "SPLIT",
                            "source_uids": [source.uid],
                            "result_uids": [child.uid],
                            "reason": "One recorded child occurrence.",
                            "reason_codes": ["A01_ONE_FOCUS"],
                        }
                    ],
                }
            },
            description="Applied atomize lineage",
        ),
    )
    ops.edit(ctx, child.uid, "Edited current wording.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="edit",
            args={"uid": child.uid, "content": "Edited current wording."},
            description="Edited child",
        ),
    )

    report = reconstruct_memory_history(
        store, store.load_direct("atomized"), child.uid[:8]
    )

    assert report.component_uids == tuple(sorted((source.uid, child.uid)))
    assert unrelated.uid not in report.component_uids
    assert report.originals[0].uid == source.uid
    assert report.current[0].uid == child.uid
    assert report.current[0].content == "Edited current wording."
    assert [event.kind for event in report.events] == [
        "CREATED",
        "SPLIT",
        "EDITED",
    ]


def test_tampered_explicit_lineage_falls_back_to_snapshot_differences(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("tampered-lineage")
    keep = ops.add(ctx, "Keep before.")
    preserve = ops.add(ctx, "Preserve before.")
    split = ops.add(ctx, "Split source.")
    absorb_survivor = ops.add(ctx, "Absorb survivor.")
    absorbed = ops.add(ctx, "Absorbed source.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="add",
            args={},
            description="Added source Memories",
        ),
    )

    ops.edit(ctx, keep.uid, "Keep was actually edited.")
    ops.edit(ctx, preserve.uid, "Preserve was actually edited.")
    ops.edit(ctx, absorbed.uid, "Absorbed source still exists and changed.")
    unexpected_child = ops.add(ctx, "Fresh but source was not removed.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="atomize",
            args={
                "trace": {
                    "schema_version": 1,
                    "operation_id": "tampered-operation",
                    "changes": [
                        {
                            "kind": "KEEP",
                            "source_uids": [keep.uid],
                            "result_uids": [keep.uid],
                        },
                        {
                            "kind": "PRESERVE",
                            "source_uids": [preserve.uid],
                            "result_uids": [preserve.uid],
                        },
                        {
                            "kind": "SPLIT",
                            "source_uids": [split.uid],
                            "result_uids": [unexpected_child.uid],
                        },
                        {
                            "kind": "ABSORB",
                            "source_uids": [
                                absorb_survivor.uid,
                                absorbed.uid,
                            ],
                            "result_uids": [absorb_survivor.uid],
                        },
                    ],
                }
            },
            description="Stored tampered lineage",
        ),
    )

    keep_report = reconstruct_memory_history(store, ctx, keep.uid)
    preserve_report = reconstruct_memory_history(store, ctx, preserve.uid)
    split_report = reconstruct_memory_history(store, ctx, split.uid)
    absorbed_report = reconstruct_memory_history(store, ctx, absorbed.uid)
    child_report = reconstruct_memory_history(store, ctx, unexpected_child.uid)

    assert "ATOMIZE_KEEP" not in {event.kind for event in keep_report.events}
    assert any(event.kind == "EDITED" for event in keep_report.events)
    assert "ATOMIZE_PRESERVED" not in {event.kind for event in preserve_report.events}
    assert any(event.kind == "EDITED" for event in preserve_report.events)
    assert not any(event.kind == "SPLIT" for event in split_report.events)
    assert split_report.component_uids == (split.uid,)
    assert not any(event.kind == "ABSORBED" for event in absorbed_report.events)
    assert any(event.kind == "EDITED" for event in absorbed_report.events)
    assert any(
        event.kind == "CREATED" and event.command == "atomize"
        for event in child_report.events
    )
    assert any(
        "trace metadata does not match its snapshot" in warning
        for warning in keep_report.warnings
    )


def test_tampered_v2_review_evidence_keeps_lineage_but_drops_evidence(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("tampered-reviewed-evidence")
    source = ops.add(ctx, "Use the same credential for staff access.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="add",
            args={},
            description="Added reviewed source",
        ),
    )
    source_position = ctx.ordered_uids().index(source.uid)
    ctx.remove(source.uid)
    child = Memory(
        uid="10000000-0000-4000-8000-000000000001",
        content="Use the staff credential for staff access.",
    )
    ctx.add(child, position=source_position)
    review_uid = "20000000-0000-4000-8000-000000000002"
    review_digest = "a" * 64
    declared_frame = "The same credential means the staff credential."
    store.save(
        ctx,
        AutoCheckpoint(
            command="atomize",
            args={
                "source_review_uid": review_uid,
                "source_review_digest": review_digest,
                "trace": {
                    "schema_version": 2,
                    "operation_id": ("30000000-0000-4000-8000-000000000003"),
                    "changes": [
                        {
                            "kind": "SPLIT",
                            "classification": "COMPOSITE",
                            "source_uids": [source.uid],
                            "result_uids": [child.uid],
                            "reason": "The reviewed referent permits a split.",
                            "reason_codes": ["A04_SOURCE_GROUNDED"],
                            "child_evidence": [
                                {
                                    "result_uid": child.uid,
                                    "source_spans": ["staff access"],
                                    "frame_spans": ["staff credential"],
                                }
                            ],
                            "review_evidence": {
                                "review_uid": review_uid,
                                "response_digest": review_digest,
                                "memory_uid": source.uid,
                                "review_item_uid": source.uid,
                                "source_analysis_uid": (
                                    "40000000-0000-4000-8000-000000000004"
                                ),
                                "uncertainty_reason": (
                                    "The credential antecedent was unresolved."
                                ),
                                "text": declared_frame,
                                # The corrupt digest must not erase the valid
                                # structural source-to-child lineage.
                                "digest": "0" * 64,
                            },
                        }
                    ],
                },
            },
            description="Stored tampered reviewed evidence",
        ),
    )

    report = reconstruct_memory_history(store, ctx, child.uid)
    split = next(event for event in report.events if event.kind == "SPLIT")

    assert split.evidence == "RECORDED"
    assert split.declared_frame is None
    assert split.child_evidence == ()
    assert any(
        "invalid reviewed atomize evidence" in warning for warning in report.warnings
    )


def test_trace_reads_current_state_after_revert(isolated_store):
    assert invoke("init", "revertible").exit_code == 0
    assert invoke("add", "keep").exit_code == 0
    store = MemoryStore()
    memory = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    keep_checkpoint = store.list_checkpoints("revertible")[0]["uid"]
    assert invoke("edit", memory.uid, "later").exit_code == 0
    assert invoke("revert", keep_checkpoint[:8]).exit_code == 0

    result = invoke("trace", memory.uid[:8])

    assert result.exit_code == 0
    assert "[revert]" in result.output
    lines = result.output.splitlines()
    revert_index = next(
        index for index, line in enumerate(lines) if line.startswith("[revert]")
    )
    revert_diff = "\n".join(lines[revert_index : revert_index + 3])
    assert "− [" in revert_diff and "later" in revert_diff
    assert "+ [" in revert_diff and "keep" in revert_diff


def test_trace_does_not_claim_uncheckpointed_current_state_as_origin(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("unrecorded")
    memory = ops.add(ctx, "Only the current file retains this.")
    store.save(ctx)

    report = reconstruct_memory_history(store, store.load_direct(ctx.name), memory.uid)

    assert report.originals == ()
    assert [event.kind for event in report.events] == ["HISTORY_GAP"]
    assert any("no retained" in warning.lower() for warning in report.warnings)


def test_trace_reconstructs_pure_canonical_reorder(isolated_store):
    store = MemoryStore()
    ctx = ops.init("reordered")
    first = ops.add(ctx, "First.")
    second = ops.add(ctx, "Second.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="add",
            args={},
            description="Added both",
        ),
    )
    ctx.order = [second.uid, first.uid]
    store.save(
        ctx,
        AutoCheckpoint(
            command="checkpoint",
            args={},
            description="Stored reordered frame",
        ),
    )

    report = reconstruct_memory_history(store, store.load_direct(ctx.name), first.uid)

    assert [event.kind for event in report.events] == [
        "CREATED",
        "REORDERED",
    ]
    reorder = report.events[-1]
    assert reorder.evidence == "RECONSTRUCTED"
    assert [state.uid for state in reorder.before] == [first.uid, second.uid]
    assert [state.uid for state in reorder.after] == [second.uid, first.uid]


def test_rationale_proposal_source_matches_context_and_memory_identity(
    isolated_store,
):
    store = MemoryStore()
    shared_uid = "10000000-0000-4000-8000-000000000001"

    intended_source = ops.init("intended-source")
    intended_source.add(Memory(uid=shared_uid, content="The intended source Memory."))
    unrelated_context = ops.init("unrelated-context")
    unrelated_context.add(Memory(uid=shared_uid, content="A colliding branch Memory."))
    target = ops.init("target")
    target.add("Existing target wording.")
    for ctx in (intended_source, unrelated_context, target):
        store.save(ctx)

    session = plan_update(
        intended_source,
        target,
        UpdatePlanProvider,
        status="impact",
    )
    store.save_impact_plan(session)

    intended_trace = reconstruct_memory_history(store, intended_source, shared_uid)
    unrelated_trace = reconstruct_memory_history(store, unrelated_context, shared_uid)
    intended_report = build_rationale(
        store,
        intended_source,
        intended_trace,
        None,
    )
    unrelated_report = build_rationale(
        store,
        unrelated_context,
        unrelated_trace,
        None,
    )

    assert [proposal.role for proposal in intended_report.proposals] == ["SOURCE"]
    assert unrelated_report.proposals == ()


def test_task1_rationale_keeps_structured_evidence_but_renders_only_provenance(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "temp/task-1").exit_code == 0
    lines = [f"raw line {index}" for index in range(1, 52)]
    lines[2] = "시간 이후 출입증 학생카드 필요하다."
    lines[3] = "nfc로 되어서 실물 카드만 필요하다."
    lines[4] = "안 되고 급한 용무면 전화해라."
    lines[5] = "직원들 출입구는 평소처럼 계속 출입 가능하다."
    lines[6] = "학생들 - 안내해야 한다 - 실물 카드를 받고나 앱으로."
    lines[13] = "같은 nfc 쓰는데 교직원들만 출입가능하다, 학생들은 여전히 못 들어온다."
    payload = "\n".join(lines)
    monkeypatch.setattr(add_command, "capture_paste", lambda: payload)
    assert invoke("add", "--paste").exit_code == 0

    store = MemoryStore()
    ctx = store.load_current_direct()
    memories = [item for item in ctx.iter_items() if isinstance(item, Memory)]
    target = memories[6]
    report = AmbiguityReport(
        memory_count=51,
        findings=(
            AmbiguityFinding(
                memory=target,
                interpretation="COMPETING",
                clarification="REQUIRED",
                ordinary_readings=(
                    "Students must bring a physical card.",
                    "Students may use an app credential.",
                ),
                reason="The accepted credential and student eligibility are unclear.",
                question="Can students use a card, an app, or neither?",
            ),
        ),
    )
    store.save_review_session(create_ambiguity_review(ctx, report))

    result = invoke("rationale", target.uid[:8])
    structured = invoke("rationale", target.uid[:8], "--json")

    assert result.exit_code == 0
    assert "PROVENANCE\n" in result.output
    assert "retained" in result.output
    assert "APPARENT PURPOSE" not in result.output
    assert "SAVED ANALYSIS" not in result.output
    assert "EVIDENCE USED FOR INFERENCE" not in result.output
    assert "Context(s)" not in result.output
    assert "LIMITS" not in result.output
    assert structured.exit_code == 0
    payload = json.loads(structured.output)
    assert payload["origin_events"][0]["source_occurrence"]["ordinal"] == 7
    assert payload["saved_analysis"]["interpretation"] == "COMPETING"
    budgets = payload["character_budgets"]
    assert payload["inference"] is None
    assert budgets["inference_limit"] == 0
    assert budgets["inference_source"] == 0
    assert budgets["provenance_limit"] < budgets["provenance_source"]


def test_trace_degrades_corrupt_add_source_or_uid_order_to_reconstructed(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "source-integrity").exit_code == 0
    monkeypatch.setattr(
        add_command,
        "capture_paste",
        lambda: "first raw line\nsecond raw line",
    )
    assert invoke("add", "--paste").exit_code == 0
    store = MemoryStore()
    ctx = store.load_current_direct()
    memories = [item for item in ctx.iter_items() if isinstance(item, Memory)]
    checkpoint_path = next(
        (isolated_store / "contexts" / ctx.name / "checkpoints").glob(
            "*Added-2-memories-from-i*.json"
        )
    )
    original = json.loads(checkpoint_path.read_text())

    corrupt_hash = json.loads(json.dumps(original))
    corrupt_hash["args"]["source"]["sha256"] = "0" * 64
    checkpoint_path.write_text(json.dumps(corrupt_hash))
    hash_report = reconstruct_memory_history(store, ctx, memories[0].uid)

    created = next(event for event in hash_report.events if event.kind == "CREATED")
    assert created.evidence == "RECONSTRUCTED"
    assert created.source_occurrence is not None
    assert not created.source_occurrence.exact_raw_source
    assert any("invalid add source hash" in item for item in hash_report.warnings)

    wrong_order = json.loads(json.dumps(original))
    wrong_order["args"]["memory_uids"].reverse()
    checkpoint_path.write_text(json.dumps(wrong_order))
    order_report = reconstruct_memory_history(store, ctx, memories[0].uid)

    created = next(event for event in order_report.events if event.kind == "CREATED")
    assert created.evidence == "RECONSTRUCTED"
    assert created.source_occurrence is not None
    assert not created.source_occurrence.exact_raw_source
    assert any("out of Context order" in item for item in order_report.warnings)


def test_rationale_excludes_stale_review_from_provenance_projection(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("stale")
    target = ops.add(ctx, "담당자에게 문의한다.")
    other = ops.add(ctx, "시설 안내.")
    store.save(
        ctx,
        AutoCheckpoint(command="add", args={}, description="Added context"),
    )
    report = AmbiguityReport(
        memory_count=2,
        findings=(
            AmbiguityFinding(
                memory=target,
                interpretation="SINGLE",
                clarification="HELPFUL",
                ordinary_readings=("Ask the responsible person.",),
                reason="The responsible person is unnamed.",
                question="Who is responsible?",
            ),
        ),
    )
    store.save_review_session(create_ambiguity_review(ctx, report))
    ops.edit(ctx, other.uid, "Changed frame.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="edit",
            args={"uid": other.uid, "content": "Changed frame."},
            description="Changed another Memory",
        ),
    )
    store.set_current("stale")

    result = invoke("rationale", target.uid[:8])
    structured = invoke("rationale", target.uid[:8], "--json")

    assert result.exit_code == 0
    assert "The responsible person is unnamed." not in result.output
    assert "APPARENT PURPOSE" not in result.output
    assert "Provenance alone does not establish" not in result.output
    assert structured.exit_code == 0
    assert json.loads(structured.output)["stale_analysis"] is True


def test_rationale_never_opens_query_only_source_or_mutates_authoritative_state(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("private-boundary")
    target = ops.add(ctx, "Explain this fragment.")
    source = store.create_query_source("restricted", "DO NOT DISCLOSE")
    ops.reference_query_context("restricted", source.uid, ctx)
    ops.add(ctx, "Visible direct evidence.")
    store.save(
        ctx,
        AutoCheckpoint(command="setup", args={}, description="Setup"),
    )
    store.set_current(ctx.name)
    before = {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
        and "rationale-inferences" not in path.relative_to(isolated_store).parts
    }

    def forbidden(*args, **kwargs):
        raise AssertionError("rationale opened a query-only source")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)
    result = invoke("rationale", target.uid[:8])
    after = {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
        and "rationale-inferences" not in path.relative_to(isolated_store).parts
    }
    cache_files = list((isolated_store / "rationale-inferences").rglob("*.json"))

    assert result.exit_code == 0
    assert "DO NOT DISCLOSE" not in result.output
    assert cache_files == []
    assert before == after
