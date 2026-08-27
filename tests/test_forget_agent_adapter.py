"""Versioned agent contract for process-local reviewed Forget."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

from memcommit.adapters.python_api import ForgetProviderFailure, MemCommitClient
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.adapters.interfaces.agent.forget import (
    FORGET_AGENT_TOOL_NAME,
    ForgetAgentAdapter,
    forget_agent_tool_schema,
)
from memcommit.store import MemoryStore


class _ForgetProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        assert operation == "forget"
        assert output_schema is not None
        messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
        payload = json.loads(
            messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
        )
        keep_all = self.calls > 1
        candidates = []
        for index, source in enumerate(payload["source"]["memories"]):
            remove = index == 0 and not keep_all
            candidates.append(
                {
                    "source_memory_id": source["item_id"],
                    "decision": "DELETE" if remove else "KEEP",
                    "proposed_content": "" if remove else source["content"],
                    "rationale": "Reviewed against the complete instruction.",
                    "criterion_item_ids": ["k1"],
                }
            )
        return json.dumps(
            {
                "overview": "Reviewed every direct Source Memory.",
                "candidates": candidates,
            }
        )


def _source(root: Path, name: str = "forget/agent") -> tuple[MemoryStore, Context]:
    store = MemoryStore(root=root)
    context = Context(uid=str(uuid.uuid4()), name=name)
    context.add(
        Memory(
            uid=str(uuid.uuid4()),
            content="The old desk was beside the west entrance.",
        )
    )
    context.add(
        Memory(
            uid=str(uuid.uuid4()),
            content="The accessible entrance remains on the north side.",
        )
    )
    store.create_context(context)
    store.set_current(context.name)
    return store, context


def _adapter(root: Path) -> tuple[ForgetAgentAdapter, _ForgetProvider]:
    provider = _ForgetProvider()
    client = MemCommitClient(
        root=root,
        semantic_provider_factory=lambda: provider,
    )
    return ForgetAgentAdapter(client), provider


def _analyze(adapter: ForgetAgentAdapter, context_name: str | None = None):
    payload = {
        "version": 1,
        "kind": "analyze",
        "instruction": "Forget the old desk.",
    }
    if context_name is not None:
        payload["context_name"] = context_name
    return adapter.invoke(payload)


def test_analyze_select_and_noop_apply_require_exact_process_local_version(
    tmp_path,
) -> None:
    root = tmp_path / "store"
    store, source = _source(root)
    adapter, provider = _adapter(root)

    analyzed = _analyze(adapter)
    candidate = analyzed["result"]["candidates"][0]
    selected = adapter.invoke(
        {
            "version": 1,
            "kind": "select",
            "review_uid": analyzed["result"]["review_uid"],
            "expected_version": analyzed["result"]["version"],
            "candidate_uid": candidate["uid"],
            "selection": "KEEP",
        }
    )
    stale = adapter.invoke(
        {
            "version": 1,
            "kind": "apply",
            "review_uid": analyzed["result"]["review_uid"],
            "expected_version": analyzed["result"]["version"],
        }
    )
    applied = adapter.invoke(
        {
            "version": 1,
            "kind": "apply",
            "review_uid": selected["result"]["review_uid"],
            "expected_version": selected["result"]["version"],
        }
    )

    assert analyzed["ok"] is True
    assert analyzed["result"]["retention"] == "PROCESS_LOCAL"
    assert analyzed["result"]["effect"] == "NONE"
    assert analyzed["result"]["source"]["context"] == source.name
    assert candidate["recommendation"] == "DELETE"
    assert selected["result"]["version"] != analyzed["result"]["version"]
    assert selected["result"]["provider_used"] is False
    assert stale["error"]["code"] == "stale_review"
    assert applied["result"]["applied"] is False
    assert applied["result"]["effect"] == "NONE"
    assert provider.calls == 1
    assert tuple(store.load_direct(source.name).memories) == tuple(source.memories)
    assert store.list_checkpoints(source.name) == []


def test_revision_reuses_frozen_source_without_mutation(tmp_path) -> None:
    root = tmp_path / "store"
    store, source = _source(root)
    adapter, provider = _adapter(root)
    analyzed = _analyze(adapter, source.name)

    revised = adapter.invoke(
        {
            "version": 1,
            "kind": "revise",
            "review_uid": analyzed["result"]["review_uid"],
            "expected_version": analyzed["result"]["version"],
            "guidance": "Keep every current detail.",
        }
    )

    assert revised["ok"] is True
    assert revised["result"]["review_uid"] == analyzed["result"]["review_uid"]
    assert revised["result"]["version"] != analyzed["result"]["version"]
    assert revised["result"]["provider_used"] is True
    assert all(
        candidate["selected_action"] == "KEEP"
        for candidate in revised["result"]["candidates"]
    )
    assert provider.calls == 2
    assert tuple(store.load_direct(source.name).memories) == tuple(source.memories)
    assert store.list_checkpoints(source.name) == []


def test_apply_mutates_once_and_exact_retry_returns_cached_receipt(tmp_path) -> None:
    root = tmp_path / "store"
    store, source = _source(root)
    adapter, _provider = _adapter(root)
    analyzed = _analyze(adapter)
    request = {
        "version": 1,
        "kind": "apply",
        "review_uid": analyzed["result"]["review_uid"],
        "expected_version": analyzed["result"]["version"],
    }

    applied = adapter.invoke(request)
    replayed = adapter.invoke(request)
    post_apply_selection = adapter.invoke(
        {
            "version": 1,
            "kind": "select",
            "review_uid": analyzed["result"]["review_uid"],
            "expected_version": analyzed["result"]["version"],
            "candidate_uid": analyzed["result"]["candidates"][0]["uid"],
            "selection": "KEEP",
        }
    )

    assert applied["result"]["applied"] is True
    assert applied["result"]["removed_count"] == 1
    assert applied["result"]["effect"] == "SOURCE_CHECKPOINT"
    assert applied["result"]["recovered"] is False
    assert replayed["result"]["checkpoint_uid"] == applied["result"][
        "checkpoint_uid"
    ]
    assert replayed["result"]["recovered"] is True
    assert replayed["result"]["effect"] == "NONE"
    assert post_apply_selection["error"]["code"] == "review_applied"
    assert len(store.load_direct(source.name).memories) == 1
    assert [entry["command"] for entry in store.list_checkpoints(source.name)] == [
        "forget"
    ]


def test_review_is_unavailable_to_a_new_adapter_process_boundary(tmp_path) -> None:
    root = tmp_path / "store"
    _source(root)
    first, _provider = _adapter(root)
    analyzed = _analyze(first)
    second, _second_provider = _adapter(root)

    response = second.invoke(
        {
            "version": 1,
            "kind": "apply",
            "review_uid": analyzed["result"]["review_uid"],
            "expected_version": analyzed["result"]["version"],
        }
    )

    assert response["error"] == {
        "code": "review_unavailable",
        "message": (
            "The process-local Forget review is unavailable; analyze it again "
            "in this tool process."
        ),
        "retryable": False,
    }


def test_concurrent_source_change_fails_before_reviewed_removal(tmp_path) -> None:
    root = tmp_path / "store"
    store, source = _source(root)
    adapter, _provider = _adapter(root)
    analyzed = _analyze(adapter)
    concurrent = store.load_direct(source.name)
    extra = Memory(uid=str(uuid.uuid4()), content="A concurrent note survives.")
    concurrent.add(extra)
    store.save(
        concurrent,
        AutoCheckpoint(
            command="add",
            args={},
            description="Concurrent test change.",
        ),
    )

    response = adapter.invoke(
        {
            "version": 1,
            "kind": "apply",
            "review_uid": analyzed["result"]["review_uid"],
            "expected_version": analyzed["result"]["version"],
        }
    )

    assert response["error"] == {
        "code": "stale_source",
        "message": "The Forget Source changed.",
        "retryable": False,
    }
    assert set(source.memories) <= set(store.load_direct(source.name).memories)
    assert [entry["command"] for entry in store.list_checkpoints(source.name)].count(
        "forget"
    ) == 0


def test_invalid_input_and_provider_failure_are_bounded(tmp_path, monkeypatch) -> None:
    root = tmp_path / "missing-store"
    client = MemCommitClient(root=root)
    adapter = ForgetAgentAdapter(client)

    invalid = adapter.invoke(
        {"version": 1, "kind": "analyze", "instruction": ""}
    )
    assert invalid["error"]["code"] == "invalid_request"
    assert not root.exists()

    monkeypatch.setattr(
        client,
        "analyze_forget",
        lambda **_kwargs: (_ for _ in ()).throw(
            ForgetProviderFailure("private /host/provider-response")
        ),
    )
    failed = _analyze(adapter)

    assert failed["error"] == {
        "code": "provider_failure",
        "message": "The Forget provider failed.",
        "retryable": True,
    }
    assert "/host" not in json.dumps(failed)


def test_schema_is_fresh_and_declares_process_local_review_contract() -> None:
    first = forget_agent_tool_schema()
    first["name"] = "changed"
    current = forget_agent_tool_schema()

    assert current["name"] == FORGET_AGENT_TOOL_NAME
    assert current["parameters"]["additionalProperties"] is False
    assert current["parameters"]["properties"]["kind"]["enum"] == [
        "analyze",
        "select",
        "revise",
        "apply",
    ]
    assert "process-local" in current["description"]


def test_agent_adapter_depends_only_on_public_api_and_shared_contract() -> None:
    path = (
        Path(__file__).parents[1]
        / "src" / "memcommit"
        / "adapters"
        / "interfaces"
        / "agent"
        / "forget.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    assert "memcommit.adapters.python_api" in imported
    assert "memcommit.adapters.interfaces.agent.contract" in imported
    forbidden = (
        "memcommit.commands",
        "memcommit.application.operations",
        "memcommit.infrastructure",
        "memcommit.store",
        "memcommit.forget_application",
        "typer",
        "prompt_toolkit",
        "mcp",
    )
    assert not any(
        name == prefix or name.startswith(f"{prefix}.")
        for name in imported
        for prefix in forbidden
    )
