"""Atomic lexical-scope contracts for immediate recursive Dedun."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.application.authority.access import resolve_context_access
from memcommit.adapters.console.entrypoint import app
from memcommit.application.retained_history.command_history import build_command_stacks
from memcommit.core.context import MemoryRef
from memcommit.application.operations.dedun.scope import (
    apply_recursive_dedun_scope,
    freeze_recursive_dedun_scope,
    prepare_recursive_dedun_scope,
)
from memcommit.application.operations.dedun.application import DedunConflictError
from memcommit.application.operations.dedun.runtime import MemoryStoreDedunPort
from memcommit.application.reviewing.quality.findings import DuplicateReport, FindingsError
from memcommit.application.reviewing.quality.redundancy_scope import analyze_independent_redundancy_scope
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)
QUALITY_MARKER = "QUALITY FIND PAYLOAD:\n"


class SemanticGroupProvider:
    def __init__(self) -> None:
        self.context_names: list[str] = []

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        assert operation == "find_duplicates"
        payload = json.loads(prompt.split(QUALITY_MARKER, 1)[1])
        memories = payload["memories"]
        self.context_names.append(memories[0]["context_name"])
        return json.dumps(
            {
                "findings": [
                    {
                        "candidate_ids": [
                            memory["candidate_id"] for memory in memories
                        ],
                        "relation": "SEMANTIC_EQUIVALENT",
                        "reason": "Both Memories state the same local rule.",
                    }
                ]
            }
        )


def _fixture(store: MemoryStore):
    root = ops.init("dedun/tree")
    root_first = ops.add(root, "root duplicate")
    root_later = ops.add(root, "root duplicate")
    child = ops.init("dedun/tree/child")
    child_first = ops.add(child, "child duplicate")
    child_later = ops.add(child, "child duplicate")
    sibling = ops.init("dedun/sibling")
    sibling_memory = ops.add(sibling, "root duplicate")
    for context in (root, child, sibling):
        store.save(context)
    store.set_current(root.name)
    return (
        root,
        root_first,
        root_later,
        child,
        child_first,
        child_later,
        sibling,
        sibling_memory,
    )


def _prepared(store: MemoryStore, root_name: str):
    access = resolve_context_access(
        store,
        root_name,
        current_name=root_name,
        required_permission="READ",
    )
    frozen = freeze_recursive_dedun_scope(store, access)
    analysis = analyze_independent_redundancy_scope(
        frozen.source,
        lambda: (_ for _ in ()).throw(
            AssertionError("exact-only frames must not connect a provider")
        ),
    )
    prepared = prepare_recursive_dedun_scope(
        frozen,
        analysis,
        port=MemoryStoreDedunPort(
            store,
            current_name=root_name,
            allow_grants=False,
        ),
    )
    return prepared


def test_cli_recursive_dedun_is_one_atomic_undoable_command(isolated_store):
    store = MemoryStore()
    (
        root,
        root_first,
        root_later,
        child,
        child_first,
        child_later,
        sibling,
        sibling_memory,
    ) = _fixture(store)

    result = runner.invoke(app, ["dedun", root.name, "-r"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "absorbed 2 redundant direct item(s) in 2/2 Context(s)" in result.output
    assert f"CONTEXT · {root.name}" in result.output
    assert f"CONTEXT · {child.name}" in result.output
    assert "recovery: mem undo (one command unit)" in result.output
    assert tuple(store.load_direct(root.name).memories) == (root_first.uid,)
    assert tuple(store.load_direct(child.name).memories) == (child_first.uid,)
    assert tuple(store.load_direct(sibling.name).memories) == (sibling_memory.uid,)

    stacks = build_command_stacks(store)
    assert stacks.undo[-1].uid.startswith("dedun:")
    assert {change.context_name for change in stacks.undo[-1].changes} == {
        root.name,
        child.name,
    }
    reviewed = runner.invoke(
        app,
        ["review", "dedun", "--receipt", stacks.undo[-1].changes[0].checkpoint_uid],
    )
    assert reviewed.exit_code == 0, reviewed.output + reviewed.stderr
    assert "SURVIVOR" in reviewed.output
    assert "ABSORB" in reviewed.output

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 0, undone.output
    assert f"mem dedun {root.name} --recursive" in undone.output
    assert tuple(store.load_direct(root.name).memories) == (
        root_first.uid,
        root_later.uid,
    )
    assert tuple(store.load_direct(child.name).memories) == (
        child_first.uid,
        child_later.uid,
    )


def test_recursive_dedun_rolls_back_all_contexts_after_write_failure(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root, *_rest = _fixture(store)
    prepared = _prepared(store, root.name)
    before = {
        name: store._context_file(name).read_bytes()
        for name in store.list_context_names()
    }
    original_save = store._save_locked
    calls = 0

    def fail_second_write(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated recursive Dedun write failure")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(store, "_save_locked", fail_second_write)

    with pytest.raises(OSError, match="simulated recursive Dedun write failure"):
        apply_recursive_dedun_scope(store, prepared)

    assert {
        name: store._context_file(name).read_bytes()
        for name in store.list_context_names()
    } == before
    assert all(
        store.list_checkpoints(name) == [] for name in store.list_context_names()
    )


def test_recursive_dedun_applies_semantic_groups_per_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("semantic-dedun")
    root_first = ops.add(root, "The west door closes at ten.")
    ops.add(root, "West-door access ends at 22:00.")
    child = ops.init("semantic-dedun/child")
    child_first = ops.add(child, "Call the desk before arrival.")
    ops.add(child, "Phone the desk prior to arriving.")
    for context in (root, child):
        store.save(context)
    store.set_current(root.name)
    provider = SemanticGroupProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_duplicates.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["dedun", root.name, "--recursive"])

    assert result.exit_code == 0, result.output + result.stderr
    assert provider.context_names == [root.name, child.name]
    assert tuple(store.load_direct(root.name).memories) == (root_first.uid,)
    assert tuple(store.load_direct(child.name).memories) == (child_first.uid,)


def test_recursive_dedun_blocks_inbound_reference_before_any_write(isolated_store):
    store = MemoryStore()
    (
        root,
        root_first,
        root_later,
        child,
        child_first,
        child_later,
        sibling,
        _sibling_memory,
    ) = _fixture(store)
    sibling.add(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=child.uid,
            target_context_name=child.name,
            target_memory_uid=child_later.uid,
        )
    )
    store.save(sibling)
    prepared = _prepared(store, root.name)

    with pytest.raises(DedunConflictError, match="inbound references"):
        apply_recursive_dedun_scope(store, prepared)

    assert tuple(store.load_direct(root.name).memories) == (
        root_first.uid,
        root_later.uid,
    )
    assert tuple(store.load_direct(child.name).memories) == (
        child_first.uid,
        child_later.uid,
    )
    assert store.list_checkpoints(root.name) == []
    assert store.list_checkpoints(child.name) == []


def test_recursive_dedun_later_analysis_failure_publishes_no_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root, *_rest = _fixture(store)
    calls = 0

    def analyze(context, _provider_factory, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise FindingsError("second semantic frame failed")
        return DuplicateReport(memory_count=len(context.memories), findings=())

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_duplicates.command.ops.find_redundancies",
        analyze,
    )

    result = runner.invoke(app, ["dedun", root.name, "--recursive"])

    assert result.exit_code == 1
    assert calls == 2
    assert "second semantic frame failed" in result.stderr
    assert all(
        store.list_checkpoints(name) == [] for name in store.list_context_names()
    )


def test_recursive_dedun_rejects_namespace_drift_before_apply(isolated_store):
    store = MemoryStore()
    root, *_rest = _fixture(store)
    prepared = _prepared(store, root.name)
    added = ops.init("dedun/tree/new-child")
    store.save(added)

    with pytest.raises(DedunConflictError, match="namespace changed"):
        apply_recursive_dedun_scope(store, prepared)

    assert all(
        store.list_checkpoints(name) == [] for name in store.list_context_names()
    )


def test_recursive_dedun_rejects_mixed_scope_presets_without_mutation(
    isolated_store,
):
    store = MemoryStore()
    root, *_rest = _fixture(store)

    result = runner.invoke(app, ["dedun", root.name, "-d", "-r"])

    assert result.exit_code == 2
    assert "either --direct/-d or --recursive/-r" in result.stderr
    assert all(
        store.list_checkpoints(name) == [] for name in store.list_context_names()
    )
