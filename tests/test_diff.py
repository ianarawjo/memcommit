"""Single-checkpoint command contract and read-only Diff presentation."""

from __future__ import annotations

import json
import uuid

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.commands.diff import command as diff_command
from memcommit.adapters.console.entrypoint import app
from memcommit.application.capabilities.history.query.checkpoint_history_slicing import (
    CheckpointHistorySlice,
)
from memcommit.core.context import AutoCheckpoint, Context
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _checkpointed_history(
    store: MemoryStore,
    *,
    name: str = "campus-wiki",
) -> tuple[Context, str, str, str, str]:
    context = ops.init(name)
    retained = ops.add(context, "Hours remain unchanged.")
    edited = ops.add(context, "Visitor parking is available in Lot A.")
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="Initial guidance"),
    )
    first_uid = store.list_checkpoints(name)[0]["uid"]

    ops.edit(context, edited.uid, "Visitor parking is available in Lot C.")
    added = ops.add(context, "Follow temporary parking signs.")
    store.save(
        context,
        AutoCheckpoint(command="update", args={}, description="Parking update"),
    )
    latest_uid = store.list_checkpoints(name)[0]["uid"]
    store.set_current(name)
    return context, first_uid, latest_uid, retained.uid, added.uid


def _store_bytes(root) -> dict:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_diff_bare_requires_a_current_context_without_creating_a_profile(
    isolated_store,
):
    assert not isolated_store.exists()

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 1
    assert "no current Context" in result.stderr
    assert "Context name/UID or checkpoint UID" in result.stderr
    assert not isolated_store.exists()


def test_diff_bare_shows_the_current_context_latest_checkpoint(isolated_store):
    store = MemoryStore()
    _context, _first_uid, latest_uid, retained_uid, _added_uid = (
        _checkpointed_history(store)
    )

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 0, result.output
    assert "DIFF · campus-wiki" in result.output
    assert f"[CHECKPOINT {latest_uid[:8]}]" in result.output
    assert "1 edited · 1 added · 0 removed" in result.output
    assert "Visitor parking is available in Lot A." in result.output
    assert "Visitor parking is available in Lot C." in result.output
    assert "Follow temporary parking signs." in result.output
    assert "Hours remain unchanged." not in result.output
    assert f"[{retained_uid[:8]}]" not in result.output
    assert "1 unchanged hidden" in result.output


