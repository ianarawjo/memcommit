"""Versioned machine-contract tests for the Query agent adapter."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from memcommit.adapters.python_api import (
    GrantedQueryResult,
    MemCommitClient,
    OrdinaryQueryResult,
    QueryCitation,
    QueryAuthorityError,
    QueryConfigurationError,
    QueryContextError,
    QueryExecutionError,
    QueryInputError,
    QueryProviderFailure,
    QueryStorageError,
    ReferenceQueryResult,
)
from memcommit.core.context import QueryContextRef
from memcommit.adapters.interfaces.agent.query import (
    QUERY_AGENT_CONTRACT_VERSION,
    QUERY_AGENT_ERROR_MESSAGE_LIMIT,
    QUERY_AGENT_TOOL_NAME,
    QueryAgentAdapter,
    query_agent_tool_schema,
)


def _client(tmp_path) -> MemCommitClient:
    return MemCommitClient(root=tmp_path / "store")


def test_schema_is_fresh_versioned_and_exposes_three_explicit_routes():
    first = query_agent_tool_schema()
    second = query_agent_tool_schema()

    assert first is not second
    assert first["name"] == QUERY_AGENT_TOOL_NAME
    parameters = first["parameters"]
    assert parameters["type"] == "object"
    variants = parameters["oneOf"]
    assert {variant["properties"]["kind"]["const"] for variant in variants} == {
        "ordinary",
        "granted",
        "reference",
    }
    assert all(
        variant["properties"]["version"]["const"] == QUERY_AGENT_CONTRACT_VERSION
        for variant in variants
    )


def test_ordinary_route_calls_only_the_public_client_and_serializes_citations(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    calls: list[dict[str, object]] = []

    def query_ordinary(**kwargs):
        calls.append(kwargs)
        return OrdinaryQueryResult(
            answer="Answer [1]",
            grounded=True,
            citations=(
                QueryCitation(
                    number=1,
                    alias="m1",
                    context_name="task/wiki",
                    kind="memory",
                    uid="memory-1",
                    content="One fact.",
                ),
            ),
        )

    monkeypatch.setattr(client, "query_ordinary", query_ordinary)
    response = QueryAgentAdapter(client).invoke(
        {
            "version": QUERY_AGENT_CONTRACT_VERSION,
            "kind": "ordinary",
            "question": "What changed?",
            "context_names": ["task/wiki"],
            "include_descendants": True,
            "follow_embeds": False,
        }
    )

    assert calls == [
        {
            "question": "What changed?",
            "context_names": ("task/wiki",),
            "include_descendants": True,
            "follow_embeds": False,
        }
    ]
    assert response == {
        "version": QUERY_AGENT_CONTRACT_VERSION,
        "ok": True,
        "kind": "ordinary",
        "result": {
            "answer": "Answer [1]",
            "grounded": True,
            "citations": [
                {
                    "number": 1,
                    "alias": "m1",
                    "context_name": "task/wiki",
                    "kind": "memory",
                    "uid": "memory-1",
                    "content": "One fact.",
                }
            ],
        },
    }
    json.dumps(response)


def test_granted_route_requires_a_question_and_serializes_one_answer(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    calls: list[dict[str, object]] = []

    def query_granted(**kwargs):
        calls.append(kwargs)
        return GrantedQueryResult(
            public_name="construction",
            answer="After 18:00.",
        )

    monkeypatch.setattr(client, "query_granted", query_granted)
    response = QueryAgentAdapter(client).invoke(
        {
            "version": QUERY_AGENT_CONTRACT_VERSION,
            "kind": "granted",
            "public_name": "construction",
            "question": "When does it open?",
            "language": "en",
            "federate_descendants": False,
        }
    )

    assert calls == [
        {
            "public_name": "construction",
            "question": "When does it open?",
            "language": "en",
            "federate_descendants": False,
        }
    ]
    assert response == {
        "version": QUERY_AGENT_CONTRACT_VERSION,
        "ok": True,
        "kind": "granted",
        "result": {
            "public_name": "construction",
            "answer": "After 18:00.",
        },
    }
    json.dumps(response)


def test_reference_route_reconstructs_only_public_routing_metadata(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    calls: list[dict[str, object]] = []

    def query_reference(**kwargs):
        calls.append(kwargs)
        return ReferenceQueryResult(
            source_name="construction-details",
            answer="The rear entrance closes.",
        )

    monkeypatch.setattr(client, "query_reference", query_reference)
    response = QueryAgentAdapter(client).invoke(
        {
            "version": QUERY_AGENT_CONTRACT_VERSION,
            "kind": "reference",
            "reference": {
                "uid": "route-1",
                "name": "construction-details",
                "target_source_uid": "source-1",
                "provider": "codex_chatgpt",
            },
            "question": "What closes?",
            "language": "en",
        }
    )

    assert len(calls) == 1
    reference = calls[0]["reference"]
    assert isinstance(reference, QueryContextRef)
    assert reference.to_dict() == {
        "type": "query_context_ref",
        "uid": "route-1",
        "name": "construction-details",
        "target_source_uid": "source-1",
        "provider": "codex_chatgpt",
    }
    assert calls[0]["question"] == "What closes?"
    assert calls[0]["language"] == "en"
    assert response["result"] == {
        "source_name": "construction-details",
        "answer": "The rear entrance closes.",
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"version": 1, "kind": "ordinary", "question": "Q"}, "version"),
        ({"version": QUERY_AGENT_CONTRACT_VERSION, "kind": "unknown"}, "kind"),
        (
            {
                "version": QUERY_AGENT_CONTRACT_VERSION,
                "kind": "ordinary",
                "question": "Q",
                "surprise": True,
            },
            "unknown fields",
        ),
        (
            {
                "version": QUERY_AGENT_CONTRACT_VERSION,
                "kind": "ordinary",
                "question": "Q",
                "context_names": [],
            },
            "must not be empty",
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
        "query_ordinary",
        lambda **_kwargs: pytest.fail("invalid input reached the public client"),
    )

    response = QueryAgentAdapter(client).invoke(payload)

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_request"
    assert message in response["error"]["message"]
    json.dumps(response)


def test_invalid_request_detail_is_control_safe_and_bounded(tmp_path):
    client = _client(tmp_path)
    hostile_key = "unknown\nfield-" + ("x" * 2_000)

    response = QueryAgentAdapter(client).invoke(
        {
            "version": QUERY_AGENT_CONTRACT_VERSION,
            "kind": "ordinary",
            "question": "Q",
            hostile_key: True,
        }
    )

    message = response["error"]["message"]
    assert "\n" not in message
    assert len(message) <= QUERY_AGENT_ERROR_MESSAGE_LIMIT
    assert message.endswith("…")


def test_provider_and_internal_failures_do_not_expose_host_details(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    payload = {
        "version": QUERY_AGENT_CONTRACT_VERSION,
        "kind": "ordinary",
        "question": "Q",
    }

    def provider_failure(**_kwargs):
        raise QueryProviderFailure("secret endpoint body /private/host/path")

    monkeypatch.setattr(client, "query_ordinary", provider_failure)
    provider_response = QueryAgentAdapter(client).invoke(payload)
    assert provider_response["error"] == {
        "code": "provider_failure",
        "message": "The Query provider could not complete the request.",
        "retryable": True,
    }
    assert "secret" not in json.dumps(provider_response)

    monkeypatch.setattr(
        client,
        "query_ordinary",
        lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("internal /private/host/path")
        ),
    )
    internal_response = QueryAgentAdapter(client).invoke(payload)
    assert internal_response["error"] == {
        "code": "internal_error",
        "message": "The Query tool failed internally.",
        "retryable": False,
    }
    assert "/private" not in json.dumps(internal_response)


@pytest.mark.parametrize(
    ("error", "code", "uses_public_message", "retryable"),
    [
        (QueryInputError("bad input"), "invalid_request", True, False),
        (
            QueryConfigurationError("bad config"),
            "configuration_error",
            True,
            False,
        ),
        (QueryContextError("missing context"), "context_unavailable", True, False),
        (QueryAuthorityError("denied"), "authority_denied", True, False),
        (
            QueryExecutionError("private execution detail"),
            "execution_failed",
            False,
            False,
        ),
        (
            QueryStorageError("/private/storage/path"),
            "storage_failure",
            False,
            False,
        ),
    ],
)
def test_public_error_taxonomy_is_stable_and_sensitive_details_are_bounded(
    tmp_path,
    monkeypatch,
    error,
    code,
    uses_public_message,
    retryable,
):
    client = _client(tmp_path)

    def fail(**_kwargs):
        raise error

    monkeypatch.setattr(client, "query_ordinary", fail)
    response = QueryAgentAdapter(client).invoke(
        {
            "version": QUERY_AGENT_CONTRACT_VERSION,
            "kind": "ordinary",
            "question": "Q",
        }
    )

    assert response["error"]["code"] == code
    assert response["error"]["retryable"] is retryable
    if uses_public_message:
        assert response["error"]["message"] == str(error)
    else:
        assert response["error"]["message"] != str(error)


def test_agent_adapter_depends_only_on_public_api_and_durable_reference_type():
    path = Path(__file__).parents[1] / "src" / "memcommit" / "adapters" / "interfaces" / "agent" / "query.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = (
        "memcommit.adapters.console.commands",
        "memcommit.application.operations",
        "memcommit.infrastructure",
        "memcommit.store",
        "typer",
        "prompt_toolkit",
    )
    assert not any(name.startswith(forbidden) for name in imported)


def test_companion_skill_preserves_route_and_failure_boundaries():
    root = Path(__file__).parents[1]
    skill = (root / "skills" / "memcommit-query" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    metadata = (
        root / "skills" / "memcommit-query" / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")

    assert "name: memcommit-query" in skill
    assert "Use when a user asks an agent" in skill
    assert "Invoke `memcommit_query` directly." in skill
    assert "Always send `version: 3`." in skill
    assert all(
        f"Use `{kind}`" in skill for kind in ("ordinary", "granted", "reference")
    )
    assert "Do not fall back to shell access" in skill
    assert "$memcommit-query" in metadata
