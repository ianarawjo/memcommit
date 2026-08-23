"""Human-readable action and impact receipts for Undo and Revert."""
from __future__ import annotations

import click
import json

import pytest
from click.testing import CliRunner as ClickCliRunner
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.command_history import CommandContextChange, ContextCommandUnit
from memcommit.commands.restoration_present import (
    _render_impact,
    _restored_command,
)
from memcommit.context import AutoCheckpoint, Memory
from memcommit.interfaces.console.theme import (
    SemanticColorRole,
    memory_object_color_rgb,
    semantic_color_rgb,
)
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import (
    source_object_label,
    source_relationship_label,
)
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

    result = runner.invoke(app, ["revert", target_uid[:8]], color=True)
    plain = click.unstyle(result.output)

    assert result.exit_code == 0
    assert "Reverted Context: notes" in plain
    assert "Restored state recorded by: mem add" in plain
    assert 'Action detail: Added: "keep this"' in plain
    assert "Affected Context: notes" in plain
    assert "Affected content: 1 Memory removed" in plain
    memory_label = source_object_label(SourceForm.MEMORY)
    assert f'- [{memory_label} {removed_uid}] "remove this"' in plain
    assert f"[{removed_uid}] Memory:" not in plain
    assert "Undo command: mem undo" in plain
    assert "Exact recovery checkpoint: mem revert" in plain
    assert "--discard-newer" in plain
    for text, role in (
        ("mem add", SemanticColorRole.ADD),
        (f"[{target_uid[:8]}]", SemanticColorRole.HISTORY),
        ("mem undo", SemanticColorRole.UNDO),
        ("mem revert", SemanticColorRole.UNDO),
    ):
        assert click.style(
            text,
            fg=semantic_color_rgb(role),
            bold=True,
        ) in result.output
    assert click.style(
        '"remove this"',
        fg=semantic_color_rgb(SemanticColorRole.REMOVE),
    ) in result.output


def test_revert_impact_colors_typed_markers_without_changing_plain_text():
    removed_uid = "11111111-1111-1111-1111-111111111111"
    edited_uid = "22222222-2222-2222-2222-222222222222"
    added_uid = "33333333-3333-3333-3333-333333333333"
    ref_uid = "44444444-4444-4444-4444-444444444444"

    @click.command()
    def receipt():
        _render_impact(
            context_name="notes",
            before_snapshot={
                "memories": {
                    removed_uid: {"type": "memory", "content": "remove me"},
                    edited_uid: {"type": "memory", "content": "before"},
                },
                "order": [removed_uid, edited_uid],
            },
            after_snapshot={
                "memories": {
                    edited_uid: {"type": "memory", "content": "after"},
                    added_uid: {"type": "memory", "content": "add me"},
                    ref_uid: {
                        "type": "memory_ref",
                        "target_context": {
                            "uid": "source-context-uid",
                            "name": "source/notes",
                        },
                        "target_memory_uid": "55555555-5555-5555-5555-555555555555",
                    },
                },
                "order": [edited_uid, added_uid, ref_uid],
            },
            resolved_memory_ref_contents={
                (
                    "source/notes",
                    "source-context-uid",
                    "55555555-5555-5555-5555-555555555555",
                ): "embedded source body"
            },
        )

    colored = ClickCliRunner().invoke(receipt, color=True)
    plain = ClickCliRunner().invoke(receipt, color=False)

    assert colored.exit_code == 0, colored.output
    assert plain.exit_code == 0, plain.output
    assert click.unstyle(colored.output) == plain.output
    memory_label = source_object_label(SourceForm.MEMORY)
    embed_label = source_relationship_label(SourceForm.MEMORY_REF)
    for marker, label, uid, role in (
        ("-", memory_label, removed_uid, SemanticColorRole.REMOVE),
        ("~", memory_label, edited_uid, SemanticColorRole.EDIT),
        ("+", memory_label, added_uid, SemanticColorRole.ADD),
        ("+", embed_label, ref_uid, SemanticColorRole.ADD),
    ):
        assert click.style(
            marker,
            fg=semantic_color_rgb(role),
            bold=True,
        ) in colored.output
        assert (
            f"  {marker} [{label} {uid[:8]}]"
            in plain.output
        )
    summary = (
        "Affected content: 1 Memory added, 1 Memory ref added, "
        "1 Memory edited, 1 Memory removed"
    )
    # The compact count is report prose. Typed detail rows below it carry the
    # semantic colors without making the heading visually noisy.
    assert summary in colored.output
    for text, role in (
        ('"before"', SemanticColorRole.REMOVE),
        ('"after"', SemanticColorRole.EDIT),
        ('"remove me"', SemanticColorRole.REMOVE),
    ):
        assert click.style(
            text,
            fg=semantic_color_rgb(role),
        ) in colored.output
    assert click.style(
        '"add me"',
        fg=memory_object_color_rgb(),
    ) in colored.output
    assert click.style(
        '"embedded source body"',
        fg=memory_object_color_rgb(),
    ) in colored.output
    assert click.style(
        embed_label,
        fg=semantic_color_rgb(SemanticColorRole.EMBED),
    ) in colored.output
    assert (
        'source/notes:55555555 "embedded source body"  READ ONLY'
        in plain.output
    )
    assert f"[{removed_uid[:8]}] Memory:" not in plain.output
    assert f"[{ref_uid[:8]}] Memory ref:" not in plain.output
    assert " Memory [55555555]" not in plain.output
    assert "to Context" not in plain.output


