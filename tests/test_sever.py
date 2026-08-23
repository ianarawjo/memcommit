"""Contracts for local Source × Criteria content severing."""

from __future__ import annotations

import json
from types import SimpleNamespace
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands import sever as sever_command
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
)
from memcommit.commands.sever_sessions import (
    list_sever_session_catalog,
    reload_selected_sever_session,
)
from memcommit.commands.resolution_workbench_shell import (
    resolution_report_fragments,
    resolution_viewer_fragments,
    session_review_action_view,
    session_todo_view,
)
from memcommit.impact_controller import ImpactController
from memcommit.context import QueryContextRef
from memcommit.query_provider import QueryProviderError
from memcommit.resolution_workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
)
from memcommit.sever import (
    SEVER_SCHEMA_VERSION,
    SeverApplication,
    SeverSession,
    sever_record_digest,
)
from memcommit.sever_provider import SEVER_PAYLOAD_MARKER
from memcommit.sever_resolution_adapter import (
    SeverResolutionWorkbenchAdapter,
    sever_memory_changes,
)
from memcommit.sever_store import SeverSessionStore
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


class SeverProvider:
    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "sever_context"
        summary_schema = output_schema["properties"]["application_summary"]
        assert "maxItems" not in summary_schema["properties"]["source_memory_ids"]
        assert "maxItems" not in summary_schema["properties"]["criterion_memory_ids"]
        assert "query-only sources" in prompt
        assert "selectively forgetting information" in prompt
        assert "decide only what the local Result remembers" in prompt
        assert "KEEP_AS_WRITTEN" in prompt
        assert "WHAT CHANGED summary rather than a count report" in prompt
        instructions = prompt.split(SEVER_PAYLOAD_MARKER, 1)[0]
        for unrelated_term in (
            "SEND_",
            "DO_NOT_SEND",
            "Share",
            "recipient",
            "transmission",
            "audience",
            "destination",
        ):
            assert unrelated_term not in instructions
        payload = json.loads(prompt.split(SEVER_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        criterion_id = payload["criteria"]["memories"][0]["memory_id"]
        candidates = []
        for index, source in enumerate(payload["source"]["memories"]):
            if index == 0:
                decision = "KEEP_SUMMARY"
                content = "Needs step-free access at appointments."
            else:
                decision = "FORGET"
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
                "overview": "The proposal keeps necessary access information and forgets unrelated detail.",
                "application_summary": {
                    "text": (
                        "Access-related needs were condensed while unrelated "
                        "personal detail was removed under the minimization criterion."
                    ),
                    "source_memory_ids": [payload["source"]["memories"][0]["memory_id"]],
                    "criterion_memory_ids": [criterion_id],
                },
                "candidates": candidates,
            }
        )


def _context(store: MemoryStore, name: str, *contents: str):
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.create_context(context)
    return context


def test_sever_start_reports_real_blocking_stages(isolated_store, monkeypatch):
    store = MemoryStore()
    source = _context(store, "local/source", "Source")
    criteria = _context(store, "local/criteria", "Criterion")
    events: list[tuple[object, ...]] = []

    class Progress:
        def update(self, stage, *, step):
            events.append(("update", stage, step))

    def wait(operation, stage, *, total, work):
        events.append(("start", operation, stage, total))
        try:
            return work(Progress())
        finally:
            events.append(("close",))

    monkeypatch.setattr(sever_command, "run_command_wait", wait)

    sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="local/result",
        provider_factory=SeverProvider,
    )

    assert events == [
        ("start", "SEVER", "preparing source and criteria", 3),
        ("update", "connecting provider", 2),
        ("update", "analyzing 1 source x 1 criteria", 3),
        ("close",),
    ]


def test_sever_provider_failure_reports_the_unsaved_frozen_frame(isolated_store):
    store = MemoryStore()
    source = _context(store, "local/source", "One", "Two")
    criteria = _context(store, "local/criteria", "Criterion")

    class TimedOutProvider:
        def complete(self, *args, **kwargs):
            raise QueryProviderError(
                "The temporary Codex sever_context timed out after 600 seconds."
            )

    with pytest.raises(
        sever_command.SeverCommandError,
        match=r"Prepared input: 2 Source Memories x 1 Criteria Memories",
    ):
        sever_command._start(
            store=store,
            source_name=source.name,
            criteria_name=criteria.name,
            output_name="local/result",
            provider_factory=TimedOutProvider,
        )


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
    assert "SEVER READY · local/personal-memory → healthcare-draft" in result.output
    assert "IMPACT · mem impact sever --session" in result.output
    assert "query-only Contexts do not grant" not in result.output
    assert "OUTPUT · healthcare-draft · READY TO CREATE" in result.output
    assert not store.context_exists("healthcare-draft")
    sessions = SeverSessionStore(store).list()
    assert len(sessions) == 1
    assert sessions[0].criteria.root_name == "local/guardrails"
    assert len(provider.payloads) == 1
    assert set(provider.payloads[0]) == {"source", "criteria", "output_name"}


