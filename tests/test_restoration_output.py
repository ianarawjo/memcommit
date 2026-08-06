"""Human-readable action and impact receipts for Undo and Revert."""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.command_history import CommandContextChange, ContextCommandUnit
from memcommit.commands.restoration_present import _restored_command
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
    assert (
        "Undid command: mem update --from test/update/from --to test/update/to"
        in result.output
    )
    assert "Affected Contexts: 1" in result.output
    assert "Affected Memories: 1 · ~ 1 edited" in result.output
    assert len(result.output.splitlines()) == 1


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
    assert (
        "Undid command: mem update --from test/update/from --to test/update/to"
        in result.output
    )
    assert store.load_current().memories[memory_uid].content == (
        "It is raining now"
    )
    assert "Affected Memories: 1 · ~ 1 edited" in result.output
    assert memory_uid[:8] not in result.output


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
    assert f"Undid command: mem revert {init_uid}" in result.output
    assert "Affected Memories: 1 · + 1 added" in result.output
    assert "restore me" not in result.output


def test_receipt_escapes_content_that_could_forge_a_heading(isolated_store):
    invoke("init", "notes")
    malicious = "bad\nAffected Context: forged\u202e"
    invoke("add", malicious)

    result = invoke("undo")

    assert result.exit_code == 0
    assert len(result.output.splitlines()) == 1
    assert "Affected Context: forged" not in result.output
    assert "bad" not in result.output


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
    assert "Affected Memories: 14 · - 14 removed" in result.output
    assert len(result.output.splitlines()) == 1


def test_memory_ref_impact_shows_pointer_but_not_target_content(
    isolated_store,
):
    invoke("init", "source")
    added = invoke("add", "SECRET TARGET")
    source_memory_uid = added.output.split("[", 1)[1].split("]", 1)[0]
    stored_source_uid = next(iter(MemoryStore().load_current().memories))
    invoke("init", "notes")
    invoke("reference", source_memory_uid, "--from", "source")

    result = invoke("undo")

    assert result.exit_code == 0
    assert (
        f"Undid command: mem reference {stored_source_uid} "
        "--from source --into notes"
    ) in result.output
    assert "Affected Memories: 0 · Other: 1 MemoryRef removed" in result.output
    assert "SECRET TARGET" not in result.output


def _command_unit(
    command: str,
    args: dict[str, object],
    *,
    context_name: str = "work/notes",
    created: bool = False,
) -> ContextCommandUnit:
    return ContextCommandUnit(
        uid="unit",
        command=command,
        description="",
        started_at="2026-08-06T00:00:00+00:00",
        completed_at="2026-08-06T00:00:00+00:00",
        changes=(
            CommandContextChange(
                context_uid="context-uid",
                context_name=context_name,
                before=None if created else {},
                after={},
                checkpoint_uid="checkpoint-uid",
            ),
        ),
        checkpoint_args=(args,),
    )


@pytest.mark.parametrize(
    ("command", "args", "expected"),
    (
        (
            "add",
            {"content": "private text"},
            "mem add <CONTENT> --context work/notes",
        ),
        (
            "edit",
            {"uid": "memory-uid", "content": "private replacement"},
            "mem edit memory-uid <CONTENT> --context work/notes",
        ),
        (
            "remove",
            {"uid": "memory-uid"},
            "mem remove memory-uid --context work/notes",
        ),
        (
            "chunk",
            {"uid": "memory-uid", "method": "paragraphs"},
            "mem chunk memory-uid --method paragraphs",
        ),
        (
            "clear",
            {"context": "work/notes"},
            "mem clear work/notes --force",
        ),
        (
            "embed",
            {"child": "source/child", "into": "work/notes"},
            "mem embed source/child --into work/notes",
        ),
        (
            "reference",
            {
                "memory_uid": "memory-uid",
                "source": "source/notes",
                "into": "work/notes",
            },
            "mem reference memory-uid --from source/notes --into work/notes",
        ),
        (
            "merge",
            {"source": "source/notes"},
            "mem merge source/notes",
        ),
        (
            "forget",
            {"query": "private instruction"},
            "mem forget <INSTRUCTION>",
        ),
        (
            "integrate",
            {"info": "private information"},
            "mem integrate <INFO>",
        ),
        (
            "revert",
            {"target_uid": "target-checkpoint-uid"},
            "mem revert target-checkpoint-uid",
        ),
        (
            "atomize",
            {"analysis_uid": "analysis-uid"},
            "mem atomize --save --context work/notes",
        ),
        (
            "atomize-grounding",
            {"grounding": {"session_uid": "session-uid"}},
            "mem atomize --accept-grounding --context work/notes",
        ),
        (
            "dev query-source install",
            {
                "name": "hidden/source",
                "into": "work/notes",
            },
            "mem dev query-source install hidden/source --into work/notes",
        ),
    ),
)
def test_undo_reconstructs_supported_context_commands(
    command: str,
    args: dict[str, object],
    expected: str,
):
    assert _restored_command(_command_unit(command, args)) == expected


def test_undo_reconstructs_meld_sever_and_translate_commands():
    meld = _command_unit(
        "meld",
        {
            "meld": {
                "mode": "DIRECTIONAL",
                "sources": [
                    {"role": "INCOMING", "context_name": "new/facts"},
                    {"role": "BASELINE", "context_name": "work/notes"},
                ],
                "target_baseline": {"context_name": "work/notes"},
            }
        },
    )
    sever = _command_unit(
        "sever",
        {
            "sever": {
                "source": "source/all",
                "source_scope": "INCLUDE_DESCENDANTS",
                "criteria": "rules/private",
                "criteria_scope": "THIS_CONTEXT_ONLY",
                "output": "result/kept",
            }
        },
    )
    translate = _command_unit(
        "translate",
        {
            "target_language": "Korean",
            "source_context": {"name": "work/notes"},
            "scope": {"kind": "memory", "memory_uid": "memory-uid"},
        },
    )

    assert _restored_command(meld) == (
        "mem meld new/facts --into work/notes --accept"
    )
    assert _restored_command(sever) == (
        "mem sever --source source/all --criteria rules/private "
        "--save-as result/kept --source-descendants --criteria-only --accept"
    )
    assert _restored_command(translate) == (
        "mem translate memory-uid --to Korean --in-place"
    )


def test_undo_uses_public_grant_operand_instead_of_authority_owner():
    unit = _command_unit(
        "remove",
        {
            "uid": "memory-uid",
            "authority_grant": {
                "uid": "grant-uid",
                "revision": 2,
                "grantee_profile_uid": "profile-uid",
                "public_context": "shared/notes",
            },
        },
        context_name="authority/private-notes",
    )

    assert _restored_command(unit) == (
        "mem remove memory-uid --context shared/notes"
    )
