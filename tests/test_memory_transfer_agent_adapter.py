"""Agent and registry parity for direct-Memory Copy and Move."""

from __future__ import annotations

import memcommit.ops as ops
from memcommit.api import MemCommitClient
from memcommit.interfaces.agent import (
    COPY_MEMORIES_AGENT_TOOL_NAME,
    MOVE_MEMORIES_AGENT_TOOL_NAME,
    MemoryTransferAgentAdapter,
    build_default_agent_tool_registry,
    copy_memories_agent_tool_schema,
    move_memories_agent_tool_schema,
)
from memcommit.store import MemoryStore


def _client(root):
    store = MemoryStore(root=root)
    source = ops.init("source")
    first = ops.add(source, "first")
    second = ops.add(source, "second")
    target = ops.init("target")
    store.save(source)
    store.save(target)
    store.set_current(target.name)
    return store, source, first, second, target, MemCommitClient(root=root)


def test_memory_transfer_agent_schemas_are_strict_and_separate():
    copy_schema = copy_memories_agent_tool_schema()
    move_schema = move_memories_agent_tool_schema()

    assert copy_schema["name"] == COPY_MEMORIES_AGENT_TOOL_NAME
    assert move_schema["name"] == MOVE_MEMORIES_AGENT_TOOL_NAME
    assert copy_schema["parameters"]["additionalProperties"] is False
    assert move_schema["parameters"]["additionalProperties"] is False
    assert "preserve_uids" in copy_schema["parameters"]["properties"]
    assert "retarget_links" in move_schema["parameters"]["properties"]
    assert "break_links" in move_schema["parameters"]["properties"]


def test_memory_transfer_agent_calls_public_facade_and_returns_typed_receipts(
    tmp_path,
):
    root = tmp_path / "store"
    store, source, first, second, target, client = _client(root)
    adapter = MemoryTransferAgentAdapter(client)

    copied = adapter.copy(
        {
            "version": 1,
            "memory_locators": [first.uid[:8]],
            "source_context": source.name,
            "into_context": target.name,
        }
    )
    moved = adapter.move(
        {
            "version": 1,
            "memory_locators": [second.uid[:8]],
            "source_context": source.name,
            "into_context": target.name,
        }
    )

    assert copied["ok"] is True
    assert copied["result"]["effect"] == "CHECKPOINTED_MEMORY_COPY"
    assert copied["result"]["uid_policy"] == "FRESH"
    assert copied["result"]["provider_used"] is False
    assert moved["ok"] is True
    assert moved["result"]["effect"] == "CHECKPOINTED_MEMORY_MOVE"
    assert moved["result"]["link_policy"] == "RETARGET"
    assert moved["result"]["provider_used"] is False
    assert list(store.load_direct(source.name).memories) == [first.uid]


def test_memory_transfer_agent_rejects_unknown_fields_and_conflicting_policies(
    tmp_path,
):
    root = tmp_path / "store"
    _store, source, first, _second, target, client = _client(root)
    adapter = MemoryTransferAgentAdapter(client)

    unknown = adapter.copy(
        {
            "version": 1,
            "memory_locators": [first.uid],
            "into_context": target.name,
            "unknown": True,
        }
    )
    conflicting = adapter.move(
        {
            "version": 1,
            "memory_locators": [first.uid],
            "source_context": source.name,
            "into_context": target.name,
            "retarget_links": True,
            "break_links": True,
        }
    )
    oversized = adapter.copy(
        {
            "version": 1,
            "memory_locators": [first.uid],
            "into_context": "x" * 1001,
        }
    )

    assert unknown["ok"] is False
    assert unknown["error"]["code"] == "invalid_request"
    assert conflicting["ok"] is False
    assert conflicting["error"]["code"] == "invalid_request"
    assert oversized["ok"] is False
    assert oversized["error"]["code"] == "invalid_request"


def test_default_registry_projects_both_memory_transfer_tools(tmp_path):
    root = tmp_path / "store"
    _store, _source, _first, _second, _target, client = _client(root)

    registry = build_default_agent_tool_registry(client)

    definitions = {
        definition.tool_schema["name"]: definition
        for definition in registry.tool_definitions()
    }
    assert definitions[COPY_MEMORIES_AGENT_TOOL_NAME].effect.read_only is False
    assert definitions[MOVE_MEMORIES_AGENT_TOOL_NAME].effect.read_only is False