def test_sever_accepts_positional_roles_and_defaults_to_self_save(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store, "practice", "Namespace marker")
    _context(store, "practice/source", "Source")
    _context(store, "practice/criteria", "Criterion")
    provider = SeverProvider()
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: provider,
    )

    defaulted = runner.invoke(
        app,
        ["sever", "practice/source", "practice/criteria"],
    )
    applied = runner.invoke(
        app,
        [
            "sever",
            "practice/source",
            "practice/criteria",
            "practice/result",
            "--accept",
        ],
    )
    mixed_alias = runner.invoke(
        app,
        [
            "sever",
            "practice/source",
            "--against",
            "practice/criteria",
            "--save-as",
            "practice/alias-result",
        ],
    )

    assert defaulted.exit_code == 0, defaulted.output + defaulted.stderr
    assert "SEVER READY · practice/source → practice/source" in defaulted.output
    assert "OUTPUT · practice/source · WILL UPDATE SOURCE" in defaulted.output
    assert store.load_direct("practice/source").memories
    assert applied.exit_code == 0, applied.output + applied.stderr
    assert "SEVER APPLIED · practice/source → practice/result" in applied.output
    assert store.context_exists("practice/result")
    assert mixed_alias.exit_code == 0, mixed_alias.output + mixed_alias.stderr
    assert "OUTPUT · practice/alias-result · READY TO CREATE" in mixed_alias.output
    assert len(provider.payloads) == 3


def test_sever_rejects_duplicate_or_overfull_positional_roles_before_provider(
    isolated_store,
    monkeypatch,
):
    provider = SeverProvider()
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: provider,
    )

    duplicate = runner.invoke(
        app,
        ["sever", "source", "criteria", "--source", "other"],
    )
    overfull = runner.invoke(
        app,
        ["sever", "source", "criteria", "result", "extra"],
    )

    assert duplicate.exit_code == 2
    assert "SOURCE was supplied both positionally and with --source" in (
        duplicate.output + duplicate.stderr
    )
    assert overfull.exit_code == 2
    assert "expected at most three positional Contexts" in (
        overfull.output + overfull.stderr
    )
    assert provider.payloads == []


def test_sever_self_save_preserves_context_and_memory_identity(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _context(
        store,
        "practice/source",
        "Source remains intact",
        "Unnecessary detail",
    )
    _context(store, "practice/criteria", "Criterion")
    provider = SeverProvider()
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: provider,
    )
    before_uid = source.uid
    before_memory_uids = tuple(source.memories)

    result = runner.invoke(
        app,
        [
            "sever",
            "practice/source",
            "practice/criteria",
            "practice/source",
            "--accept",
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "SAVE MODE · SELF-SAVE" in result.output
    assert "SOURCE · UPDATED" in result.output
    updated = store.load_direct("practice/source")
    assert updated.uid == before_uid
    assert tuple(updated.memories) == before_memory_uids[:1]
    assert updated.memories[before_memory_uids[0]].content == (
        "Needs step-free access at appointments."
    )
    checkpoint = store.list_checkpoints("practice/source")[0]
    assert checkpoint["args"]["sever"]["save_mode"] == "SELF_SAVE"
    assert "context_creation" not in checkpoint["args"]
    assert len(provider.payloads) == 1


def test_sever_rejects_recursive_self_save_before_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store, "practice/source", "Source")
    _context(store, "practice/source/child", "Child Source")
    _context(store, "practice/criteria", "Criterion")
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
            "practice/source",
            "practice/criteria",
            "--source-descendants",
            "--accept",
        ],
    )

    assert result.exit_code == 1
    assert "Self-save requires Source descendants to be excluded" in (
        result.output + result.stderr
    )
    assert provider.payloads == []


