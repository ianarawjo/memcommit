"""Location-first checkpoint projection for saved Update Diff inspection."""

from __future__ import annotations

import json
from dataclasses import replace

import memcommit.ops as ops
from memcommit.commands.update.checkpoint_history import (
    update_checkpoint_detail_renderer,
    update_checkpoint_entry,
    update_location_annotations,
    update_subtree_checkpoint_entries,
    update_subtree_locations,
)
from memcommit.commands.shared.history_picker import HistoryDetailView
from memcommit.update import (
    UpdateApplicationReceipt,
    UpdateCheckpointReceipt,
    operation_digest,
    plan_update,
)


class Provider:
    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_id = payload["source"]["memories"][0]["source_id"]
        target = payload["target"]["memories"][0]
        return json.dumps(
            {
                "edits": [
                    {
                        "target_id": target["target_id"],
                        "new_content": "Use the green entrance.",
                        "source_ids": [source_id],
                        "reason": "The entrance changed.",
                    }
                ],
                "additions": [],
                "removals": [],
            }
        )


def _session():
    source = ops.init("source")
    ops.add(source, "The green entrance is current.")
    target = ops.init("target/building-access")
    ops.add(target, "Use the blue entrance.")
    return plan_update(source, target, Provider, status="staged")


def test_location_annotation_groups_memory_operations_under_update_action():
    annotations = update_location_annotations(_session())

    assert annotations == {
        "target/building-access": (
            "update · 1 change · 1 EDIT · 0 ADD · 0 REMOVE · NOT CHECKPOINTED"
        )
    }


def test_checkpoint_row_names_the_actual_update_action_not_edit():
    session = _session()
    entry = update_checkpoint_entry(session, "target/building-access")

    assert entry.command == "update"
    assert entry.uid == session.uid
    assert entry.description == "STAGED semantic update · 1 target Memory change"
    assert entry.detail == "Staged Update · no checkpoint has been created."


def test_applied_location_uses_the_recorded_checkpoint_identity():
    session = _session()
    checkpoint_uid = "11111111-1111-4111-8111-111111111111"
    applied = session.with_application(
        UpdateApplicationReceipt(
            applied_at="2026-08-06T12:00:00-04:00",
            operation_digest=operation_digest(session.operations),
            target_digest="0" * 64,
            target_contexts=session.target_contexts,
            checkpoints=(
                UpdateCheckpointReceipt(
                    context_uid=session.operations[0].owner_context_uid,
                    context_name="target/building-access",
                    checkpoint_uid=checkpoint_uid,
                ),
            ),
        )
    )

    entry = update_checkpoint_entry(applied, "target/building-access")
    annotation = update_location_annotations(applied)["target/building-access"]

    assert entry.uid == checkpoint_uid
    assert entry.command == "update"
    assert entry.timestamp == "2026-08-06T12:00:00-04:00"
    assert "checkpoint 11111111" in annotation


def test_checkpoint_detail_keeps_update_action_and_red_then_green_transition():
    session = _session()
    entry = update_checkpoint_entry(session, "target/building-access")
    detail = update_checkpoint_detail_renderer(
        session,
        "target/building-access",
    )(entry)
    assert isinstance(detail, HistoryDetailView)
    fragments = detail.content
    rendered = "".join(text for _style, text in fragments)

    assert "ACTION      update" in rendered
    assert "UPDATE · EDIT Memory" in rendered
    assert ("class:semantic.edit", "EDIT") in fragments
    assert rendered.index(" - Use the blue entrance.") < rendered.index(
        " + Use the green entrance."
    )
    assert next(style for style, text in fragments if text == "blue") == (
        "class:memory-diff.remove.changed"
    )
    assert next(style for style, text in fragments if text == "green") == (
        "class:memory-diff.add.changed"
    )
    assert (
        sum(
            style in {"class:memory-diff.remove", "class:memory-diff.add"}
            and text == "Use the "
            for style, text in fragments
        )
        == 2
    )
    assert detail.unit_start_lines == (6,)


def test_subtree_history_collects_only_changed_owners_below_exact_root():
    session = _session()
    first = session.operations[0]
    second = replace(
        first,
        owner_context_name="target/temporary-parking",
        owner_context_uid="22222222-2222-4222-8222-222222222222",
        memory_uid="33333333-3333-4333-8333-333333333333",
    )
    unrelated = replace(
        first,
        owner_context_name="other/temporary-parking",
        owner_context_uid="44444444-4444-4444-8444-444444444444",
        memory_uid="55555555-5555-4555-8555-555555555555",
    )
    session = replace(session, operations=(first, second, unrelated))

    locations = update_subtree_locations(session, "target")
    entries = update_subtree_checkpoint_entries(session, "target")

    assert locations == (
        "target/building-access",
        "target/temporary-parking",
    )
    assert tuple(entry.location for entry in entries) == locations
    assert len({entry.uid for entry in entries}) == 2
    assert all(entry.location in entry.description for entry in entries)
