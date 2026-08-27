"""Host-neutral discovery and real execution tests for agent tools."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import memcommit.application.ops as ops
from memcommit.adapters.python_api import MemCommitClient
from memcommit.adapters.interfaces.agent import (
    ADD_AGENT_TOOL_NAME,
    APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME,
    ATOMIZE_AGENT_TOOL_NAME,
    ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
    COMPARE_AGENT_TOOL_NAME,
    COPY_MEMORIES_AGENT_TOOL_NAME,
    DEDUP_AGENT_TOOL_NAME,
    EMBED_AGENT_TOOL_NAME,
    MELD_AGENT_TOOL_NAME,
    MOVE_MEMORIES_AGENT_TOOL_NAME,
    DISTILL_AGENT_TOOL_NAME,
    ELABORATE_AGENT_TOOL_NAME,
    FIT_AGENT_TOOL_NAME,
    FORGET_AGENT_TOOL_NAME,
    FIND_AGENT_TOOL_NAME,
    QUALITY_FIND_AGENT_TOOL_NAME,
    HELP_AGENT_TOOL_NAME,
    PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME,
    QUERY_AGENT_TOOL_NAME,
    QUERY_AGENT_CONTRACT_VERSION,
    REFERENCE_AGENT_TOOL_NAME,
    REPLACE_AGENT_TOOL_NAME,
    REMOVE_ITEM_AGENT_TOOL_NAME,
    RESOLVE_AGENT_TOOL_NAME,
    SEARCH_AGENT_TOOL_NAME,
    SHOW_AGENT_TOOL_NAME,
    AgentToolBinding,
    AgentToolRegistrationError,
    AgentToolRegistry,
    build_default_agent_tool_registry,
)
from memcommit.persistence.store import MemoryStore


class _RegistryQueryProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "ordinary query"
        assert output_schema is not None
        payload = json.loads(prompt.split("ORDINARY QUERY PAYLOAD:\n", 1)[1])
        aliases = [item["alias"] for item in payload["complete_frozen_corpus"]]
        return json.dumps(
            {
                "outcome_kind": "ANSWER",
                "blocks": [
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "The registry reached the added Memory.",
                        "source_aliases": aliases,
                    }
                ],
            }
        )


def _binding(
    name="example_tool",
    *,
    schema_factory=None,
    handler=None,
) -> AgentToolBinding:
    return AgentToolBinding(
        name=name,
        schema_factory=schema_factory
        or (
            lambda: {
                "name": name,
                "description": "Example.",
                "parameters": {"type": "object"},
            }
        ),
        handler=handler or (lambda payload: {"ok": True, "payload": payload}),
    )


def test_default_registry_discovers_fresh_frozen_shipped_schemas(tmp_path):
    registry = build_default_agent_tool_registry(
        MemCommitClient(root=tmp_path / "store")
    )

    assert registry.tool_names == (
        HELP_AGENT_TOOL_NAME,
        SHOW_AGENT_TOOL_NAME,
        FIND_AGENT_TOOL_NAME,
        REPLACE_AGENT_TOOL_NAME,
        REMOVE_ITEM_AGENT_TOOL_NAME,
        PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME,
        APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME,
        SEARCH_AGENT_TOOL_NAME,
        QUERY_AGENT_TOOL_NAME,
        QUALITY_FIND_AGENT_TOOL_NAME,
        ADD_AGENT_TOOL_NAME,
        COPY_MEMORIES_AGENT_TOOL_NAME,
        MOVE_MEMORIES_AGENT_TOOL_NAME,
        REFERENCE_AGENT_TOOL_NAME,
        EMBED_AGENT_TOOL_NAME,
        COMPARE_AGENT_TOOL_NAME,
        MELD_AGENT_TOOL_NAME,
        ATOMIZE_AGENT_TOOL_NAME,
        ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
        DISTILL_AGENT_TOOL_NAME,
        ELABORATE_AGENT_TOOL_NAME,
        FIT_AGENT_TOOL_NAME,
        FORGET_AGENT_TOOL_NAME,
        RESOLVE_AGENT_TOOL_NAME,
        DEDUP_AGENT_TOOL_NAME,
    )
    first = registry.tool_schemas()
    second = registry.tool_schemas()
    assert first is not second
    assert [schema["name"] for schema in first] == list(registry.tool_names)
    assert all("use_when" not in schema for schema in first)
    assert all(
        isinstance(definition.use_when, str) and definition.use_when.strip()
        for definition in registry.tool_definitions()
    )
    definitions_by_name = {
        definition.tool_schema["name"]: definition
        for definition in registry.tool_definitions()
    }
    assert [
        detail.id for detail in definitions_by_name[ADD_AGENT_TOOL_NAME].help_details
    ] == ["copy-or-link"]
    assert [
        detail.id for detail in definitions_by_name[QUERY_AGENT_TOOL_NAME].help_details
    ] == ["query-only-access"]
    assert definitions_by_name[REFERENCE_AGENT_TOOL_NAME].help_details == ()
    json.dumps(first)

    first[0]["name"] = "changed"
    add_index = registry.tool_names.index(ADD_AGENT_TOOL_NAME)
    first[add_index]["parameters"]["required"].clear()
    definitions = registry.tool_definitions()
    definitions[0].tool_schema["name"] = "changed-definition"
    third = registry.tool_schemas()
    assert third[0]["name"] == HELP_AGENT_TOOL_NAME
    assert third[add_index]["parameters"]["required"] == [
        "version",
        "kind",
        "contents",
    ]
    assert registry.tool_definitions()[0].tool_schema["name"] == HELP_AGENT_TOOL_NAME


def test_default_registry_help_is_a_provider_free_entrypoint(tmp_path):
    root = tmp_path / "missing-store"
    registry = build_default_agent_tool_registry(MemCommitClient(root=root))

    response = registry.invoke(
        HELP_AGENT_TOOL_NAME,
        {"version": 1, "kind": "describe", "operation": "query"},
    )

    assert response["ok"] is True
    assert response["result"]["operation"]["name"] == "query"
    assert response["result"]["effect"] == "NONE"
    assert not root.exists()


def test_registration_freezes_schema_factory_once():
    schema = {
        "name": "example_tool",
        "description": "Original.",
        "parameters": {"type": "object"},
    }
    calls = 0

    def schema_factory():
        nonlocal calls
        calls += 1
        return schema

    registry = AgentToolRegistry((_binding(schema_factory=schema_factory),))
    schema["description"] = "Changed after registration."

    assert calls == 1
    assert registry.tool_schemas()[0]["description"] == "Original."
    assert registry.tool_schemas()[0]["description"] == "Original."
    assert calls == 1


def test_registration_freezes_explicit_use_when_for_discovery():
    binding = AgentToolBinding(
        name="example_tool",
        schema_factory=lambda: {
            "name": "example_tool",
            "description": "Example.",
            "parameters": {"type": "object"},
        },
        handler=lambda payload: {"ok": True, "payload": payload},
        use_when="Using the example operation.",
    )

    registry = AgentToolRegistry((binding,))

    [definition] = registry.tool_definitions()
    assert definition.use_when == "Using the example operation."
    assert definition.tool_schema == registry.tool_schemas()[0]
    assert "use_when" not in definition.tool_schema


@pytest.mark.parametrize(
    ("bindings", "message"),
    [
        ((_binding(name=""),), "nonblank"),
        ((_binding(), _binding()), "more than once"),
        (
            (
                _binding(
                    schema_factory=lambda: {
                        "name": "different_tool",
                        "parameters": {"type": "object"},
                    }
                ),
            ),
            "must match",
        ),
        (
            (
                _binding(
                    schema_factory=lambda: {
                        "name": "example_tool",
                        "not_json": object(),
                    }
                ),
            ),
            "JSON-safe",
        ),
        (
            (
                AgentToolBinding(
                    name="example_tool",
                    schema_factory=lambda: {
                        "name": "example_tool",
                        "description": "Example.",
                        "parameters": {"type": "object"},
                        "use_when": "Schema guidance.",
                    },
                    handler=lambda payload: {"ok": True, "payload": payload},
                    use_when="Binding guidance.",
                ),
            ),
            "use_when differ",
        ),
        (
            (
                AgentToolBinding(
                    name="example_tool",
                    schema_factory=lambda: {
                        "name": "example_tool",
                        "description": "Example.",
                        "parameters": {"type": "object"},
                    },
                    handler=lambda payload: {"ok": True, "payload": payload},
                    use_when=" ",
                ),
            ),
            "use_when must be nonblank",
        ),
        (
            (
                AgentToolBinding(
                    name="example_tool",
                    schema_factory=lambda: {
                        "name": "example_tool",
                        "description": "Example.",
                        "parameters": {"type": "object"},
                    },
                    handler=lambda payload: {"ok": True, "payload": payload},
                    help_details=[],  # type: ignore[arg-type]
                ),
            ),
            "help_details must be a typed tuple",
        ),
    ],
)
def test_invalid_or_duplicate_registrations_fail_before_host_start(bindings, message):
    with pytest.raises(AgentToolRegistrationError, match=message):
        AgentToolRegistry(bindings)


@pytest.mark.parametrize("tool_name", [None, "", " \n"])
def test_invalid_tool_name_is_bounded_and_never_opens_store(tmp_path, tool_name):
    root = tmp_path / "missing-store"
    registry = build_default_agent_tool_registry(MemCommitClient(root=root))

    response = registry.invoke(tool_name, {"untrusted": True})

    assert response == {
        "version": 1,
        "ok": False,
        "kind": None,
        "error": {
            "code": "invalid_tool_name",
            "message": "Agent tool name must be nonblank text.",
            "retryable": False,
        },
    }
    assert not root.exists()


def test_unknown_tool_is_stable_and_never_opens_store(tmp_path):
    root = tmp_path / "missing-store"
    registry = build_default_agent_tool_registry(MemCommitClient(root=root))

    response = registry.invoke("untrusted\nunknown", {"untrusted": True})

    assert response["error"] == {
        "code": "unknown_tool",
        "message": "The requested MemCommit agent tool is not registered.",
        "retryable": False,
    }
    assert "untrusted" not in json.dumps(response)
    assert not root.exists()


def test_add_then_query_runs_through_one_real_registry_and_public_client(
    isolated_store,
):
    store = MemoryStore()
    target = ops.init("notes")
    store.save(target)
    store.set_current(target.name)
    before_checkpoints = len(store.list_checkpoints(target.name))
    registry = build_default_agent_tool_registry(
        MemCommitClient(
            root=isolated_store,
            ordinary_provider_factory=_RegistryQueryProvider,
        )
    )

    add_response = registry.invoke(
        ADD_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "memories",
            "contents": ["Line one.\nLine two.", "same", "same"],
            "context_name": "notes",
        },
    )

    assert add_response["ok"] is True
    assert add_response["result"]["count"] == 3
    assert [memory["content"] for memory in add_response["result"]["memories"]] == [
        "Line one.\nLine two.",
        "same",
        "same",
    ]
    assert [
        memory.content for memory in store.load_direct("notes").memories.values()
    ] == ["Line one.\nLine two.", "same", "same"]
    assert len(store.list_checkpoints(target.name)) == before_checkpoints + 1
    after_add = {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    }

    query_response = registry.invoke(
        QUERY_AGENT_TOOL_NAME,
        {
            "version": QUERY_AGENT_CONTRACT_VERSION,
            "kind": "ordinary",
            "question": "What did the registry add?",
            "context_names": ["notes"],
            "include_descendants": False,
            "follow_embeds": False,
        },
    )

    assert query_response["ok"] is True
    assert query_response["result"]["grounded"] is True
    citation_contents = {
        citation["content"] for citation in query_response["result"]["citations"]
    }
    assert {"Line one.\nLine two.", "same"} <= citation_contents
    assert any("add checkpoint" in content for content in citation_contents)
    assert {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    } == after_add


def test_invalid_add_stops_at_adapter_before_store_access(tmp_path):
    root = tmp_path / "missing-store"
    registry = build_default_agent_tool_registry(MemCommitClient(root=root))

    response = registry.invoke(
        ADD_AGENT_TOOL_NAME,
        {"version": 1, "kind": "memories", "contents": []},
    )

    assert response["error"]["code"] == "invalid_request"
    assert response["error"]["retryable"] is False
    assert not root.exists()


@pytest.mark.parametrize(
    "handler",
    [
        lambda _payload: (_ for _ in ()).throw(RuntimeError("private /host/path")),
        lambda _payload: ["not", "an", "object"],
        lambda _payload: {"not_json": float("nan")},
        lambda _payload: {"nested": {1: "non-text key"}},
    ],
)
def test_custom_handler_failures_are_redacted_and_nonretryable(handler):
    registry = AgentToolRegistry((_binding(handler=handler),))

    response = registry.invoke("example_tool", {})

    assert response["error"] == {
        "code": "internal_error",
        "message": "The registered MemCommit agent tool failed internally.",
        "retryable": False,
    }
    assert "/host" not in json.dumps(response)


def test_registry_depends_only_on_public_client_and_agent_adapters():
    path = (
        Path(__file__).parents[1] / "src" / "memcommit" / "adapters" / "interfaces" / "agent" / "registry.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = (
        "memcommit.commands",
        "memcommit.application.operations",
        "memcommit.infrastructure",
        "memcommit.store",
        "typer",
        "prompt_toolkit",
        "mcp",
    )
    assert not any(name.startswith(forbidden) for name in imported)
    assert "memcommit.adapters.python_api" in imported
    assert "memcommit.adapters.interfaces.agent.add" in imported
    assert "memcommit.adapters.interfaces.agent.atomize" in imported
    assert "memcommit.adapters.interfaces.agent.atomize_grounding" in imported
    assert "memcommit.adapters.interfaces.agent.query" in imported
    assert "memcommit.adapters.interfaces.agent.forget" in imported
    assert "memcommit.adapters.interfaces.agent.resolve" in imported
    assert "memcommit.adapters.interfaces.agent.help" in imported
