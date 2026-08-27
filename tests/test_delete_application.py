"""Focused boundary tests for the unified Delete operation."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

import memcommit.application.ops as ops
from memcommit.adapters.python_api import (
    DeleteInputError,
    MemCommitClient,
)
from memcommit.context import AutoCheckpoint
from memcommit.delete_application import (
    ContextDeleteRequest,
    DeleteStalePlanError,
    DirectItemDeleteRequest,
    apply_context_delete,
    prepare_context_delete,
    run_direct_item_delete,
)
from memcommit.delete_runtime import MemoryStoreDeletePort
from memcommit.adapters.interfaces.agent import (
    APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME,
    PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME,
    REMOVE_ITEM_AGENT_TOOL_NAME,
    build_default_agent_tool_registry,
)
from memcommit.adapters.interfaces.mcp import McpRegistryProjection
from memcommit.store import MemoryStore


def _store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(root=tmp_path / "store")


def test_direct_item_delete_is_one_checkpointed_undoable_effect(tmp_path):
    store = _store(tmp_path)
    context = ops.init("owner")
    memory = ops.add(context, "remove me")
    store.create_context(context)
    store.set_current(context.name)
    port = MemoryStoreDeletePort.capture(store)

    result = run_direct_item_delete(
        DirectItemDeleteRequest(selector=memory.uid[:8]),
        port=port,
    )

    assert result.context_name == "owner"
    assert result.item.uid == memory.uid
    assert result.item.kind == "MEMORY"
    assert memory.uid not in store.load_direct("owner").memories
    [checkpoint] = store.list_checkpoints("owner")
    assert checkpoint["uid"] == result.checkpoint_uid
    assert checkpoint["command"] == "remove"


def test_public_bare_item_selector_uses_the_shared_cross_context_locator(tmp_path):
    root = tmp_path / "store"
    store = MemoryStore(root=root)
    owner = ops.init("owner")
    memory = ops.add(owner, "remove me outside current")
    store.create_context(owner)
    store.create_context(ops.init("current"))
    store.set_current("current")

    receipt = MemCommitClient(root=root).remove_item(memory.uid[:8])

    assert receipt.context_name == "owner"
    assert receipt.item.uid == memory.uid
    assert memory.uid not in store.load_direct("owner").memories
    assert store.current_context_name() == "current"


def test_context_delete_plan_is_read_only_and_preserves_descendants(tmp_path):
    store = _store(tmp_path)
    parent = ops.init("project")
    child = ops.init("project/child")
    store.create_context(parent)
    store.create_context(child)
    port = MemoryStoreDeletePort(store, current_name="project/child")

    plan = prepare_context_delete(
        ContextDeleteRequest(".."),
        port=port,
    )

    assert plan.context_name == "project"
    assert plan.checkpoint_history_deleted is True
    assert plan.restorable_snapshot_retained is False
    assert store.context_exists("project")
    result = apply_context_delete(plan, port=port)
    assert result.status == "APPLIED"
    assert result.descendants_preserved is True
    assert not store.context_exists("project")
    assert store.context_exists("project/child")


def test_context_delete_rejects_a_changed_record_before_publication(tmp_path):
    store = _store(tmp_path)
    context = ops.init("victim")
    store.create_context(context)
    port = MemoryStoreDeletePort.capture(store)
    plan = prepare_context_delete(ContextDeleteRequest("victim"), port=port)
    changed = store.load_direct("victim")
    ops.add(changed, "changed after review")
    store.save(
        changed,
        AutoCheckpoint(command="add", args={}, description="changed"),
    )

    with pytest.raises(DeleteStalePlanError, match="changed after deletion was reviewed"):
        apply_context_delete(plan, port=port)

    assert store.context_exists("victim")


def test_public_delete_plan_is_client_bound_and_tamper_evident(tmp_path):
    root = tmp_path / "store"
    store = MemoryStore(root=root)
    store.create_context(ops.init("victim"))
    client = MemCommitClient(root=root)
    other = MemCommitClient(root=root)
    plan = client.plan_context_delete("victim")

    with pytest.raises(DeleteInputError, match="does not belong"):
        other.apply_context_delete(plan)
    with pytest.raises(DeleteInputError, match="modified"):
        client.apply_context_delete(replace(plan, plan_digest="0" * 64))

    assert store.context_exists("victim")
    receipt = client.apply_context_delete(plan)
    assert receipt.status == "APPLIED"
    assert receipt.undoable is False


def test_public_context_delete_reports_a_committed_cleanup_warning(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "store"
    store = MemoryStore(root=root)
    store.create_context(ops.init("victim"))
    store.set_current("victim")
    client = MemCommitClient(root=root)
    plan = client.plan_context_delete("victim")

    def fail_state_write(self, state):
        raise OSError("injected state cleanup failure")

    monkeypatch.setattr(MemoryStore, "_write_state", fail_state_write)

    receipt = client.apply_context_delete(plan)

    assert receipt.status == "APPLIED_WITH_CLEANUP_WARNING"
    assert "deletion committed" in receipt.cleanup_warning
    assert not store.context_exists("victim")


def test_agent_and_mcp_split_delete_by_effect_and_require_exact_plan(tmp_path):
    root = tmp_path / "store"
    store = MemoryStore(root=root)
    owner = ops.init("owner")
    memory = ops.add(owner, "remove me")
    store.create_context(owner)
    store.create_context(ops.init("victim"))
    registry = build_default_agent_tool_registry(MemCommitClient(root=root))
    projection = McpRegistryProjection(registry)
    tools = {tool.name: tool for tool in projection.list_tools()}

    assert tools[REMOVE_ITEM_AGENT_TOOL_NAME].to_dict()["annotations"] == {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
    assert tools[PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME].to_dict()["annotations"] == {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    assert tools[APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME].to_dict()["annotations"] == {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }

    removed = registry.invoke(
        REMOVE_ITEM_AGENT_TOOL_NAME,
        {"version": 1, "selector": memory.uid, "context_name": "owner"},
    )
    assert removed["ok"] is True
    assert removed["result"]["undoable"] is True

    planned = registry.invoke(
        PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME,
        {"version": 1, "context_name": "victim"},
    )
    assert planned["ok"] is True
    assert store.context_exists("victim")
    rejected = registry.invoke(
        APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME,
        {
            "version": 1,
            "context_name": "victim",
            "expected_plan_digest": "0" * 64,
        },
    )
    assert rejected["error"]["code"] == "stale_plan"
    assert rejected["error"]["retryable"] is True
    applied = registry.invoke(
        APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME,
        {
            "version": 1,
            "context_name": "victim",
            "expected_plan_digest": planned["result"]["plan_digest"],
        },
    )
    assert applied["ok"] is True
    assert applied["result"]["undoable"] is False
    assert not store.context_exists("victim")


@pytest.mark.parametrize(
    "path",
    (
        "src/memcommit/application/operations/delete/application.py",
        "src/memcommit/application/operations/delete/runtime.py",
    ),
)
def test_delete_boundary_has_no_terminal_dependencies(path):
    root = Path(__file__).parents[1]
    tree = ast.parse((root / path).read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    assert not any(
        name == prefix or name.startswith(f"{prefix}.")
        for name in imports
        for prefix in (
            "memcommit.commands",
            "memcommit.adapters.interfaces",
            "prompt_toolkit",
            "typer",
        )
    )
