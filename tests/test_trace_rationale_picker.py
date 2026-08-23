"""Bare-command picker contracts for ``mem trace`` and ``mem rationale``."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.memory_report_recents import (
    MemoryReportRecentSelection,
    MemoryReportSelectAction,
)
from memcommit.commands.memory_picker import MemoryReportTargetSelection
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


def _target_selection(
    root: str,
    owner: str,
    memory_uid: str,
    *,
    include_descendants: bool = False,
) -> MemoryReportTargetSelection:
    return MemoryReportTargetSelection(
        root_context_name=root,
        owner_context_name=owner,
        memory_uid=memory_uid,
        include_descendants=include_descendants,
    )


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
        initial_include_descendants,
        **kwargs,
    ):
        observed["items"] = [(item.uid, item.status) for item in items]
        observed["context_name"] = context_name
        observed["operation"] = operation
        return _target_selection(context_name, context_name, target.uid)

    monkeypatch.setattr(
        "memcommit.commands.trace.choose_memory_report_target",
        select,
    )

    result = invoke("trace", "--plain")

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
        "memcommit.commands.rationale.choose_memory_report_target",
        lambda items, *, context_name, operation, initial_include_descendants, **kwargs: (
            _target_selection(context_name, context_name, target.uid)
        ),
    )
    result = invoke("rationale")

    assert result.exit_code == 0, result.output
    assert "Rationale [" in result.output
    assert "portable note" in result.output
    assert "PROVENANCE\n" in result.output
    assert "retained" in result.output
    assert "APPARENT PURPOSE" not in result.output


def test_trace_descendant_range_opens_the_selected_owner_history(
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
        initial_include_descendants,
        **kwargs,
    ):
        observed["rows"] = [
            (item.context_name, item.uid, item.change_count) for item in items
        ]
        return _target_selection(
            context_name,
            "notes/child",
            target.uid,
            include_descendants=True,
        )

    monkeypatch.setattr(
        "memcommit.commands.trace.choose_memory_report_target",
        select,
    )

    result = invoke("trace", "--plain")

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
        initial_include_descendants,
        **kwargs,
    ):
        observed["context_name"] = context_name
        observed["operation"] = operation
        observed["items"] = [(item.context_name, item.content) for item in items]
        return _target_selection(
            context_name,
            "notes/child",
            child_target.uid,
            include_descendants=True,
        )

    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory_report_target",
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


def test_interactive_rationale_returns_terminal_receipt_without_viewer(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]
    monkeypatch.setattr(
        "memcommit.commands.rationale.interactive_report_terminal",
        lambda: True,
    )

    result = invoke("rationale", target.uid)

    assert result.exit_code == 0, result.output
    assert "Rationale [" in result.output
    assert "portable note" in result.output
    assert "RATIONALE REPORT" not in result.output


def test_interactive_trace_opens_vertical_viewer_only_when_requested(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]
    viewed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "memcommit.commands.trace.interactive_report_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.trace.open_trace_viewer",
        lambda report, *, verbose, limit: viewed.append(
            (report.context_name, report.selected_uid)
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.trace.choose_memory_report_target",
        lambda items, *, context_name, operation, initial_include_descendants, **kwargs: (
            _target_selection(context_name, context_name, target.uid)
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.trace.choose_memory_report_recent",
        lambda store, *, operation: MemoryReportSelectAction(),
    )
    bare = invoke("trace")
    explicit = invoke("trace", target.uid)
    explicit_tui = invoke("trace", target.uid, "--tui")

    assert bare.exit_code == 0, bare.output
    assert explicit.exit_code == 0, explicit.output
    assert explicit_tui.exit_code == 0, explicit_tui.output
    assert "TRACE · notes" in bare.output
    assert "TRACE · notes" in explicit.output
    assert viewed == [("notes", target.uid)]


def test_bare_trace_recent_reopens_without_context_memory_selector(
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
        "memcommit.commands.trace.choose_memory_report_recent",
        lambda store, *, operation: MemoryReportRecentSelection(
            context_name="notes",
            memory_uid=target.uid,
            include_descendants=False,
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.trace.choose_memory_report_target",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("a recent receipt must bypass fresh selection")
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.trace.open_trace_viewer",
        lambda report, *, verbose, limit: viewed.append(report.current[0].content),
    )

    result = invoke("trace", "--tui")

    assert result.exit_code == 0, result.output
    assert len(viewed) == 1
    assert viewed == ["portable note"]


def test_bare_rationale_recent_reopens_its_recorded_scope(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]
    monkeypatch.setattr(
        "memcommit.commands.rationale.interactive_report_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory_report_recent",
        lambda store, *, operation: MemoryReportRecentSelection(
            context_name="notes",
            memory_uid=target.uid,
            include_descendants=True,
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory_report_target",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("a recent receipt must bypass fresh selection")
        ),
    )
    result = invoke("rationale")

    assert result.exit_code == 0, result.output
    assert "portable note" in result.output
    assert "retained" in result.output


def test_bare_rationale_cancel_returns_without_report(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory_report_target",
        lambda items, *, context_name, operation, initial_include_descendants, **kwargs: None,
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
        "memcommit.commands.trace.choose_memory_report_target",
        cancel_target,
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory_report_target",
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
        "memcommit.commands.trace.choose_memory_report_target",
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
        "memcommit.commands.rationale.choose_memory_report_target",
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
        "memcommit.commands.trace.choose_memory_report_target",
        unexpected,
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory_report_target",
        unexpected,
    )

    trace = invoke("trace", target.uid[:8])
    rationale = invoke("rationale", target.uid[:8])

    assert trace.exit_code == 0, trace.output
    assert rationale.exit_code == 0, rationale.output


def test_explicit_context_bypasses_recents_and_uses_exact_picker_root(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0
    target = _direct_memories(MemoryStore())[0]

    def unexpected(*args, **kwargs):
        raise AssertionError("an explicit Context must bypass global launchers")

    monkeypatch.setattr(
        "memcommit.commands.trace.choose_memory_report_recent",
        unexpected,
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory_report_recent",
        unexpected,
    )
    observed_roots: dict[str, str] = {}

    def select_trace(items, *, context_name, **kwargs):
        observed_roots["trace"] = context_name
        return _target_selection(context_name, context_name, target.uid)

    def select_rationale(items, *, context_name, **kwargs):
        observed_roots["rationale"] = context_name
        return _target_selection(context_name, context_name, target.uid)

    monkeypatch.setattr(
        "memcommit.commands.trace.choose_memory_report_target",
        select_trace,
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory_report_target",
        select_rationale,
    )

    trace = invoke("trace", "--context", ".")
    rationale = invoke(
        "rationale",
        "--context",
        ".",
    )

    assert trace.exit_code == 0, trace.output
    assert rationale.exit_code == 0, rationale.output
    assert observed_roots == {"trace": "notes", "rationale": "notes"}


def test_bare_json_requires_an_explicit_selector(isolated_store, monkeypatch):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "portable note").exit_code == 0

    def unexpected(*args, **kwargs):
        raise AssertionError("bare JSON output must not open a picker")

    monkeypatch.setattr(
        "memcommit.commands.trace.choose_memory_report_target",
        unexpected,
    )
    monkeypatch.setattr(
        "memcommit.commands.rationale.choose_memory_report_target",
        unexpected,
    )

    trace = invoke("trace", "--json")
    rationale = invoke("rationale", "--json")

    assert trace.exit_code == 1
    assert rationale.exit_code == 1
    assert "requires an explicit item UID" in trace.output
    assert "requires an explicit item UID" in rationale.output


def test_command_help_marks_memory_selector_as_optional():
    trace = invoke("trace", "--help")
    rationale = invoke("rationale", "--help")

    assert trace.exit_code == 0
    assert rationale.exit_code == 0
    assert "[SELECTOR]" in trace.output
    assert "[SELECTOR]" in rationale.output
    assert "select from the current Context" in " ".join(trace.output.split())
    assert "select from the current readable Context" in " ".join(
        rationale.output.split()
    )
    assert "descendants" in trace.output
    assert "descendants" in rationale.output


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
