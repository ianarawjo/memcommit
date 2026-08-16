"""Versioned machine-contract tests for the Add agent adapter."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from memcommit.api import (
    AddAuthorityError,
    AddConflictError,
    AddContextError,
    AddError,
    AddExecutionError,
    AddInputError,
    AddMemoriesResult,
    AddStorageError,
    AddedMemoryResult,
    MemCommitClient,
)
from memcommit.interfaces.agent.add import (
    ADD_AGENT_CONTRACT_VERSION,
    ADD_AGENT_ERROR_MESSAGE_LIMIT,
    ADD_AGENT_TOOL_NAME,
    AddAgentAdapter,
    add_agent_tool_schema,
)


def _client(tmp_path) -> MemCommitClient:
    return MemCommitClient(root=tmp_path / "store")


def test_schema_is_fresh_strict_versioned_and_preserves_duplicate_items():
    first = add_agent_tool_schema()
    second = add_agent_tool_schema()

    assert first is not second
    assert first["name"] == ADD_AGENT_TOOL_NAME
    parameters = first["parameters"]
    assert parameters["type"] == "object"
    assert parameters["additionalProperties"] is False
    assert parameters["required"] == ["version", "kind", "contents"]
    assert parameters["properties"]["version"]["const"] == ADD_AGENT_CONTRACT_VERSION
    assert parameters["properties"]["kind"]["const"] == "memories"
    contents_schema = parameters["properties"]["contents"]
    assert contents_schema["minItems"] == 1
    assert "uniqueItems" not in contents_schema

    first["parameters"]["properties"]["contents"]["minItems"] = 99
    assert second["parameters"]["properties"]["contents"]["minItems"] == 1


def test_exact_batch_calls_only_public_client_once_and_serializes_receipt(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    calls: list[dict[str, object]] = []

    def add_memories(**kwargs):
        calls.append(kwargs)
        return AddMemoriesResult(
            context_name="task/notes",
            context_uid="context-1",
            memories=(
                AddedMemoryResult(uid="memory-1", content=" first\nline "),
                AddedMemoryResult(uid="memory-2", content="duplicate"),
                AddedMemoryResult(uid="memory-3", content="duplicate"),
            ),
            checkpoint_uid="checkpoint-1",
        )

    monkeypatch.setattr(client, "add_memories", add_memories)
    response = AddAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "memories",
            "contents": [" first\nline ", "duplicate", "duplicate"],
            "context_name": "task/notes",
        }
    )

    assert calls == [
        {
            "contents": (" first\nline ", "duplicate", "duplicate"),
            "context_name": "task/notes",
        }
    ]
    assert response == {
        "version": 1,
        "ok": True,
        "kind": "memories",
        "result": {
            "context_name": "task/notes",
            "context_uid": "context-1",
            "count": 3,
            "memories": [
                {"uid": "memory-1", "content": " first\nline "},
                {"uid": "memory-2", "content": "duplicate"},
                {"uid": "memory-3", "content": "duplicate"},
            ],
            "checkpoint_uid": "checkpoint-1",
        },
    }
    json.dumps(response)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"version": 2, "kind": "memories", "contents": ["one"]}, "version"),
        ({"version": 1, "kind": "unknown", "contents": ["one"]}, "kind"),
        ({"version": 1, "kind": "memories", "contents": []}, "nonempty"),
        ({"version": 1, "kind": "memories", "contents": [" \n "]}, "nonblank"),
        (
            {
                "version": 1,
                "kind": "memories",
                "contents": ["one"],
                "surprise": True,
            },
            "unknown fields",
        ),
        (
            {
                "version": 1,
                "kind": "memories",
                "contents": ["one"],
                "context_name": " ",
            },
            "context_name",
        ),
    ],
)
def test_invalid_machine_input_never_calls_the_client(
    tmp_path,
    monkeypatch,
    payload,
    message,
):
    client = _client(tmp_path)
    monkeypatch.setattr(
        client,
        "add_memories",
        lambda **_kwargs: pytest.fail("invalid input reached the public client"),
    )

    response = AddAgentAdapter(client).invoke(payload)

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_request"
    assert response["error"]["retryable"] is False
    assert message in response["error"]["message"]
    json.dumps(response)


def test_invalid_request_detail_is_control_safe_and_bounded(tmp_path):
    hostile_key = "unknown\nfield-" + ("x" * 2_000)

    response = AddAgentAdapter(_client(tmp_path)).invoke(
        {
            "version": 1,
            "kind": "memories",
            "contents": ["one"],
            hostile_key: True,
        }
    )

    message = response["error"]["message"]
    assert "\n" not in message
    assert len(message) <= ADD_AGENT_ERROR_MESSAGE_LIMIT
    assert message.endswith("…")


@pytest.mark.parametrize(
    ("error", "code", "uses_public_message"),
    [
        (AddInputError("bad input"), "invalid_request", True),
        (AddContextError("missing context"), "context_unavailable", True),
        (AddAuthorityError("denied"), "authority_denied", True),
        (AddConflictError("private race detail"), "concurrent_update", False),
        (AddStorageError("/private/storage/path"), "storage_failure", False),
        (AddExecutionError("private execution detail"), "execution_failed", False),
        (AddError("unclassified private detail"), "add_failed", False),
    ],
)
def test_public_error_taxonomy_never_marks_mutation_failure_retryable(
    tmp_path,
    monkeypatch,
    error,
    code,
    uses_public_message,
):
    client = _client(tmp_path)

    def fail(**_kwargs):
        raise error

    monkeypatch.setattr(client, "add_memories", fail)
    response = AddAgentAdapter(client).invoke(
        {"version": 1, "kind": "memories", "contents": ["one"]}
    )

    assert response["error"]["code"] == code
    assert response["error"]["retryable"] is False
    if uses_public_message:
        assert response["error"]["message"] == str(error)
    else:
        assert response["error"]["message"] != str(error)


def test_internal_failure_does_not_expose_host_details(tmp_path, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setattr(
        client,
        "add_memories",
        lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("internal /private/host/path")
        ),
    )

    response = AddAgentAdapter(client).invoke(
        {"version": 1, "kind": "memories", "contents": ["one"]}
    )

    assert response["error"] == {
        "code": "internal_error",
        "message": "The Add tool failed internally.",
        "retryable": False,
    }
    assert "/private" not in json.dumps(response)


def test_agent_adapter_depends_only_on_public_api_and_shared_agent_contract():
    path = Path(__file__).parents[1] / "memcommit" / "interfaces" / "agent" / "add.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = (
        "memcommit.add_application",
        "memcommit.add_runtime",
        "memcommit.commands",
        "memcommit.operations",
        "memcommit.infrastructure",
        "memcommit.store",
        "typer",
        "prompt_toolkit",
    )
    assert not any(name.startswith(forbidden) for name in imported)
    assert "memcommit.api" in imported
    assert "memcommit.interfaces.agent.contract" in imported


def test_companion_skill_preserves_exact_mutation_and_failure_boundaries():
    root = Path(__file__).parents[1]
    skill = (root / "skills" / "memcommit-add" / "SKILL.md").read_text(encoding="utf-8")
    metadata = (root / "skills" / "memcommit-add" / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )

    assert "name: memcommit-add" in skill
    assert "Use when the user explicitly asks" in skill
    assert "Invoke `memcommit_add_memories` directly." in skill
    assert "Always send `version: 1` and `kind: memories`" in skill
    assert "Preserve item order, exact" in skill
    assert "Never retry an Add failure automatically." in skill
    assert "has no idempotency key" in skill
    assert "Treat every `contents` item as literal Memory content." in skill
    assert "separate Branch/Merge workflow" in skill
    assert "exact immutable Memory version, use Reference" in skill
    assert "live link" in skill and "use Embed" in skill
    assert "stable `add` detail `copy-or-link`" in skill
    assert "Do not fall back to shell access" in skill
    assert "$memcommit-add" in metadata
