"""Shared existing-Context operand and terminal-label boundaries."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.impact import command as impact_command
from memcommit.commands.review import command as review_command
from memcommit.commands.compare.command import display_escape_text as compare_escape
from memcommit.commands.shared.context_picker import (
    _build_context_tree,
    _context_ancestors,
    _render_context_options,
    _visible_context_rows,
    choose_context,
)
from memcommit.commands.profile.picker import (
    ProfilePickerEntry,
    _render_profile_options,
    choose_profile,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context import AutoCheckpoint
from memcommit.findings import AmbiguityReport, ConflictReport, DuplicateReport
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _persist_relative_pair():
    store = MemoryStore()
    current = ops.init("scope/from")
    store.save(current)
    target = ops.init("scope/to")
    memory = ops.add(target, "Target evidence.")
    store.save(
        target,
        AutoCheckpoint(
            command="test setup",
            args={"context": target.name},
            description="Created target evidence",
        ),
    )
    store.set_current(current.name)
    return store, current, target, memory


def _count_current_reads(monkeypatch):
    original = MemoryStore.current_context_name
    calls: list[str | None] = []

    def counted(store):
        value = original(store)
        calls.append(value)
        return value

    monkeypatch.setattr(MemoryStore, "current_context_name", counted)
    return calls


def test_read_and_analysis_commands_share_relative_context_operand_boundary(
    isolated_store,
    monkeypatch,
):
    _store, _current, target, memory = _persist_relative_pair()
    current_reads = _count_current_reads(monkeypatch)

    monkeypatch.setattr(
        "memcommit.commands.find.command.connect_codex_chatgpt_provider",
        lambda: object(),
    )
    monkeypatch.setattr(
        "memcommit.operations.search.application.rank_candidates",
        lambda *_args, **_kwargs: [],
    )

    monkeypatch.setattr(
        "memcommit.commands.find_ambiguities.command.ops.find_ambiguities",
        lambda context, *_args, **_kwargs: AmbiguityReport(
            memory_count=len(context.memories),
            findings=(),
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.find_duplicates.command.ops.find_redundancies",
        lambda context, *_args, **_kwargs: DuplicateReport(
            memory_count=len(context.memories),
            findings=(),
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.find_conflicts.command.ops.find_conflicts",
        lambda context, *_args, **_kwargs: ConflictReport(
            memory_count=len(context.memories),
            pair_count=0,
            findings=(),
        ),
    )

    invocations = (
        ["show", memory.uid, "--context", "../to"],
        ["trace", memory.uid, "--context", "../to"],
        [
            "rationale",
            memory.uid,
            "--context",
            "../to",
        ],
        ["find", "evidence", "--context", "../to"],
        ["find-ambiguities", "--context", "../to"],
        ["dedun", "--context", "../to"],
        ["find-conflicts", "--context", "../to"],
    )

    results = [runner.invoke(app, argv) for argv in invocations]

    assert all(result.exit_code == 0 for result in results), [
        result.output for result in results
    ]
    assert all(target.name in result.output for result in results)
    assert current_reads == ["scope/from"] * len(invocations)


def test_query_resolves_only_ordinary_parent_context_operand(
    isolated_store,
    monkeypatch,
):
    store, _current, target, _memory = _persist_relative_pair()
    source = store.create_query_source("opaque-source", "Concealed evidence.")
    parent = store.load_direct(target.name)
    ops.reference_query_context("opaque-source", source.uid, parent)
    store.save(parent)
    current_reads = _count_current_reads(monkeypatch)
    calls: list[tuple[str, str, str]] = []

    class Provider:
        def query(self, source_name, source_content, question):
            calls.append((source_name, source_content, question))
            return "Grounded answer."

    monkeypatch.setattr(
        "memcommit.commands.query.command.connect_query_provider",
        lambda _provider: Provider(),
    )

    result = runner.invoke(
        app,
        [
            "query",
            "opaque-source",
            "What is known?",
            "--context",
            "../to",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "Grounded answer.\n"
    assert calls == [("opaque-source", "Concealed evidence.", "What is known?")]
    assert current_reads == ["scope/from"]


def test_review_and_unary_impact_canonicalize_before_stateful_helpers(
    isolated_store,
    monkeypatch,
):
    _persist_relative_pair()
    current_reads = _count_current_reads(monkeypatch)
    observed: list[tuple[str, str]] = []

    def capture_review(**kwargs):
        observed.append(("review", kwargs["context_name"]))

    def capture_impact(**kwargs):
        observed.append(("impact", kwargs["context_name"]))

    monkeypatch.setattr(
        review_command,
        "_run_atomize_workbench",
        capture_review,
    )
    monkeypatch.setattr(impact_command, "_atomize_impact", capture_impact)

    review = runner.invoke(
        app,
        ["review", "atomize", "--context", "../to"],
    )
    impact = runner.invoke(
        app,
        ["impact", "atomize", "--context", "../to"],
    )

    assert review.exit_code == 0, review.output
    assert impact.exit_code == 0, impact.output
    assert observed == [
        ("review", "scope/to"),
        ("impact", "scope/to"),
    ]
    assert current_reads == ["scope/from", "scope/from"]


def _visible_text(fragments: list[tuple[str, str]]) -> str:
    return "".join(text for style, text in fragments if style != "[SetCursorPosition]")


def test_context_picker_escapes_labels_but_returns_raw_identity():
    raw_name = "scope/target\u202e\\name"
    tree = _build_context_tree((raw_name,))
    rendered = _visible_text(
        _render_context_options(
            _visible_context_rows(tree, _context_ancestors(tree, raw_name)),
            selected=raw_name,
            current=raw_name,
        )
    )

    assert raw_name not in rendered
    assert r"scope/target\u202e\\name" in rendered
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_context(
            (raw_name,),
            current=raw_name,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert selected == raw_name


def test_context_catalog_uses_escaped_labels_with_raw_current_identity(
    isolated_store,
    monkeypatch,
):
    raw_name = "scope/current\u202e"
    calls: list[str] = []

    def current_name(_store):
        calls.append("current")
        return raw_name

    monkeypatch.setattr(MemoryStore, "current_context_name", current_name)
    monkeypatch.setattr(
        MemoryStore,
        "list_context_names",
        lambda _store: [raw_name, "safe"],
    )

    result = runner.invoke(app, ["contexts"])

    assert result.exit_code == 0, result.output
    assert raw_name not in result.output
    assert r"* scope/current\u202e" in result.output
    assert calls == ["current"]


def test_profile_picker_escapes_metadata_but_returns_raw_identity():
    raw_name = "profile\u202e"
    entry = ProfilePickerEntry(
        name=raw_name,
        context_count=1,
        current_context="scope\ncurrent",
        query_source_count=1,
        query_source_names=("query\tname",),
    )
    rendered = _visible_text(
        _render_profile_options((entry,), selected=0, current=raw_name)
    )

    assert raw_name not in rendered
    assert r"profile\u202e" in rendered
    assert r"current=scope\ncurrent" in rendered
    assert r"query=query\tname" in rendered
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_profile(
            (entry,),
            current=raw_name,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert selected is not None
    assert selected.kind == "USE"
    assert selected.name == raw_name


def test_compare_uses_the_shared_injective_display_escaper():
    assert compare_escape is display_escape_text
    assert compare_escape("line\n\x07\u202e") == r"line\n\x07\u202e"


@pytest.mark.parametrize(
    "command",
    (
        ("atomize",),
        ("impact", "atomize"),
        ("audit",),
        ("dedun",),
        ("find-ambiguities",),
        ("find-duplicates",),
        ("find-redundancies",),
        ("find-conflicts",),
    ),
)
def test_unary_context_position_and_option_cannot_compete(
    isolated_store,
    command,
):
    result = runner.invoke(app, [*command, "one", "--context", "two"])

    assert result.exit_code == 2
    assert "both positionally and with --context" in result.stderr


def test_impact_update_positionals_require_the_complete_pair(
    isolated_store,
):
    result = runner.invoke(app, ["impact", "update", "source-only"])

    assert result.exit_code == 2
    assert "exactly SOURCE TARGET" in result.stderr


def test_update_single_positional_is_the_source_with_current_target(
    isolated_store,
):
    result = runner.invoke(app, ["update", "source-only"])

    assert result.exit_code == 1
    assert "No current target Context" in result.stderr


@pytest.mark.parametrize("command", (("update",), ("impact", "update")))
def test_directional_positionals_cannot_mix_with_endpoint_options(
    isolated_store,
    command,
):
    result = runner.invoke(
        app,
        [*command, "source", "target", "--to", "other"],
    )

    assert result.exit_code == 2
    assert "cannot be combined with --from or --to" in result.stderr
