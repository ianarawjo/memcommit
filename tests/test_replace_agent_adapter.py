"""Versioned machine contract tests for deterministic Replace."""

from __future__ import annotations

import memcommit.application.ops as ops
from memcommit.adapters.python_api import MemCommitClient
from memcommit.adapters.interfaces.agent.replace import (
    REPLACE_AGENT_TOOL_NAME,
    ReplaceAgentAdapter,
    replace_agent_tool_schema,
)
from memcommit.store import MemoryStore


def _adapter(tmp_path):
    root = tmp_path / "store"
    store = MemoryStore(root=root)
    context = ops.init("replace/source")
    ops.add(context, "needle and needle")
    store.save(context)
    store.set_current(context.name)
    return ReplaceAgentAdapter(MemCommitClient(root=root)), store


def _request(kind: str, **extra):
    return {
        "version": 1,
        "kind": kind,
        "pattern": "needle",
        "replacement": "thread",
        **extra,
    }


def test_agent_plan_then_exact_digest_apply(tmp_path) -> None:
    adapter, store = _adapter(tmp_path)

    planned = adapter.invoke(_request("plan"))

    assert planned["ok"] is True
    assert planned["result"]["effect"] == "NONE"
    assert planned["result"]["provider_used"] is False
    assert planned["result"]["occurrence_count"] == 2
    assert store.list_checkpoints("replace/source") == []

    applied = adapter.invoke(
        _request(
            "apply",
            expected_plan_digest=planned["result"]["plan_digest"],
        )
    )

    assert applied["ok"] is True
    assert applied["result"]["effect"] == "CONTEXTS_CHANGED"
    assert applied["result"]["provider_used"] is False
    assert len(applied["result"]["checkpoints"]) == 1
    assert [
        memory.content
        for memory in store.load_direct("replace/source").memories.values()
    ] == ["thread and thread"]


def test_agent_apply_replans_and_rejects_stale_digest(tmp_path) -> None:
    adapter, store = _adapter(tmp_path)
    planned = adapter.invoke(_request("plan"))
    current = store.load_direct("replace/source")
    current.add("later needle")
    store.save(current)

    response = adapter.invoke(
        _request(
            "apply",
            expected_plan_digest=planned["result"]["plan_digest"],
        )
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "stale_plan"
    assert response["error"]["retryable"] is True
    assert store.list_checkpoints("replace/source") == []


def test_agent_schema_requires_digest_only_for_apply() -> None:
    schema = replace_agent_tool_schema()

    assert schema["name"] == REPLACE_AGENT_TOOL_NAME
    assert schema["parameters"]["additionalProperties"] is False
    assert schema["parameters"]["allOf"][0]["then"] == {
        "required": ["expected_plan_digest"]
    }
    assert schema["parameters"]["allOf"][0]["else"] == {
        "not": {"required": ["expected_plan_digest"]}
    }


def test_agent_rejects_unknown_or_malformed_fields(tmp_path) -> None:
    adapter, _store = _adapter(tmp_path)

    missing_digest = adapter.invoke(_request("apply"))
    extra = adapter.invoke(_request("plan", surprise=True))

    assert missing_digest["error"]["code"] == "invalid_request"
    assert extra["error"]["code"] == "invalid_request"