def test_scripted_sever_decision_rejects_a_stale_reviewed_session(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store, "source", "Source")
    _context(store, "criteria", "Criterion")
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: SeverProvider(),
    )
    started = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "source",
            "--criteria",
            "criteria",
            "--save-as",
            "result",
        ],
    )
    assert started.exit_code == 0, started.output
    before = SeverSessionStore(store).list()[0]

    result = runner.invoke(
        app,
        [
            "sever",
            "--resume",
            before.uid,
            "--candidate",
            before.candidates[0].uid,
            "--choice",
            "recommended",
            "--expect-session",
            "0" * 64,
        ],
    )

    assert result.exit_code == 1
    assert "changed after this command was reviewed" in (
        result.output + result.stderr
    )
    assert SeverSessionStore(store).load(before.uid) == before


def test_accept_materializes_only_reviewed_result_content(isolated_store, monkeypatch):
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
    assert "SEVER APPLIED · local/personal-memory → healthcare-draft" in result.output
    assert "RESULT · CREATED SEPARATELY" in result.output
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


def test_sever_undo_and_redo_restore_output_session_and_checkpoint_log(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store, "source", "Source")
    _context(store, "criteria", "Criterion")
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: SeverProvider(),
    )
    applied = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "source",
            "--criteria",
            "criteria",
            "--save-as",
            "result",
            "--accept",
        ],
    )
    assert applied.exit_code == 0, applied.output
    result_before = store.load_direct("result").to_dict()
    applied_session = SeverSessionStore(store).list()[0]
    assert applied_session.application is not None
    application = applied_session.application

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 0, undone.output
    assert "Undid command: mem sever" in undone.output
    assert not store.context_exists("result")
    reviewing = SeverSessionStore(store).load(applied_session.uid)
    assert reviewing.state == "REVIEWING"
    assert reviewing.application is None
    [(archived_context, archived_checkpoints)] = (
        store.list_command_context_archives()
    )
    assert archived_context.to_dict() == result_before
    assert [entry["command"] for entry in archived_checkpoints] == [
        "undo",
        "sever",
    ]

    redone = runner.invoke(app, ["redo"])

    assert redone.exit_code == 0, redone.output
    assert "Redid command: mem sever" in redone.output
    assert store.load_direct("result").to_dict() == result_before
    restored_session = SeverSessionStore(store).load(applied_session.uid)
    assert restored_session.state == "APPLIED"
    assert restored_session.application == application
    assert store.list_command_context_archives() == ()
    assert [
        entry["command"] for entry in store.list_checkpoints("result")
    ] == ["redo", "undo", "sever"]
    assert runner.invoke(app, ["switch", "result"]).exit_code == 0
    logged = runner.invoke(app, ["log", "--plain"])
    assert logged.exit_code == 0, logged.output
    assert "redo" in logged.output
    assert "undo" in logged.output
    assert "sever" in logged.output

    undone_again = runner.invoke(app, ["undo"])
    assert undone_again.exit_code == 0, undone_again.output
    assert not store.context_exists("result")

    reapplied = runner.invoke(
        app,
        ["sever", "--resume", applied_session.uid, "--accept"],
    )
    assert reapplied.exit_code == 0, reapplied.output
    assert store.load_direct("result").uid != application.output_context_uid
    cleared_redo = runner.invoke(app, ["redo"])
    assert cleared_redo.exit_code == 1
    assert "no recorded Context command to redo" in cleared_redo.stderr


def test_sever_self_save_undo_and_redo_restore_source_and_session(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _context(
        store,
        "source",
        "I need a step-free entrance.",
        "My sibling prefers chocolate snacks.",
    )
    _context(store, "criteria", "Share only necessary information.")
    original = source.to_dict()
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: SeverProvider(),
    )

    applied = runner.invoke(app, ["sever", "source", "criteria", "--accept"])

    assert applied.exit_code == 0, applied.output
    self_saved = store.load_direct("source").to_dict()
    assert self_saved != original
    applied_session = SeverSessionStore(store).list()[0]
    application = applied_session.application
    assert application is not None

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 0, undone.output
    assert store.load_direct("source").to_dict() == original
    reviewing = SeverSessionStore(store).load(applied_session.uid)
    assert reviewing.state == "REVIEWING"
    assert reviewing.application is None

    redone = runner.invoke(app, ["redo"])

    assert redone.exit_code == 0, redone.output
    assert store.load_direct("source").to_dict() == self_saved
    restored = SeverSessionStore(store).load(applied_session.uid)
    assert restored.state == "APPLIED"
    assert restored.application == application
    assert [
        checkpoint["command"] for checkpoint in store.list_checkpoints("source")
    ] == ["redo", "undo", "sever"]


