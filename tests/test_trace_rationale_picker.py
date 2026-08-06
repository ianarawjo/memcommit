"""Bare-command picker contracts for ``mem trace`` and ``mem rationale``."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Memory, MemoryRef, QueryContextRef
from memcommit.provenance import collect_trace_candidates
from memcommit.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def _direct_memories(store: MemoryStore) -> list[Memory]:
    return [
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    ]


def test_candidate_catalog_lists_current_then_historical_once(isolated_store):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "kept").exit_code == 0
    assert invoke("add", "removed").exit_code == 0
    store = MemoryStore()
    kept, removed = _direct_memories(store)
    assert invoke("edit", kept.uid, "kept revision").exit_code == 0
    assert invoke("remove", removed.uid).exit_code == 0

    candidates = collect_trace_candidates(
        store,
        store.load_current_direct(),
    )

    assert [(item.uid, item.status, item.content) for item in candidates] == [
        (kept.uid, "CURRENT", "kept revision"),
        (removed.uid, "HISTORICAL", "removed"),
    ]


def test_bare_trace_runs_existing_report_for_picker_uid(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "temporary").exit_code == 0
    store = MemoryStore()
    target = _direct_memories(store)[0]
    assert invoke("remove", target.uid).exit_code == 0
    observed: dict[str, object] = {}

    def select(items, *, context_name, operation):
        observed["items"] = [(item.uid, item.status) for item in items]
        observed["context_name"] = context_name
        observed["operation"] = operation
        return target.uid

    monkeypatch.setattr("memcommit.commands.trace.choose_memory", select)

    result = invoke("trace")

    assert result.exit_code == 0, result.output
    assert observed == {
        "items": [(target.uid, "HISTORICAL")],
        "context_name": "notes",
        "operation": "trace",
    }
    assert "REMOVED" in result.output
    assert "temporary" in result.output


def test_bare_recorded_rationale_selects_before_any_provider_call(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory",
        lambda items, *, context_name, operation: target.uid,
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("--recorded-only must not connect a provider")
        ),
    )

    result = invoke("rationale", "--recorded-only")

    assert result.exit_code == 0, result.output
    assert "Rationale for" in result.output
    assert "portable note" in result.output


def test_rationale_picker_groups_memories_under_their_public_context(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "root note").exit_code == 0
    assert invoke("init", "notes/child").exit_code == 0
    assert invoke("add", "child note").exit_code == 0
    child_target = _direct_memories(MemoryStore())[0]
    assert invoke("switch", "notes").exit_code == 0
    observed: dict[str, object] = {}

    def select(items, *, context_name, operation):
        observed["context_name"] = context_name
        observed["operation"] = operation
        observed["items"] = [(item.context_name, item.content) for item in items]
        return child_target.uid

    monkeypatch.setattr("memcommit.commands.rationale.choose_memory", select)

    result = invoke("rationale", "--recorded-only")

    assert result.exit_code == 0, result.output
    assert observed == {
        "context_name": "notes",
        "operation": "rationale",
        "items": [
            ("notes", "root note"),
            ("notes/child", "child note"),
        ],
    }


def test_interactive_rationale_report_uses_common_viewer(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]
    observed: dict[str, str] = {}
    monkeypatch.setattr(
        "memcommit.commands.rationale.interactive_report_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.run_read_only_viewer",
        lambda text, *, title: observed.update(text=text, title=title),
    )

    result = invoke("rationale", target.uid, "--recorded-only")

    assert result.exit_code == 0, result.output
    assert observed["title"] == "RATIONALE REPORT"
    assert "Rationale for" in observed["text"]
    assert "portable note" in observed["text"]


def test_only_bare_interactive_trace_continues_into_common_viewer(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]
    viewed: list[str] = []
    monkeypatch.setattr(
        "memcommit.commands.trace.interactive_report_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.trace.run_read_only_viewer",
        lambda text, *, title: viewed.append(f"{title}\n{text}"),
    )
    monkeypatch.setattr(
        "memcommit.commands.trace.choose_memory",
        lambda items, *, context_name, operation: target.uid,
    )

    bare = invoke("trace")
    explicit = invoke("trace", target.uid)

    assert bare.exit_code == 0, bare.output
    assert explicit.exit_code == 0, explicit.output
    assert len(viewed) == 1
    assert viewed[0].startswith("TRACE REPORT\n")
    assert "portable note" in viewed[0]
    assert "portable note" in explicit.output


def test_bare_rationale_cancel_never_connects_provider(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory",
        lambda items, *, context_name, operation: None,
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("cancelled rationale must not connect a provider")
        ),
    )

    result = invoke("rationale")

    assert result.exit_code == 0, result.output
    assert "Rationale cancelled." in result.output


def test_bare_commands_require_tty_instead_of_auto_selecting(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    monkeypatch.setattr(
        "memcommit.commands.rationale.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("non-TTY rationale must not connect a provider")
        ),
    )

    trace = invoke("trace")
    rationale = invoke("rationale")

    assert trace.exit_code == 1
    assert rationale.exit_code == 1
    assert "requires a terminal" in trace.output
    assert "requires a terminal" in rationale.output


def test_bare_commands_report_an_empty_context_before_opening_picker(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "empty").exit_code == 0
    monkeypatch.setattr(
        "memcommit.commands.rationale.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("empty rationale must not connect a provider")
        ),
    )

    trace = invoke("trace")
    rationale = invoke("rationale")

    assert trace.exit_code == 1
    assert rationale.exit_code == 1
    assert "No current or retained historical" in trace.output
    assert "No current or retained historical" in rationale.output


def test_explicit_selectors_bypass_picker(isolated_store, monkeypatch):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]

    def unexpected(*args, **kwargs):
        raise AssertionError("an explicit selector must not open the picker")

    monkeypatch.setattr("memcommit.commands.trace.choose_memory", unexpected)
    monkeypatch.setattr("memcommit.commands.rationale.choose_memory", unexpected)

    trace = invoke("trace", target.uid[:8])
    rationale = invoke("rationale", target.uid[:8], "--recorded-only")

    assert trace.exit_code == 0, trace.output
    assert rationale.exit_code == 0, rationale.output


def test_bare_json_requires_an_explicit_selector(isolated_store, monkeypatch):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0

    def unexpected(*args, **kwargs):
        raise AssertionError("bare JSON output must not open a picker")

    monkeypatch.setattr("memcommit.commands.trace.choose_memory", unexpected)
    monkeypatch.setattr("memcommit.commands.rationale.choose_memory", unexpected)

    trace = invoke("trace", "--json")
    rationale = invoke("rationale", "--json")

    assert trace.exit_code == 1
    assert rationale.exit_code == 1
    assert "requires an explicit Memory UID" in trace.output
    assert "requires an explicit Memory UID" in rationale.output


def test_command_help_marks_memory_selector_as_optional():
    trace = invoke("trace", "--help")
    rationale = invoke("rationale", "--help")

    assert trace.exit_code == 0
    assert rationale.exit_code == 0
    assert "[SELECTOR]" in trace.output
    assert "[SELECTOR]" in rationale.output
    assert "omit to enter" in trace.output
    assert "omit to enter" in rationale.output


def test_candidate_catalog_never_opens_refs_or_query_only_sources(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("privacy")
    ordinary = Memory(uid="ordinary", content="Visible ordinary Memory")
    ctx.add(ordinary)
    ctx.add(
        MemoryRef(
            uid="ref",
            target_context_uid="secret-context",
            target_context_name="secret",
            target_memory_uid="secret-memory",
            target=Memory(uid="secret-memory", content="SECRET REF CONTENT"),
        )
    )
    ctx.add(
        QueryContextRef(
            uid="query",
            name="restricted-contracts",
            target_source_uid="secret-source",
            provider="codex_chatgpt",
        )
    )
    store.save(ctx)

    def forbidden(*args, **kwargs):
        raise AssertionError("picker catalog opened concealed or referenced content")

    monkeypatch.setattr(MemoryStore, "_load_direct_memory", forbidden)
    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)

    candidates = collect_trace_candidates(store, store.load_direct("privacy"))

    assert [(item.uid, item.content) for item in candidates] == [
        (ordinary.uid, ordinary.content)
    ]
    assert "SECRET REF CONTENT" not in repr(candidates)
