"""Global identity and atomic recovery contracts for recursive Checkpoint."""

from __future__ import annotations

import re
import uuid

import pytest
from typer.testing import CliRunner

from memcommit.application.retained_history.checkpoint_catalog import (
    CheckpointCatalogError,
    resolve_checkpoint_unit,
)
from memcommit.adapters.console.entrypoint import app
from memcommit.commands.shared.history_picker import revert_exact_command_review
from memcommit.persistence.store import MemoryStore, context_record_digest


runner = CliRunner(mix_stderr=False)


def invoke(*args: str):
    return runner.invoke(app, list(args))


def _recursive_baseline() -> tuple[MemoryStore, str, dict[str, str]]:
    for name in ("tree", "tree/child", "tree/child/deep"):
        assert invoke("init", name).exit_code == 0
        assert invoke("add", f"{name} baseline", "--context", name).exit_code == 0
    result = invoke(
        "checkpoint",
        "tree",
        "recursive baseline",
        "--recursive",
    )
    assert result.exit_code == 0, result.output
    match = re.search(r"\[([0-9a-f]{8})\]", result.output)
    assert match is not None
    store = MemoryStore()
    member_uids = {
        name: next(
            checkpoint["uid"]
            for checkpoint in store.list_checkpoints(name)
            if checkpoint.get("message") == "recursive baseline"
        )
        for name in ("tree", "tree/child", "tree/child/deep")
    }
    root_uid = member_uids["tree"]
    assert root_uid.startswith(match.group(1))
    assert f"mem revert {root_uid} --keep" in result.output
    return store, root_uid, member_uids


def test_recursive_receipt_uses_a_real_global_checkpoint_uid_and_manifest(
    isolated_store,
):
    store, root_uid, member_uids = _recursive_baseline()

    root = next(
        checkpoint
        for checkpoint in store.list_checkpoints("tree")
        if checkpoint["uid"] == root_uid
    )
    manifest = root["args"]["checkpoint_set"]
    assert manifest == {
        "version": 2,
        "uid": root_uid,
        "root": {
            "uid": store.load_direct("tree").uid,
            "name": "tree",
        },
        "include_descendants": True,
        "members": [
            {
                "context_uid": store.load_direct(name).uid,
                "context_name": name,
                "checkpoint_uid": member_uids[name],
            }
            for name in ("tree", "tree/child", "tree/child/deep")
        ],
    }

    for name, checkpoint_uid in member_uids.items():
        unit = resolve_checkpoint_unit(store, checkpoint_uid[:8])
        assert unit.canonical_uid == root_uid
        assert [member.context_name for member in unit.members] == [
            "tree",
            "tree/child",
            "tree/child/deep",
        ]
        assert unit.selected_uid == checkpoint_uid


def test_global_recursive_uid_reverts_every_member_and_undo_restores_the_unit(
    isolated_store,
):
    store, root_uid, _member_uids = _recursive_baseline()
    for name in ("tree", "tree/child", "tree/child/deep"):
        assert invoke("add", f"{name} later", "--context", name).exit_code == 0
    store.set_current("tree/child/deep")

    result = invoke("revert", root_uid[:8], "--keep")

    assert result.exit_code == 0, result.output
    assert f"Reverted checkpoint unit: [{root_uid[:8]}]" in result.output
    assert "Affected Contexts: 3" in result.output
    for name in ("tree", "tree/child", "tree/child/deep"):
        assert [
            memory.content for memory in store.load_direct(name).memories.values()
        ] == [f"{name} baseline"]

    undone = invoke("undo")
    assert undone.exit_code == 0, undone.output
    assert "Affected Contexts: 3" in undone.output
    for name in ("tree", "tree/child", "tree/child/deep"):
        assert [
            memory.content for memory in store.load_direct(name).memories.values()
        ] == [f"{name} baseline", f"{name} later"]


def test_recursive_discard_newer_remains_one_undoable_command_unit(isolated_store):
    store, root_uid, _member_uids = _recursive_baseline()
    for name in ("tree", "tree/child", "tree/child/deep"):
        assert invoke("add", f"{name} later", "--context", name).exit_code == 0

    reverted = invoke("revert", root_uid, "--discard-newer")

    assert reverted.exit_code == 0, reverted.output
    assert "Affected Contexts: 3" in reverted.output
    assert invoke("undo").exit_code == 0
    for name in ("tree", "tree/child", "tree/child/deep"):
        assert [
            memory.content for memory in store.load_direct(name).memories.values()
        ] == [f"{name} baseline", f"{name} later"]


def test_global_direct_uid_resolves_outside_the_current_context(isolated_store):
    assert invoke("init", "source").exit_code == 0
    assert invoke("add", "baseline").exit_code == 0
    checkpoint = invoke("checkpoint", "global baseline")
    assert checkpoint.exit_code == 0
    checkpoint_uid = re.search(r"\[([0-9a-f]{8})\]", checkpoint.output).group(1)
    assert invoke("add", "later").exit_code == 0
    assert invoke("init", "unrelated").exit_code == 0

    result = invoke("revert", checkpoint_uid, "--keep")

    assert result.exit_code == 0, result.output
    store = MemoryStore()
    assert [
        memory.content for memory in store.load_direct("source").memories.values()
    ] == ["baseline"]
    assert store.current_context_name() == "unrelated"


