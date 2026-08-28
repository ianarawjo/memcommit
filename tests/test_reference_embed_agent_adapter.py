"""Machine contracts for snapshot Reference and live Embed."""

from __future__ import annotations

import json

from memcommit.adapters.python_api import (
    ContextReferenceResult,
    EmbeddedContextResult,
    EmbeddedMemoryResult,
    EmbedPlacementResult,
    MemCommitClient,
    MemoryReferenceResult,
)
from memcommit.adapters.agent.embed import (
    EMBED_AGENT_TOOL_NAME,
    EmbedAgentAdapter,
    embed_agent_tool_schema,
)
from memcommit.adapters.agent.reference import (
    REFERENCE_AGENT_TOOL_NAME,
    ReferenceAgentAdapter,
    reference_agent_tool_schema,
)


def _client(tmp_path) -> MemCommitClient:
    return MemCommitClient(root=tmp_path / "store")


def test_reference_agent_is_explicit_snapshot_and_calls_public_client_once(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    calls: list[dict[str, object]] = []

    def reference_memory(**kwargs):
        calls.append(kwargs)
        return MemoryReferenceResult(
            reference_uid="reference-uid",
            source_name="source",
            source_uid="source-uid",
            memory_uid="memory-uid",
            memory_content_sha256="sha256",
            into_name="target",
            into_uid="target-uid",
            checkpoint_uid="checkpoint-uid",
        )

    monkeypatch.setattr(client, "reference_memory", reference_memory)
    response = ReferenceAgentAdapter(client).invoke(
        {
            "version": 2,
            "kind": "memory",
            "memory_selector": "memory",
            "source_context": "source",
            "into_context": "target",
        }
    )

    assert calls == [
        {
            "memory_selector": "memory",
            "source_context": "source",
            "into_context": "target",
        }
    ]
    assert response["ok"] is True
    assert response["result"]["mode"] == "SNAPSHOT"
    assert response["result"]["memory_content_sha256"] == "sha256"
    json.dumps(response)


def test_reference_agent_routes_context_snapshot_without_operand_guessing(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    calls: list[dict[str, object]] = []

    def reference_context(**kwargs):
        calls.append(kwargs)
        return ContextReferenceResult(
            reference_uid="context-reference-uid",
            source_name="source",
            source_uid="source-uid",
            snapshot_content_sha256="snapshot-sha256",
            include_descendants=True,
            follow_embeds=True,
            context_count=3,
            into_name="target",
            into_uid="target-uid",
            checkpoint_uid="checkpoint-uid",
        )

    monkeypatch.setattr(client, "reference_context", reference_context)
    response = ReferenceAgentAdapter(client).invoke(
        {
            "version": 2,
            "kind": "context",
            "source_context": "source",
            "into_context": "target",
            "recursive": True,
        }
    )

    assert calls == [
        {
            "source_context": "source",
            "into_context": "target",
            "recursive": True,
        }
    ]
    assert response["ok"] is True
    assert response["result"]["context_count"] == 3
    assert response["result"]["follow_embeds"] is True


def test_embed_agent_uses_tagged_kind_instead_of_guessing_from_operand(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    calls: list[tuple[str, dict[str, object]]] = []
    placement = EmbedPlacementResult(0, None, "next-uid")

    def embed_memory(**kwargs):
        calls.append(("memory", kwargs))
        return EmbeddedMemoryResult(
            embed_uid="embed-uid",
            source_name="source",
            source_uid="source-uid",
            memory_uid="same-text-as-a-context-name",
            into_name="target",
            into_uid="target-uid",
            placement=placement,
            checkpoint_uid="checkpoint-uid",
        )

    def embed_context(**kwargs):
        calls.append(("context", kwargs))
        return EmbeddedContextResult(
            child_name="same-text-as-a-memory-selector",
            child_uid="child-uid",
            into_name="target",
            into_uid="target-uid",
            placement=placement,
            checkpoint_uid="checkpoint-2",
        )

    monkeypatch.setattr(client, "embed_memory", embed_memory)
    monkeypatch.setattr(client, "embed_context", embed_context)
    adapter = EmbedAgentAdapter(client)

    memory = adapter.invoke(
        {
            "version": 1,
            "kind": "memory",
            "memory_selector": "same-text-as-a-context-name",
            "source_context": "source",
            "into_context": "target",
        }
    )
    context = adapter.invoke(
        {
            "version": 1,
            "kind": "context",
            "child_context": "same-text-as-a-memory-selector",
            "into_context": "target",
        }
    )

    assert [call[0] for call in calls] == ["memory", "context"]
    assert memory["result"]["mode"] == "LIVE"
    assert context["result"]["mode"] == "LIVE"
    assert memory["result"]["placement"]["next_uid"] == "next-uid"
    json.dumps([memory, context])


def test_agent_schemas_are_fresh_strict_and_expose_distinct_semantics():
    first_reference = reference_agent_tool_schema()
    second_reference = reference_agent_tool_schema()
    first_embed = embed_agent_tool_schema()
    second_embed = embed_agent_tool_schema()

    assert first_reference["name"] == REFERENCE_AGENT_TOOL_NAME
    assert [
        branch["properties"]["kind"]["const"]
        for branch in first_reference["parameters"]["oneOf"]
    ] == ["memory", "context"]
    assert first_embed["name"] == EMBED_AGENT_TOOL_NAME
    assert [branch["properties"]["kind"]["const"] for branch in first_embed["parameters"]["oneOf"]] == [
        "memory",
        "context",
    ]
    first_reference["parameters"]["oneOf"].clear()
    first_embed["parameters"]["oneOf"].clear()
    assert len(second_reference["parameters"]["oneOf"]) == 2
    assert len(second_embed["parameters"]["oneOf"]) == 2


def test_invalid_kind_never_calls_public_client(tmp_path, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setattr(
        client,
        "embed_memory",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid request reached the public client")
        ),
    )

    response = EmbedAgentAdapter(client).invoke(
        {"version": 1, "kind": "snapshot", "into_context": "target"}
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_request"
