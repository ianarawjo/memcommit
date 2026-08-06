"""Location-first checkpoint projection for saved Update Diff inspection."""
from __future__ import annotations

import json

import memcommit.ops as ops
from memcommit.commands.update_checkpoint_history import (
    update_checkpoint_detail_renderer,
    update_checkpoint_entry,
    update_location_annotations,
)
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
            "update · 1 change · 1 EDIT · 0 ADD · 0 REMOVE · "
            "NOT CHECKPOINTED"
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
    fragments = update_checkpoint_detail_renderer(
        session,
        "target/building-access",
    )(entry)
    rendered = "".join(text for _style, text in fragments)

    assert "ACTION      update" in rendered
    assert "UPDATE · EDIT Memory" in rendered
    assert rendered.index(" - Use the blue entrance.") < rendered.index(
        " + Use the green entrance."
    )
    assert any(
        style.startswith("class:memory-diff.remove") and "blue" in text
        for style, text in fragments
    )
    assert any(
        style.startswith("class:memory-diff.add") and "green" in text
        for style, text in fragments
    )