def test_sever_undo_rolls_back_context_archive_when_session_save_fails(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store, "source", "Source")
    _context(store, "criteria", "Criterion")
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: SeverProvider(),
    )
    applied = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "source",
            "--criteria",
            "criteria",
            "--save-as",
            "result",
            "--accept",
        ],
    )
    assert applied.exit_code == 0, applied.output
    session = SeverSessionStore(store).list()[0]
    result_before = store.load_direct("result").to_dict()
    original_save = SeverSessionStore.save

    def fail_reviewing_save(self, candidate, *, expected_digest):
        if candidate.uid == session.uid and candidate.state == "REVIEWING":
            raise OSError("simulated Sever session failure")
        return original_save(
            self,
            candidate,
            expected_digest=expected_digest,
        )

    monkeypatch.setattr(SeverSessionStore, "save", fail_reviewing_save)

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 1
    assert "simulated Sever session failure" in undone.stderr
    assert store.load_direct("result").to_dict() == result_before
    assert SeverSessionStore(store).load(session.uid) == session
    assert store.list_command_context_archives() == ()
    assert [
        entry["command"] for entry in store.list_checkpoints("result")
    ] == ["sever"]


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
    session = SeverSessionStore(store).list()[0]
    assert session.source.excluded_query_context_names == (
        "remote/government/healthcare-agent/info-request/questions-and-answers",
    )
    overview = SeverResolutionWorkbenchAdapter(session).view().overview
    assert "NOT INCLUDED" in overview
    assert "questions-and-answers" in overview
    assert "do not grant readable Memory access" in overview


def test_provider_schema_avoids_unsupported_unique_items_and_rejects_duplicates(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store, "source", "Source")
    _context(store, "criteria", "Criterion")

    class DuplicateCriterionProvider(SeverProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            assert "uniqueItems" not in json.dumps(output_schema)
            value = json.loads(
                super().complete(
                    prompt,
                    operation=operation,
                    output_schema=output_schema,
                )
            )
            refs = value["candidates"][0]["criterion_memory_ids"]
            value["candidates"][0]["criterion_memory_ids"] = [refs[0], refs[0]]
            return json.dumps(value)

    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: DuplicateCriterionProvider(),
    )
    result = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "source",
            "--criteria",
            "criteria",
            "--save-as",
            "draft",
        ],
    )

    assert result.exit_code == 1
    assert "cited a criterion more than once" in result.stderr
    assert not store.context_exists("draft")


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
            "-r",
            "--source-root-only",
            "--criteria",
            "criteria",
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


def test_new_sever_setup_resolves_both_operands_against_one_current_snapshot(
    isolated_store,
    monkeypatch,
):
    current_reads: list[str] = []
    resolved: list[tuple[str, str | None]] = []

    def changing_current(_store):
        value = "alpha/current" if not current_reads else "beta/current"
        current_reads.append(value)
        return value

    def resolve_access(
        _store,
        operand,
        *,
        current_name,
        required_permission,
    ):
        assert required_permission == "READ"
        resolved.append((operand, current_name))
        return SimpleNamespace(display_name=operand)

    monkeypatch.setattr(MemoryStore, "current_context_name", changing_current)
    monkeypatch.setattr(sever_command, "resolve_context_access", resolve_access)
    monkeypatch.setattr(
        sever_command,
        "run_command_wait",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            sever_command.SeverCommandError("stop after operand resolution")
        ),
    )

    result = runner.invoke(
        app,
        [
            "sever",
            "--criteria",
            "../criteria",
            "--save-as",
            "result",
        ],
    )

    assert result.exit_code == 1
    assert current_reads == ["alpha/current"]
    assert resolved == [
        ("alpha/current", "alpha/current"),
        ("alpha/criteria", "alpha/current"),
    ]


