"""Bare-command picker contracts for ``mem trace`` and ``mem rationale``."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory, MemoryRef, QueryContextRef
from memcommit.core.context_targeting.model import ContextTarget, DirectMemoryTarget
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    collect_memory_history_candidates,
)
from memcommit.application.capabilities.reviewing.read_report_recents import (
    read_report_recents,
)
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def _direct_memories(store: MemoryStore) -> list[Memory]:
    return [
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    ]


def _memory_target(owner: str, memory_uid: str) -> DirectMemoryTarget:
    return DirectMemoryTarget(context_name=owner, selector=memory_uid)


def test_candidate_catalog_lists_current_then_historical_once(isolated_store):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "kept").exit_code == 0
    assert invoke("add", "removed").exit_code == 0
    store = MemoryStore()
    kept, removed = _direct_memories(store)
    assert invoke("edit", kept.uid, "kept revision").exit_code == 0
    assert invoke("remove", removed.uid).exit_code == 0

    candidates = collect_memory_history_candidates(
        store,
        store.load_current_direct(),
    )

    assert [(item.uid, item.status, item.content) for item in candidates] == [
        (kept.uid, "CURRENT", "kept revision"),
        (removed.uid, "HISTORICAL", "removed"),
    ]
    assert [item.change_count for item in candidates] == [2, 2]


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

    def select(
        items,
        *,
        context_name,
        operation,
        **kwargs,
    ):
        observed["items"] = [(item.uid, item.status) for item in items]
        observed["context_name"] = context_name
        observed["operation"] = operation
        return _memory_target(context_name, target.uid)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.trace.command.choose_history_report_target",
        select,
    )

    result = invoke("trace")

    assert result.exit_code == 0, result.output
    assert observed == {
        "items": [(target.uid, "HISTORICAL")],
        "context_name": "notes",
        "operation": "trace",
    }
    assert "[remove] [CHECKPOINT " in result.output
    assert 'removed "temporary"' in result.output
    assert "temporary" in result.output


def test_bare_rationale_selects_provenance_target(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.choose_history_report_target",
        lambda items,
        *,
        context_name,
        operation,
        **kwargs: (_memory_target(context_name, target.uid)),
    )
    result = invoke("rationale")

    assert result.exit_code == 0, result.output
    assert "Rationale [" in result.output
    assert "portable note" in result.output
    assert "PROVENANCE\n" in result.output
    assert "retained" in result.output
    assert "APPARENT PURPOSE" not in result.output


def test_trace_browser_opens_the_selected_owner_history(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("init", "notes/child").exit_code == 0
    assert invoke("add", "first child wording").exit_code == 0
    store = MemoryStore()
    target = _direct_memories(store)[0]
    assert invoke("edit", target.uid, "current child wording").exit_code == 0
    assert invoke("switch", "notes").exit_code == 0
    observed: dict[str, object] = {}

    def select(
        items,
        *,
        context_name,
        operation,
        **kwargs,
    ):
        observed["rows"] = [
            (item.context_name, item.uid, item.change_count) for item in items
        ]
        return _memory_target("notes/child", target.uid)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.trace.command.choose_history_report_target",
        select,
    )

    result = invoke("trace")

    assert result.exit_code == 0, result.output
    assert observed["rows"] == [("notes/child", target.uid, 2)]
    assert "TRACE" in result.output
    assert "current child wording" in result.output


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

    def select(
        items,
        *,
        context_name,
        operation,
        **kwargs,
    ):
        observed["context_name"] = context_name
        observed["operation"] = operation
        observed["items"] = [(item.context_name, item.content) for item in items]
        return _memory_target("notes/child", child_target.uid)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.choose_history_report_target",
        select,
    )

    result = invoke("rationale")

    assert result.exit_code == 0, result.output
    assert observed == {
        "context_name": "notes",
        "operation": "rationale",
        "items": [
            ("notes", "root note"),
            ("notes/child", "child note"),
        ],
    }
    assert "PROVENANCE\n" in result.output
    assert "retained" in result.output
    assert "APPARENT PURPOSE" not in result.output


def test_rationale_returns_terminal_receipt_without_viewer(
    isolated_store,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]
    result = invoke("rationale", target.uid)

    assert result.exit_code == 0, result.output
    assert "Rationale [" in result.output
    assert "portable note" in result.output
    assert "RATIONALE REPORT" not in result.output


def test_trace_selector_prints_one_lineage_and_rejects_retired_tui(isolated_store):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]
    explicit = invoke("trace", target.uid)
    explicit_tui = invoke("trace", target.uid, "--tui")

    assert explicit.exit_code == 0, explicit.output
    assert explicit_tui.exit_code == 2
    assert "TRACE · notes" in explicit.output
    assert "portable note" in explicit.output
    assert "No such option: --tui" in explicit_tui.output


def test_bare_trace_browser_can_select_an_exact_context(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.trace.command.choose_history_report_target",
        lambda *args, **kwargs: ContextTarget("notes"),
    )
    result = invoke("trace")

    assert result.exit_code == 0, result.output
    assert "TRACE · notes" in result.output
    assert "[CONTEXT]" in result.output
    assert "portable note" in result.output


def test_bare_rationale_browser_can_select_an_exact_context(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.choose_history_report_target",
        lambda *args, **kwargs: ContextTarget("notes"),
    )

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            return '{"provenance":"The retained Add created this Context state."}'

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.connect_semantic_provider",
        Provider,
    )
    result = invoke("rationale")

    assert result.exit_code == 0, result.output
    assert "Rationale · notes" in result.output
    assert "retained Add" in result.output


def test_bare_rationale_cancel_returns_without_report(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.choose_history_report_target",
        lambda items,
        *,
        context_name,
        operation,
        **kwargs: None,
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
    trace = invoke("trace")
    rationale = invoke("rationale")

    assert trace.exit_code == 1
    assert rationale.exit_code == 1
    assert "requires a terminal" in trace.output
    assert "requires a terminal" in rationale.output


def test_bare_commands_open_empty_current_memory_tree_before_cancelling(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "empty").exit_code == 0
    observed: list[tuple[str, str, tuple[str, ...], tuple[object, ...]]] = []

    def cancel_target(
        items,
        *,
        context_name,
        operation,
        catalog_context_names,
        **kwargs,
    ):
        observed.append(
            (
                operation,
                context_name,
                tuple(catalog_context_names),
                tuple(items),
            )
        )
        return None

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.trace.command.choose_history_report_target",
        cancel_target,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.choose_history_report_target",
        cancel_target,
    )

    trace = invoke("trace")
    rationale = invoke("rationale")

    assert trace.exit_code == 0, trace.output
    assert rationale.exit_code == 0, rationale.output
    assert "Trace cancelled." in trace.output
    assert "Rationale cancelled." in rationale.output
    assert observed == [
        ("trace", "empty", ("empty",), ()),
        ("rationale", "empty", ("empty",), ()),
    ]


def test_bare_trace_does_not_browse_away_from_empty_current_context(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "empty").exit_code == 0
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "trace me").exit_code == 0
    store = MemoryStore()
    assert invoke("switch", "empty").exit_code == 0
    observed: dict[str, object] = {}

    def cancel_target(items, *, context_name, catalog_context_names, **kwargs):
        observed["root"] = context_name
        observed["catalog"] = tuple(catalog_context_names)
        observed["items"] = tuple(items)
        return None

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.trace.command.choose_history_report_target",
        cancel_target,
    )

    result = invoke("trace")

    assert result.exit_code == 0, result.output
    assert observed == {"root": "empty", "catalog": ("empty",), "items": ()}
    assert "Trace cancelled." in result.output
    assert store.current_context_name() == "empty"


def test_bare_rationale_does_not_browse_away_from_empty_current_context(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "empty").exit_code == 0
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "explain me").exit_code == 0
    store = MemoryStore()
    assert invoke("switch", "empty").exit_code == 0
    observed: dict[str, object] = {}

    def cancel_target(items, *, context_name, catalog_context_names, **kwargs):
        observed["root"] = context_name
        observed["catalog"] = tuple(catalog_context_names)
        observed["items"] = tuple(items)
        return None

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.choose_history_report_target",
        cancel_target,
    )
    result = invoke("rationale")

    assert result.exit_code == 0, result.output
    assert observed == {"root": "empty", "catalog": ("empty",), "items": ()}
    assert "Rationale cancelled." in result.output
    assert store.current_context_name() == "empty"


def test_explicit_selectors_bypass_picker(isolated_store, monkeypatch):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]

    def unexpected(*args, **kwargs):
        raise AssertionError("an explicit selector must not open the picker")

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.trace.command.choose_history_report_target",
        unexpected,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.choose_history_report_target",
        unexpected,
    )

    trace = invoke("trace", target.uid[:8])
    rationale = invoke("rationale", target.uid[:8])

    assert trace.exit_code == 0, trace.output
    assert rationale.exit_code == 0, rationale.output


def test_context_option_bypasses_browser_and_runs_exact_context_report(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0

    def unexpected(*args, **kwargs):
        raise AssertionError("an explicit Context must bypass the browser")

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.trace.command.choose_history_report_target",
        unexpected,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.choose_history_report_target",
        unexpected,
    )

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            return '{"provenance":"The retained Add created this Context state."}'

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.connect_semantic_provider",
        Provider,
    )

    trace = invoke("trace", "--context", ".")
    rationale = invoke(
        "rationale",
        "--context",
        ".",
    )

    assert trace.exit_code == 0, trace.output
    assert rationale.exit_code == 0, rationale.output
    assert "TRACE · notes" in trace.output
    assert "[CONTEXT]" in trace.output
    assert "Rationale · notes" in rationale.output


def test_context_option_rejects_a_positional_memory_selector(isolated_store):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]

    trace = invoke("trace", target.uid, "--context", "notes")
    rationale = invoke("rationale", target.uid, "--context", "notes")

    assert trace.exit_code == 1
    assert rationale.exit_code == 1
    assert "--context selects a Context" in trace.output
    assert "--context selects a Context" in rationale.output
    assert "CONTEXT:UID" in trace.output
    assert "CONTEXT:UID" in rationale.output


def test_context_option_is_an_explicit_json_target(isolated_store, monkeypatch):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            return '{"provenance":"The retained Add created this Context state."}'

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.connect_semantic_provider",
        Provider,
    )

    trace = invoke("trace", "--context", "notes", "--json")
    rationale = invoke("rationale", "--context", "notes", "--json")

    assert trace.exit_code == 0, trace.output
    assert rationale.exit_code == 0, rationale.output
    assert '"target": "CONTEXT"' in trace.output
    assert '"target": "CONTEXT"' in rationale.output


def test_trace_rationale_and_memory_log_do_not_publish_recents(isolated_store):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]

    assert invoke("trace", target.uid).exit_code == 0
    assert invoke("rationale", target.uid).exit_code == 0
    assert invoke("log", "--memory", target.uid).exit_code == 0

    store = MemoryStore()
    assert read_report_recents(store, operation="trace") == ()
    assert read_report_recents(store, operation="rationale") == ()


def test_bare_json_requires_an_explicit_selector(isolated_store, monkeypatch):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0

    def unexpected(*args, **kwargs):
        raise AssertionError("bare JSON output must not open a picker")

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.trace.command.choose_history_report_target",
        unexpected,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.choose_history_report_target",
        unexpected,
    )

    trace = invoke("trace", "--json")
    rationale = invoke("rationale", "--json")

    assert trace.exit_code == 1
    assert rationale.exit_code == 1
    assert "requires an explicit Context or Memory target" in trace.output
    assert "requires an explicit Context or Memory target" in rationale.output


def test_command_help_marks_memory_selector_as_optional():
    trace = invoke("trace", "--help")
    rationale = invoke("rationale", "--help")

    assert trace.exit_code == 0
    assert rationale.exit_code == 0
    assert "[SELECTOR]" in trace.output
    assert "[SELECTOR]" in rationale.output
    assert "browse the current local subtree" in " ".join(trace.output.split())
    assert "browse the current readable subtree" in " ".join(
        rationale.output.split()
    )
    assert "Trace this exact Context" in " ".join(trace.output.split())
    assert "Explain this exact Context" in " ".join(rationale.output.split())


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

    candidates = collect_memory_history_candidates(store, store.load_direct("privacy"))

    assert [(item.uid, item.content) for item in candidates] == [
        (ordinary.uid, ordinary.content)
    ]
    assert "SECRET REF CONTENT" not in repr(candidates)
