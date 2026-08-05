"""Human-readable action and impact receipts for Undo and Revert."""
from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.context import AutoCheckpoint, Memory
from memcommit.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_undo_reports_update_action_context_and_edited_memory(isolated_store):
    invoke("init", "test/update/to")
    invoke("add", "It is raining now")
    store = MemoryStore()
    context = store.load_current()
    memory_uid = next(iter(context.memories))
    context.replace(Memory(memory_uid, "going to rain today"))
    store.save(
        context,
        AutoCheckpoint(
            command="update",
            args={"source_context_name": "test/update/from"},
            description=(
                "Applied semantic update 12345678 from test/update/from."
            ),
        ),
    )

    result = invoke("undo")

    assert result.exit_code == 0
    assert "Undid command: mem update" in result.output
    assert (
        "Action detail: Applied semantic update 12345678 "
        "from test/update/from."
    ) in result.output


def test_legacy_checkpoint_without_recorded_preimage_uses_prior_state(
    isolated_store,
):
    invoke("init", "test/update/to")
    invoke("add", "It is raining now")
    store = MemoryStore()
    context = store.load_current()
    memory_uid = next(iter(context.memories))
    context.replace(Memory(memory_uid, "going to rain today"))
    store.save(
        context,
        AutoCheckpoint(
            command="update",
            args={"source_context_name": "test/update/from"},
            description="Legacy semantic update",
        ),
    )
    checkpoint_dir = (
        isolated_store / "contexts" / "test" / "update" / "to"
        / "checkpoints"
    )
    update_path = max(
        checkpoint_dir.glob("*.json"),
        key=lambda path: json.loads(path.read_text())["timestamp"],
    )
    record = json.loads(update_path.read_text())
    assert record.pop("command_before") is not None
    update_path.write_text(json.dumps(record))

    result = invoke("undo")

    assert result.exit_code == 0, result.output
    assert "Undid command: mem update" in result.output
    assert store.load_current().memories[memory_uid].content == (
        "It is raining now"
    )
    assert "Affected Context: test/update/to" in result.output
    assert "Affected content: 1 Memory edited" in result.output
    assert (
        f'~ [{memory_uid[:8]}] Memory: "going to rain today" '
        '→ "It is raining now"'
    ) in result.output


def test_revert_reports_target_action_and_removed_content(isolated_store):
    invoke("init", "notes")
    invoke("add", "keep this")
    store = MemoryStore()
    target_uid = store.list_checkpoints("notes")[0]["uid"]
    added = invoke("add", "remove this")
    removed_uid = added.output.split("[", 1)[1].split("]", 1)[0]

    result = invoke("revert", target_uid[:8])

    assert result.exit_code == 0
    assert "Reverted Context: notes" in result.output
    assert "Restored state recorded by: mem add" in result.output
    assert 'Action detail: Added: "keep this"' in result.output
    assert "Affected Context: notes" in result.output
    assert "Affected content: 1 Memory removed" in result.output
    assert f'- [{removed_uid}] Memory: "remove this"' in result.output
    assert "Undo command: mem undo" in result.output
    assert "Exact recovery checkpoint: mem revert" in result.output


def test_undo_of_revert_names_revert_as_the_action(isolated_store):
    invoke("init", "notes")
    invoke("add", "restore me")
    store = MemoryStore()
    init_uid = store.list_checkpoints("notes")[-1]["uid"]
    invoke("revert", init_uid[:8])

    result = invoke("undo")

    assert result.exit_code == 0
    assert "Undid command: mem revert" in result.output
    assert f"Action detail: Reverted to checkpoint [{init_uid[:8]}]" in result.output
    assert "Affected content: 1 Memory added" in result.output
    assert 'Memory: "restore me"' in result.output


def test_receipt_escapes_content_that_could_forge_a_heading(isolated_store):
    invoke("init", "notes")
    malicious = "bad\nAffected Context: forged\u202e"
    invoke("add", malicious)

    result = invoke("undo")

    assert result.exit_code == 0
    assert sum(
        line.startswith("Affected Context:")
        for line in result.output.splitlines()
    ) == 1
    assert not any(
        line.startswith("Affected Context: forged")
        for line in result.output.splitlines()
    )
    assert r'"bad\nAffected Context: forged\u202e"' in result.output


def test_receipt_bounds_large_change_details_but_keeps_exact_counts(
    isolated_store,
):
    invoke("init", "notes")
    store = MemoryStore()
    context = store.load_current()
    for index in range(14):
        context.add(f"item {index}")
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"count": 14},
            description="Added a batch of 14 memories",
        ),
    )

    result = invoke("undo")

    assert result.exit_code == 0
    assert "Affected content: 14 Memories removed" in result.output
    assert "... 2 more affected direct items not shown" in result.output


def test_memory_ref_impact_shows_pointer_but_not_target_content(
    isolated_store,
):
    invoke("init", "source")
    added = invoke("add", "SECRET TARGET")
    source_memory_uid = added.output.split("[", 1)[1].split("]", 1)[0]
    invoke("init", "notes")
    invoke("reference", source_memory_uid, "--from", "source")

    result = invoke("undo")

    assert result.exit_code == 0
    assert "Undid command: mem reference" in result.output
    assert "Affected content: 1 MemoryRef removed" in result.output
    assert 'MemoryRef: to Context "source"' in result.output
    assert "SECRET TARGET" not in result.output