def test_sever_requires_exactly_one_criteria_and_new_output(isolated_store):
    store = MemoryStore()
    _context(store, "local/personal-memory", "Memory")

    missing = runner.invoke(
        app,
        ["sever", "--source", "local/personal-memory", "--save-as", "draft"],
    )
    assert missing.exit_code == 1
    assert "requires CRITERIA" in missing.stderr

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
        "SOURCE local/personal-memory × CRITERIA local/guardrails → OTHER-SAVE draft"
    )
    assert view.status == "REVIEWING"
    assert view.accept_enabled
    assert {item.priority for item in view.items} == {"REQUIRED"}
    item = view.items[0]
    assert item.title == "Source"
    assert item.issue_presentation is not None
    evidence = item.issue_presentation.evidence[0]
    assert evidence.group_heading == "SEVER ASSESSMENT"
    assert evidence.sources_heading == "EVIDENCE MEMORIES"
    assert evidence.classification == "RECOMMENDED RESULT · SUMMARIZE"
    assert [source.label for source in evidence.sources] == [
        "SOURCE MEMORY",
        "APPLICABLE CRITERION 1",
    ]
    assert [block.heading for block in item.blocks] == [
        "PROPOSED RESULT MEMORY"
    ]
    assert [
        (location.role, location.name, location.state)
        for location in view.context_locations
    ] == [
        ("SOURCE", source.name, ""),
        ("CRITERIA", criteria.name, ""),
        ("RESULT", "draft", "CREATE ON APPLY"),
    ]
    navigation = ResolutionNavigation(
        selected_item_uid=item.uid,
        expanded_item_uid=item.uid,
    )
    detail = "".join(
        text
        for _style, text in resolution_viewer_fragments(
            view,
            navigation,
        )
    )
    ordered_headings = (
        "SEVER ASSESSMENT",
        "CLASSIFICATION",
        "EVIDENCE MEMORIES",
        "SOURCE MEMORY · FROM local/personal-memory",
        "WHY THIS TREATMENT",
        "SEVER QUESTION",
        "PROPOSED RESULT TREATMENTS",
        "PROPOSED RESULT MEMORY",
        "RESPONSE",
    )
    positions = [detail.index(heading) for heading in ordered_headings]
    assert positions == sorted(positions)
    report = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            review_and_apply=True,
        )
    )
    assert "SOURCE OVERVIEW" in report
    assert "WHAT MEM UNDERSTOOD" not in report
    assert "WHAT APPLIED" in report
    assert "Access-related needs were condensed" in report
    assert "Affected Source examples: “Source”" in report
    assert "Main Criteria: “Criterion”" in report
    assert "SOURCE MEMORIES · 1" not in report
    assert "DISCLOSURE 1 ·" not in report
    assert [option.label for option in view.items[0].options] == [
        "Use recommendation · SUMMARIZE",
        "Keep",
        "Forget",
    ]
    assert [result.label for result in view.results] == ["SUMMARIZE"]


def test_applied_resolution_report_names_its_existing_checkpoint(isolated_store):
    store = MemoryStore()
    source = _context(store, "local/personal-memory", "Source")
    criteria = _context(store, "local/guardrails", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="draft",
        provider_factory=lambda: SeverProvider(),
    )
    checkpoint_uid = str(uuid.uuid4())
    applied = session.with_application(
        SeverApplication(
            output_context_uid=str(uuid.uuid4()),
            checkpoint_uid=checkpoint_uid,
            result_memory_uids=tuple(
                str(uuid.uuid4()) for _candidate, _source, _content in session.results()
            ),
        )
    )

    view = SeverResolutionWorkbenchAdapter(applied).view()

    assert view.report_items_summary is not None
    assert (
        f"Result Context draft was created in checkpoint [{checkpoint_uid[:8]}]."
        in view.report_items_summary.text
    )
    assert "Result Context has not been created" not in view.report_items_summary.text
    assert "RECOVERY · mem undo" in sever_command.render_sever(applied)


def test_custom_sever_response_remains_answered_and_apply_ready(isolated_store):
    store = MemoryStore()
    source = _context(store, "local/personal-memory", "Source")
    criteria = _context(store, "local/guardrails", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="draft",
        provider_factory=lambda: SeverProvider(),
    )
    candidate = session.candidates[0]
    session = session.select(candidate.uid, "CUSTOM", "Custom local result.")

    view = SeverResolutionWorkbenchAdapter(session).view()
    item = view.item(candidate.uid)
    todo = session_todo_view(
        view,
        {},
        review_and_apply=True,
        read_only=False,
    )

    assert item.commentable is True
    assert item.response_state == "ANSWERED"
    assert item.response_text == "Custom local result."
    assert item.blocks[0].text == "Custom local result."
    assert todo.kind == "REVIEW AND APPLY"
    assert (
        session_review_action_view(view, {}, whole_set_available=True).kind == "APPLY"
    )