def test_revert_impact_marks_an_unavailable_live_embed_as_dangling():
    ref_uid = "44444444-4444-4444-4444-444444444444"

    @click.command()
    def receipt():
        _render_impact(
            context_name="notes",
            before_snapshot={"memories": {}, "order": []},
            after_snapshot={
                "memories": {
                    ref_uid: {
                        "type": "memory_ref",
                        "uid": ref_uid,
                        "target_context": {
                            "uid": "source-context-uid",
                            "name": "source/notes",
                        },
                        "target_memory_uid": (
                            "55555555-5555-5555-5555-555555555555"
                        ),
                    }
                },
                "order": [ref_uid],
            },
        )

    result = ClickCliRunner().invoke(receipt, color=False)

    assert result.exit_code == 0, result.output
    assert (
        "  + [embedded 44444444] source/notes:55555555  DANGLING"
        in result.output
    )
    assert "READ ONLY" not in result.output


def test_undo_of_revert_names_revert_as_the_action(isolated_store):
    invoke("init", "notes")
    invoke("add", "restore me")
    store = MemoryStore()
    init_uid = store.list_checkpoints("notes")[-1]["uid"]
    invoke("revert", init_uid[:8])

    result = invoke("undo")

    assert result.exit_code == 0
    assert f"Undid command: mem revert {init_uid} --keep" in result.output
    assert "Affected Memories: 1 · + 1 added" in result.output
    assert "restore me" not in result.output


def test_undo_and_redo_color_success_and_memory_effect_separately(
    isolated_store,
):
    invoke("init", "notes")
    added = invoke("add", "remove and restore me")
    memory_uid = added.output.split("[", 1)[1].split("]", 1)[0]
    full_memory_uid = next(iter(MemoryStore().load_current().memories))
    invoke("remove", memory_uid)

    undone = runner.invoke(app, ["undo"], color=True)

    assert undone.exit_code == 0, undone.output
    assert click.style(
        "Undid command: ",
        fg=semantic_color_rgb(SemanticColorRole.UNDO),
        bold=True,
    ) in undone.output
    assert click.style(
        "+ 1 added",
        fg=semantic_color_rgb(SemanticColorRole.ADD),
    ) in undone.output
    assert f"mem remove {full_memory_uid[:8]} --context notes" in click.unstyle(
        undone.output
    )
    assert full_memory_uid not in undone.output

    redone = runner.invoke(app, ["redo"], color=True)

    assert redone.exit_code == 0, redone.output
    assert click.style(
        "Redid command: ",
        fg=semantic_color_rgb(SemanticColorRole.REDO),
        bold=True,
    ) in redone.output
    assert click.style(
        "- 1 removed",
        fg=semantic_color_rgb(SemanticColorRole.REMOVE),
    ) in redone.output

    assert runner.invoke(app, ["undo"]).exit_code == 0
    store = MemoryStore()
    context = store.load_current()
    restored_memory = next(iter(context.memories.values()))
    context.replace(Memory(restored_memory.uid, "edited after restore"))
    store.save(
        context,
        AutoCheckpoint(
            command="edit",
            args={"uid": restored_memory.uid, "content": "edited after restore"},
            description="Edited restored Memory",
        ),
    )

    edit_undone = runner.invoke(app, ["undo"], color=True)

    assert edit_undone.exit_code == 0, edit_undone.output
    assert click.style(
        "~ 1 edited",
        fg=semantic_color_rgb(SemanticColorRole.EDIT),
    ) in edit_undone.output


def test_undo_expands_a_colliding_direct_memory_prefix(isolated_store):
    invoke("init", "notes")
    store = MemoryStore()
    context = store.load_current()
    first = Memory(
        "deadbeef-1111-1111-1111-111111111111",
        "remove this one",
    )
    second = Memory(
        "deadbeef-2222-2222-2222-222222222222",
        "keep this one",
    )
    context.add(first)
    context.add(second)
    store.save(
        context,
        AutoCheckpoint(
            command="seed",
            args={},
            description="Seed colliding UIDs",
        ),
    )
    removed = runner.invoke(app, ["remove", first.uid])
    assert removed.exit_code == 0, removed.output

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 0, undone.output
    assert "mem remove deadbeef-1 --context notes" in undone.output
    assert first.uid not in undone.output


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
    assert "Affected Memories: 0 · Other: 1 Memory ref removed" in result.output
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
            "mem chunk memory-uid --method paragraphs --context work/notes",
        ),
        (
            "chunk",
            {
                "context": "work/notes",
                "method": "sentences",
                "splits": [
                    {"uid": "memory-uid", "chunk_uids": ["a", "b"]}
                ],
            },
            "mem chunk --method sentences --context work/notes",
        ),
        (
            "chunk",
            {
                "context": "work/notes",
                "method": "clauses",
                "break_on": ",;",
                "min_chars": 40,
                "max_chars": 120,
                "splits": [
                    {"uid": "memory-uid", "chunk_uids": ["a", "b"]}
                ],
            },
            (
                "mem chunk --method clauses --break-on ',;' --min-chars 40 "
                "--max-chars 120 --context work/notes"
            ),
        ),
        (
            "clear",
            {"context": "work/notes"},
            "mem clear work/notes",
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
            "mem revert target-checkpoint-uid --discard-newer",
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
        "mem sever source/all rules/private result/kept --source-descendants "
        "--criteria-root-only --accept"
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


def test_undo_keeps_full_uid_when_legacy_scope_cannot_be_reconstructed():
    full_uid = "b925d6bf-aec7-4de5-a432-7cf627d72628"

    unit = _command_unit("remove", {"uid": full_uid})

    assert _restored_command(unit) == (
        f"mem remove {full_uid} --context work/notes"
    )
