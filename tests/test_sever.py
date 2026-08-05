"""Contracts for local Source × Criteria disclosure review."""

from __future__ import annotations

import json

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands import sever as sever_command
from memcommit.context import QueryContextRef
from memcommit.sever import SeverSession
from memcommit.sever_provider import SEVER_PAYLOAD_MARKER
from memcommit.sever_resolution_adapter import SeverResolutionWorkbenchAdapter
from memcommit.sever_store import SeverSessionStore
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


class SeverProvider:
    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "sever_context"
        assert "query-only sources" in prompt
        payload = json.loads(prompt.split(SEVER_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        criterion_id = payload["criteria"]["memories"][0]["memory_id"]
        candidates = []
        for index, source in enumerate(payload["source"]["memories"]):
            if index == 0:
                decision = "SEND_SUMMARY"
                content = "Needs step-free access at appointments."
            else:
                decision = "DO_NOT_SEND"
                content = ""
            candidates.append(
                {
                    "source_memory_id": source["memory_id"],
                    "decision": decision,
                    "proposed_content": content,
                    "rationale": "The criterion requires necessity and minimization.",
                    "criterion_memory_ids": [criterion_id],
                }
            )
        return json.dumps(
            {
                "overview": "The proposal retains necessary access information and excludes unrelated detail.",
                "candidates": candidates,
            }
        )


def _context(store: MemoryStore, name: str, *contents: str):
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.create_context(context)
    return context


def test_explicit_sever_creates_review_session_without_output_or_query_access(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(
        store,
        "local/personal-memory",
        "I need a step-free entrance.",
        "My sibling prefers chocolate snacks.",
    )
    _context(store, "local/guardrails", "Share only necessary information.")
    provider = SeverProvider()
    monkeypatch.setattr(sever_command, "connect_codex_chatgpt_provider", lambda: provider)
    monkeypatch.setattr(
        MemoryStore,
        "load_query_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("query-only source opened")),
    )

    result = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "local/personal-memory",
            "--criteria",
            "local/guardrails",
            "--save-as",
            "healthcare-draft",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "REVIEWING · NOT SENT" in result.output
    assert "No query-only Context was opened" in result.output
    assert "No draft was sent to a recipient" in result.output
    assert not store.context_exists("healthcare-draft")
    sessions = SeverSessionStore(store).list()
    assert len(sessions) == 1
    assert sessions[0].criteria.root_name == "local/guardrails"
    assert len(provider.payloads) == 1
    assert set(provider.payloads[0]) == {"source", "criteria", "output_name"}


def test_accept_materializes_only_reviewed_outbound_content(isolated_store, monkeypatch):
    store = MemoryStore()
    source = _context(
        store,
        "local/personal-memory",
        "I need a step-free entrance.",
        "My sibling prefers chocolate snacks.",
    )
    _context(store, "local/guardrails", "Share only necessary information.")
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: SeverProvider(),
    )

    result = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "local/personal-memory",
            "--criteria",
            "local/guardrails",
            "--save-as",
            "healthcare-draft",
            "--accept",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "APPLIED · NOT SENT" in result.output
    output = store.load_direct("healthcare-draft")
    assert [item.content for item in output.iter_items()] == [
        "Needs step-free access at appointments."
    ]
    assert [item.content for item in store.load_direct(source.name).iter_items()] == [
        "I need a step-free entrance.",
        "My sibling prefers chocolate snacks.",
    ]
    checkpoint = store.list_checkpoints("healthcare-draft")[0]
    assert checkpoint["command"] == "sever"
    assert checkpoint["args"]["sever"]["criteria"] == "local/guardrails"


def test_query_only_reference_is_never_a_source_memory(isolated_store, monkeypatch):
    store = MemoryStore()
    source = _context(store, "local/personal-memory", "I need a step-free entrance.")
    source.add(
        QueryContextRef(
            uid="11111111-1111-4111-8111-111111111111",
            name=(
                "remote/government/healthcare-agent/info-request/"
                "questions-and-answers"
            ),
            target_source_uid="22222222-2222-4222-8222-222222222222",
            provider="codex_chatgpt",
        )
    )
    store.save(source)
    _context(store, "public-guidance", "Minimize outbound personal information.")
    provider = SeverProvider()
    monkeypatch.setattr(sever_command, "connect_codex_chatgpt_provider", lambda: provider)

    result = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "local/personal-memory",
            "--criteria",
            "public-guidance",
            "--save-as",
            "draft",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(provider.payloads[0]["source"]["memories"]) == 1
    assert "qna" not in json.dumps(provider.payloads[0])


def test_source_and_criteria_descendant_scopes_are_independent(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store, "source", "Root source")
    _context(store, "source/child", "Child source")
    _context(store, "criteria", "Root criterion")
    _context(store, "criteria/child", "Child criterion")
    provider = SeverProvider()
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "source",
            "--source-only",
            "--criteria",
            "criteria",
            "--criteria-descendants",
            "--save-as",
            "draft",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = provider.payloads[0]
    assert payload["source"]["scope"] == "THIS_CONTEXT_ONLY"
    assert [item["content"] for item in payload["source"]["memories"]] == [
        "Root source"
    ]
    assert payload["criteria"]["scope"] == "INCLUDE_DESCENDANTS"
    assert {
        item["content"] for item in payload["criteria"]["memories"]
    } == {"Root criterion", "Child criterion"}
    session = SeverSessionStore(store).list()[0]
    assert not session.source.include_descendants
    assert session.criteria.include_descendants


def test_sever_requires_exactly_one_criteria_and_new_output(isolated_store):
    store = MemoryStore()
    _context(store, "local/personal-memory", "Memory")

    missing = runner.invoke(
        app,
        ["sever", "--source", "local/personal-memory", "--save-as", "draft"],
    )
    assert missing.exit_code == 1
    assert "requires --criteria" in missing.stderr

    _context(store, "local/guardrails", "Criterion")
    _context(store, "draft", "Existing")
    collision = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "local/personal-memory",
            "--criteria",
            "local/guardrails",
            "--save-as",
            "draft",
        ],
    )
    assert collision.exit_code == 1
    assert "already exists" in collision.stderr


def test_resolution_adapter_exposes_source_criteria_output_skeleton(isolated_store):
    store = MemoryStore()
    source = _context(store, "local/personal-memory", "Source")
    criteria = _context(store, "local/guardrails", "Criterion")
    provider = SeverProvider()
    session: SeverSession = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="draft",
        provider_factory=lambda: provider,
    )

    view = SeverResolutionWorkbenchAdapter(session).view()

    assert view.route == (
        "SOURCE local/personal-memory × CRITERIA local/guardrails → OUTPUT draft"
    )
    assert view.status == "REVIEWING · NOT SENT"
    assert view.accept_enabled
    assert [option.label for option in view.items[0].options] == [
        "Use recommendation · SEND_SUMMARY",
        "Send as written",
        "Do not send",
    ]