def test_sever_routes_its_local_output_to_decision_free_auto_accept(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _context(store, "local/personal-memory", "Source")
    criteria = _context(store, "local/guardrails", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="draft",
        provider_factory=lambda: SeverProvider(),
    )
    sessions = SeverSessionStore(store)
    sessions.save(session, expected_digest=None)
    workbench_kwargs = []

    def next_action(*_args, **kwargs):
        workbench_kwargs.append(kwargs)
        return ResolutionWorkbenchAction(kind="CLOSE")

    monkeypatch.setattr(
        "memcommit.commands.resolution_workbench_shell.run_resolution_workbench_shell",
        next_action,
    )

    changed = sever_command._run_workbench(store, session)

    assert changed.output_name == "draft"
    assert sessions.load(session.uid).output_name == "draft"
    assert workbench_kwargs[0]["decision_free_behavior"] == "AUTO_ACCEPT"
    view = SeverResolutionWorkbenchAdapter(session).view()
    item = view.items[0]
    turn = workbench_kwargs[0]["turn_command_review"](
        ResolutionWorkbenchAction(
            kind="SUBMIT_ITEM",
            item_uid=item.uid,
            option_uid=item.options[0].uid,
        )
    )
    assert turn is not None
    assert turn.argv[-2:] == (
        "--expect-session",
        sever_record_digest(session),
    )
    assert "--accept" not in turn.argv


def test_sever_report_lists_large_result_only_once_when_impact_is_present(
    isolated_store,
):
    store = MemoryStore()
    source = _context(store, "source", "A uniquely identifiable Source Memory")
    criteria = _context(store, "criteria", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="result",
        provider_factory=lambda: SeverProvider(),
    )
    view = SeverResolutionWorkbenchAdapter(session).view()
    impact = ImpactController.from_memory_changes(
        operation=view.operation,
        artifact_uid=view.artifact_uid,
        revision=view.revision,
        title="IMPACT · LOCAL SEVER RESULT · SOURCE UNCHANGED",
        summary="The exact local result.",
        changes=sever_memory_changes(session),
    )

    report = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            review_and_apply=True,
            impact_controller=impact,
        )
    )

    assert "OTHER-SAVE DRAFT · SOURCE UNCHANGED" not in report
    assert report.count("Needs step-free access at appointments.") == 1
    assert "source → result" in report
    assert "- A uniquely identifiable Source Memory" in report
    assert "+ Needs step-free access at appointments." in report
    assert "[SUMMARIZE]" in report
    assert "[SUMMARIZE] source → result [" in report
    assert "RULE · Criterion" not in report
    assert "WHY · The criterion requires necessity and minimization." not in report


def test_legacy_share_oriented_tokens_load_as_neutral_sever_decisions(
    isolated_store,
):
    store = MemoryStore()
    source = _context(store, "source", "Source")
    criteria = _context(store, "criteria", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="result",
        provider_factory=lambda: SeverProvider(),
    )
    legacy = session.to_dict()
    legacy["schema_version"] = 1
    candidate = legacy["candidates"][0]
    candidate["recommendation"] = "DO_NOT_SEND"
    candidate["proposed_content"] = ""
    candidate["selection"] = "EXCLUDE"

    loaded = SeverSession.from_dict(legacy)

    assert loaded.candidates[0].recommendation == "FORGET"
    assert loaded.candidates[0].selection == "FORGET"
    assert loaded.to_dict()["schema_version"] == SEVER_SCHEMA_VERSION


def test_version_two_session_without_grounded_summary_or_exclusion_names_loads(
    isolated_store,
):
    store = MemoryStore()
    source = _context(store, "source", "Source")
    criteria = _context(store, "criteria", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="result",
        provider_factory=lambda: SeverProvider(),
    )
    legacy = session.to_dict()
    legacy["schema_version"] = 2
    legacy.pop("applied_summary")
    legacy["source"].pop("excluded_query_context_names")
    legacy["criteria"].pop("excluded_query_context_names")

    loaded = SeverSession.from_dict(legacy)

    assert loaded.applied_summary is None
    assert loaded.source.excluded_query_context_names == ()
    assert loaded.criteria.excluded_query_context_names == ()
    summary = SeverResolutionWorkbenchAdapter(loaded).view().report_items_summary
    assert summary is not None
    assert "Affected Source examples: “Source”" in summary.text