def test_legacy_receipt_only_set_uid_is_a_global_catalog_alias(isolated_store):
    assert invoke("init", "legacy").exit_code == 0
    assert invoke("init", "legacy/child").exit_code == 0
    store = MemoryStore()
    contexts = tuple(store.load_direct(name) for name in ("legacy", "legacy/child"))
    set_uid = str(uuid.uuid4())
    membership = [{"uid": context.uid, "name": context.name} for context in contexts]
    checkpoints = store.checkpoint_context_batch(
        ((context, context_record_digest(context)) for context in contexts),
        message="legacy recursive baseline",
        command="checkpoint",
        args={
            "checkpoint_set": {
                "version": 1,
                "uid": set_uid,
                "root": "legacy",
                "include_descendants": True,
            },
            "command_contexts": membership,
        },
        expected_context_catalog=tuple(store.list_context_names()),
    )
    for name in ("legacy", "legacy/child"):
        assert invoke("add", "later", "--context", name).exit_code == 0

    unit = resolve_checkpoint_unit(store, set_uid[:8])
    assert unit.canonical_uid == checkpoints[0].uid
    assert unit.legacy_aliases == (set_uid,)
    result = invoke("revert", set_uid[:8], "--keep")

    assert result.exit_code == 0, result.output
    assert not store.load_direct("legacy").memories
    assert not store.load_direct("legacy/child").memories


def test_recursive_revert_rolls_back_every_member_after_late_failure(
    isolated_store,
    monkeypatch,
):
    store, root_uid, _member_uids = _recursive_baseline()
    for name in ("tree", "tree/child", "tree/child/deep"):
        assert invoke("add", f"{name} later", "--context", name).exit_code == 0
    unit = resolve_checkpoint_unit(store, root_uid)
    before_contexts = {
        name: store.load_direct(name).to_dict()
        for name in ("tree", "tree/child", "tree/child/deep")
    }
    before_histories = {
        name: store.list_checkpoints(name)
        for name in ("tree", "tree/child", "tree/child/deep")
    }
    original = store._revert_locked
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected late member failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "_revert_locked", fail_second)

    with pytest.raises(OSError, match="injected late member failure"):
        store.revert_checkpoint_unit(unit)

    assert {
        name: store.load_direct(name).to_dict()
        for name in ("tree", "tree/child", "tree/child/deep")
    } == before_contexts
    assert {
        name: store.list_checkpoints(name)
        for name in ("tree", "tree/child", "tree/child/deep")
    } == before_histories


def test_recursive_revert_rejects_stale_member_before_any_publication(
    isolated_store,
):
    store, root_uid, _member_uids = _recursive_baseline()
    unit = resolve_checkpoint_unit(store, root_uid)
    assert invoke("add", "concurrent", "--context", "tree/child").exit_code == 0
    before_root = store.load_direct("tree").to_dict()
    before_root_history = store.list_checkpoints("tree")

    with pytest.raises(RuntimeError, match="changed after"):
        store.revert_checkpoint_unit(unit)

    assert store.load_direct("tree").to_dict() == before_root
    assert store.list_checkpoints("tree") == before_root_history


def test_recursive_revert_review_names_every_affected_checkpoint():
    review = revert_exact_command_review(
        context_name="tree/child",
        checkpoint_uid="22222222-2222-4222-8222-222222222222",
        keep_history=True,
        affected_checkpoints=(
            ("tree", "11111111-1111-4111-8111-111111111111"),
            ("tree/child", "22222222-2222-4222-8222-222222222222"),
        ),
    )

    assert review.effects == (
        "The complete checkpoint unit will restore 2 Contexts.",
        "Context 'tree' uses checkpoint [11111111].",
        "Context 'tree/child' uses checkpoint [22222222].",
        "Every currently visible checkpoint remains active.",
    )


def test_recursive_manifest_fails_closed_when_one_member_checkpoint_is_missing(
    isolated_store,
):
    store, root_uid, member_uids = _recursive_baseline()
    store._remove_checkpoint_uid_locked(
        "tree/child",
        member_uids["tree/child"],
    )

    with pytest.raises(CheckpointCatalogError, match="member .* is missing"):
        resolve_checkpoint_unit(store, root_uid)


def test_inherited_recursive_checkpoint_cannot_retarget_its_source_unit(
    isolated_store,
):
    store, root_uid, _member_uids = _recursive_baseline()
    store.set_current("tree")
    branched = invoke("branch", "experiment", "--recursive")
    assert branched.exit_code == 0, branched.output
    source_before = {
        name: store.load_direct(name).to_dict()
        for name in ("tree", "tree/child", "tree/child/deep")
    }
    branch_before = {
        name: store.load_direct(name).to_dict()
        for name in (
            "experiment",
            "experiment/child",
            "experiment/child/deep",
        )
    }

    result = invoke(
        "revert",
        root_uid[:8],
        "--context",
        "experiment",
        "--keep",
    )

    assert result.exit_code == 1
    assert "inherited recursive checkpoint" in result.stderr
    assert {
        name: store.load_direct(name).to_dict()
        for name in ("tree", "tree/child", "tree/child/deep")
    } == source_before
    assert {
        name: store.load_direct(name).to_dict()
        for name in (
            "experiment",
            "experiment/child",
            "experiment/child/deep",
        )
    } == branch_before