def test_diff_ignores_the_active_update_slot(isolated_store):
    store = MemoryStore()
    _checkpointed_history(store)
    (isolated_store / "staged-update.json").write_text(
        '{"status":"not-a-valid-update"}',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 0, result.output
    assert "DIFF · campus-wiki" in result.output
    assert "Update preview" not in result.output


def test_diff_context_name_returns_its_latest_checkpoint(isolated_store):
    store = MemoryStore()
    _context, _first_uid, latest_uid, _retained_uid, _added_uid = (
        _checkpointed_history(store)
    )

    result = runner.invoke(app, ["diff", "campus-wiki", "--stat"])

    assert result.exit_code == 0, result.output
    assert f"CHECKPOINT  {latest_uid}" in result.output
    assert "CONTEXT     campus-wiki" in result.output


def test_diff_context_operand_accepts_context_uid(isolated_store):
    store = MemoryStore()
    context, _first_uid, latest_uid, _retained_uid, _added_uid = (
        _checkpointed_history(store)
    )

    result = runner.invoke(app, ["diff", context.uid[:8], "--stat"])

    assert result.exit_code == 0, result.output
    assert f"CHECKPOINT  {latest_uid}" in result.output
    assert "CONTEXT     campus-wiki" in result.output


def test_diff_bare_checkpoint_uid_reopens_that_exact_revision(isolated_store):
    store = MemoryStore()
    _context, first_uid, latest_uid, _retained_uid, _added_uid = (
        _checkpointed_history(store)
    )

    result = runner.invoke(app, ["diff", first_uid[:8]])

    assert result.exit_code == 0, result.output
    assert f"[CHECKPOINT {first_uid[:8]}]" in result.output
    assert latest_uid not in result.output
    assert "2 added" in result.output
    assert "Visitor parking is available in Lot A." in result.output


def test_diff_explicit_context_and_checkpoint_forms_reopen_exact_revision(
    isolated_store,
):
    store = MemoryStore()
    _context, first_uid, _latest_uid, _retained_uid, _added_uid = (
        _checkpointed_history(store)
    )

    operand = runner.invoke(
        app,
        ["diff", first_uid[:8], "--context", "campus-wiki", "--stat"],
    )
    option = runner.invoke(
        app,
        [
            "diff",
            "campus-wiki",
            "--checkpoint",
            first_uid[:8],
            "--stat",
        ],
    )

    assert operand.exit_code == 0, operand.output
    assert option.exit_code == 0, option.output
    assert f"CHECKPOINT  {first_uid}" in operand.output
    assert f"CHECKPOINT  {first_uid}" in option.output


def test_diff_relative_context_locator_uses_one_current_snapshot(isolated_store):
    store = MemoryStore()
    _checkpointed_history(store, name="project/archive")
    current = ops.init("project/current")
    store.save(current)
    store.set_current(current.name)

    result = runner.invoke(app, ["diff", "../archive", "--stat"])

    assert result.exit_code == 0, result.output
    assert "CONTEXT     project/archive" in result.output


def test_diff_interactive_default_opens_one_read_only_viewer(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _checkpointed_history(store)
    viewed: dict[str, object] = {}
    monkeypatch.setattr(diff_command, "interactive_report_terminal", lambda: True)
    monkeypatch.setattr(
        diff_command,
        "open_checkpoint_revision_viewer",
        lambda history, entry, **kwargs: viewed.update(
            history=history,
            entry=entry,
            kwargs=kwargs,
        ),
    )

    result = runner.invoke(app, ["diff", "--verbose"])

    assert result.exit_code == 0, result.output
    assert isinstance(viewed["history"], CheckpointHistorySlice)
    assert viewed["kwargs"] == {
        "context_name": "campus-wiki",
        "verbose": True,
    }
    assert result.output == ""


def test_diff_raw_and_stat_bypass_the_viewer(isolated_store, monkeypatch):
    store = MemoryStore()
    _checkpointed_history(store)
    monkeypatch.setattr(diff_command, "interactive_report_terminal", lambda: True)
    monkeypatch.setattr(
        diff_command,
        "open_checkpoint_revision_viewer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("raw/stat Diff must not open the Viewer")
        ),
    )

    raw = runner.invoke(app, ["diff", "--raw"])
    stat = runner.invoke(app, ["diff", "--stat"])

    assert raw.exit_code == 0, raw.output
    assert "diff --mem campus-wiki#" in raw.output
    assert "-Visitor parking is available in Lot A." in raw.output
    assert "+Visitor parking is available in Lot C." in raw.output
    assert stat.exit_code == 0, stat.output
    assert "SUMMARY" in stat.output
    assert "Visitor parking" not in stat.output


def test_diff_verbose_includes_unchanged_memories_and_full_uids(isolated_store):
    store = MemoryStore()
    _context, _first_uid, latest_uid, retained_uid, _added_uid = (
        _checkpointed_history(store)
    )

    result = runner.invoke(app, ["diff", "--verbose"])

    assert result.exit_code == 0, result.output
    assert f"[CHECKPOINT {latest_uid}]" in result.output
    assert f"[{retained_uid}] Hours remain unchanged." in result.output
    assert "unchanged hidden" not in result.output


def test_diff_is_read_only(isolated_store):
    store = MemoryStore()
    _checkpointed_history(store)
    before = _store_bytes(isolated_store)

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 0, result.output
    assert _store_bytes(isolated_store) == before


def test_diff_rejects_a_second_checkpoint_operand(isolated_store):
    store = MemoryStore()
    _context, first_uid, latest_uid, _retained_uid, _added_uid = (
        _checkpointed_history(store)
    )

    result = runner.invoke(app, ["diff", first_uid[:8], latest_uid[:8]])

    assert result.exit_code == 2
    assert "unexpected extra argument" in result.stderr.lower()


def test_diff_bare_operand_rejects_context_checkpoint_collision(isolated_store):
    store = MemoryStore()
    _context, _first_uid, latest_uid, _retained_uid, _added_uid = (
        _checkpointed_history(store)
    )
    # Existing legacy names may predate the portable-name rule that reserves
    # the visible UUID-prefix shape for typed CLI operands.
    collision = Context(uid=str(uuid.uuid4()), name=latest_uid[:8])
    collision_path = store._context_file(collision.name)
    collision_path.parent.mkdir(parents=True)
    collision_path.write_text(json.dumps(collision.to_dict()), encoding="utf-8")

    result = runner.invoke(app, ["diff", latest_uid[:8]])

    assert result.exit_code == 1
    assert "matches both Context" in result.stderr
    assert "--context or --checkpoint" in result.stderr


def test_diff_reports_a_context_without_checkpoints(isolated_store):
    store = MemoryStore()
    context = ops.init("empty-history")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 1
    assert "has no checkpoints" in result.stderr


def test_diff_rejects_raw_and_stat_together_without_touching_store(
    isolated_store,
):
    assert not isolated_store.exists()

    result = runner.invoke(app, ["diff", "--raw", "--stat"])

    assert result.exit_code == 2
    assert "cannot be used together" in result.stderr
    assert not isolated_store.exists()