def test_saved_sever_catalog_projects_common_picker_rows_and_reloads(
    isolated_store,
):
    store = MemoryStore()
    source = _context(store, "source", "Source")
    criteria = _context(store, "criteria", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="draft",
        provider_factory=lambda: SeverProvider(),
    )
    sessions = SeverSessionStore(store)
    sessions.save(session, expected_digest=None)

    catalog = list_sever_session_catalog(sessions)

    assert len(catalog) == 1
    entry = catalog[0]
    assert entry.picker_entry.kind == "sever"
    assert entry.picker_entry.key == session.uid
    assert entry.picker_entry.status == "REVIEWING · OTHER-SAVE"
    assert entry.picker_entry.reopen_argv == (
        "mem",
        "sever",
        "--resume",
        session.uid,
    )
    assert "source × criteria → draft" == entry.picker_entry.title
    assert reload_selected_sever_session(sessions, entry) == session


def test_shared_sever_picker_revalidates_the_selected_record(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _context(store, "source", "Source")
    criteria = _context(store, "criteria", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="draft",
        provider_factory=lambda: SeverProvider(),
    )
    sessions = SeverSessionStore(store)
    sessions.save(session, expected_digest=None)

    def change_then_select(entries, **kwargs):
        changed = session.select(session.candidates[0].uid, "FORGET")
        sessions.save(changed, expected_digest=sever_record_digest(session))
        entry = entries[0]
        return SessionOpenReceipt(
            kind=entry.kind,
            key=entry.key,
            argv=entry.reopen_argv,
        )

    monkeypatch.setattr(sever_command, "choose_session", change_then_select)

    with pytest.raises(ValueError, match="changed while the list was open"):
        sever_command._choose_saved_sever_session(sessions)


def test_shared_sever_picker_new_receipt_enters_setup_path(
    isolated_store,
    monkeypatch,
):
    sessions = SeverSessionStore(MemoryStore())
    monkeypatch.setattr(
        sever_command,
        "choose_session",
        lambda entries, **kwargs: SessionNewReceipt(
            kind="sever",
            argv=("mem", "sever"),
        ),
    )

    action, session = sever_command._choose_saved_sever_session(sessions)

    assert action == "NEW"
    assert session is None


def test_sessions_sever_opens_a_selected_saved_session_without_provider_call(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _context(store, "source", "Source")
    criteria = _context(store, "criteria", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="draft",
        provider_factory=lambda: SeverProvider(),
    )
    SeverSessionStore(store).save(session, expected_digest=None)
    monkeypatch.setattr(sever_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        sever_command,
        "_choose_saved_sever_session",
        lambda sessions: ("OPEN", session),
    )
    monkeypatch.setattr(
        sever_command,
        "_run_workbench",
        lambda store, selected: selected,
    )
    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(AssertionError("provider called")),
    )

    result = runner.invoke(app, ["sever", "--sessions"])

    assert result.exit_code == 0, result.output
    assert f"SESSION · {session.uid}" in result.output
    assert f"IMPACT · mem impact sever --session {session.uid}" in result.output
    assert "SEVER READY · source → draft" in result.output


def test_bare_sever_enters_setup_without_session_launcher(
    isolated_store,
    monkeypatch,
):
    setup_calls = []
    monkeypatch.setattr(sever_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        sever_command,
        "_choose_saved_sever_session",
        lambda _sessions: pytest.fail("bare Sever must not browse saved sessions"),
    )
    monkeypatch.setattr(
        sever_command,
        "_interactive_setup",
        lambda store: setup_calls.append(store) or None,
    )

    result = runner.invoke(app, ["sever"])

    assert result.exit_code == 0, result.output
    assert len(setup_calls) == 1
    assert "Sever setup cancelled" in result.output


def test_non_tty_sever_sessions_retains_plain_listing(
    isolated_store,
):
    store = MemoryStore()
    source = _context(store, "source", "Source")
    criteria = _context(store, "criteria", "Criterion")
    session = sever_command._start(
        store=store,
        source_name=source.name,
        criteria_name=criteria.name,
        output_name="draft",
        provider_factory=lambda: SeverProvider(),
    )
    SeverSessionStore(store).save(session, expected_digest=None)

    result = runner.invoke(app, ["sever", "--sessions"])

    assert result.exit_code == 0, result.output
    assert session.uid in result.output
    assert "source × criteria → draft" in result.output
