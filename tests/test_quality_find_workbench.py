"""Shared setup and process-local Resolution contracts for quality finders."""

from __future__ import annotations

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.quality_find_workbench import (
    QualityFindSetupReceipt,
    choose_quality_find_setup,
    run_interactive_quality_find,
    run_quality_find_resolution_workbench,
)
from memcommit.findings import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.quality_find_workbench import (
    QualityFindWorkbenchError,
    create_quality_find_workbench,
    quality_find_resolution_view,
)
from memcommit.store import MemoryStore


runner = CliRunner()


def _context():
    ctx = ops.init("quality/source")
    first = ops.add(ctx, "The main entrance opens at 8:00.")
    second = ops.add(ctx, "The main entrance remains closed until 9:00.")
    return ctx, first, second


def test_flagless_setup_uses_one_common_checked_context_and_explicit_todo():
    with create_pipe_input() as pipe_input:
        # Move the cursor, explicitly check beta, then Tab to the Run action.
        pipe_input.send_text("\x1b[B\r\t\r")
        receipt = choose_quality_find_setup(
            ("alpha", "beta"),
            current="alpha",
            kind="conflicts",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == QualityFindSetupReceipt("beta")


def test_flagless_setup_escape_cancels_without_a_receipt():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        receipt = choose_quality_find_setup(
            ("alpha",),
            current="alpha",
            kind="duplicates",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is None


def test_interactive_orchestration_does_not_analyze_a_cancelled_setup(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _first, _second = _context()
    store.create_context(ctx)
    store.set_current(ctx.name)
    analyzed: list[str] = []

    monkeypatch.setattr(
        "memcommit.commands.quality_find_workbench.choose_quality_find_setup",
        lambda *_args, **_kwargs: None,
    )

    completed = run_interactive_quality_find(
        store,
        current_name=ctx.name,
        kind="conflicts",
        analyze=lambda selected: analyzed.append(selected.name),
    )

    assert completed is False
    assert analyzed == []


def test_ambiguity_projection_keeps_readings_and_process_local_response():
    ctx, first, _second = _context()
    report = AmbiguityReport(
        memory_count=2,
        findings=(
            AmbiguityFinding(
                memory=first,
                interpretation="DOMINANT",
                clarification="REQUIRED",
                ordinary_readings=(
                    "The public main entrance opens at 8:00.",
                    "The staff main entrance opens at 8:00.",
                ),
                reason="The audience of the entrance schedule is unspecified.",
                question="Does this schedule apply to the public or staff entrance?",
            ),
        ),
    )
    session = create_quality_find_workbench("ambiguities", ctx, report)
    initial = quality_find_resolution_view(session, ctx)
    item = initial.items[0]

    assert [option.label for option in item.options] == [
        "DOMINANT",
        "ALTERNATIVE",
    ]
    response = session.response_for(item.uid)
    response.selected_option_uid = item.options[1].uid
    response.text = "It applies to staff."

    updated = quality_find_resolution_view(session, ctx).items[0]
    assert updated.status == "ANSWERED"
    assert updated.selected_option_uid == item.options[1].uid
    assert updated.response_text == "It applies to staff."


def test_conflict_projection_keeps_pair_scope_and_no_fabricated_choices():
    ctx, first, second = _context()
    report = ConflictReport(
        memory_count=2,
        pair_count=1,
        findings=(
            ConflictFinding(
                left=first,
                right=second,
                conflict="YES",
                scope_dimensions=("PLACE", "TIME"),
                reason="Both Memories govern the same entrance at overlapping times.",
                question="Which opening time is authoritative?",
            ),
        ),
    )

    item = quality_find_resolution_view(
        create_quality_find_workbench("conflicts", ctx, report),
        ctx,
    ).items[0]

    assert item.options == ()
    assert item.question == "Which opening time is authoritative?"
    assert item.issue_presentation is not None
    evidence = item.issue_presentation.evidence[0]
    assert [source.content for source in evidence.sources] == [
        first.content,
        second.content,
    ]
    assert evidence.classification == "YES · PLACE · TIME"


def test_duplicate_projection_reviews_emitted_links_without_choosing_survivor():
    ctx, first, second = _context()
    report = DuplicateReport(
        memory_count=2,
        findings=(
            DuplicateFinding(
                left=first,
                right=second,
                relation="SEMANTIC_EQUIVALENT",
                reason="The two Memories are substitutable in this frame.",
            ),
        ),
    )

    item = quality_find_resolution_view(
        create_quality_find_workbench("duplicates", ctx, report),
        ctx,
    ).items[0]

    assert [option.label for option in item.options] == [
        "CONFIRM LINK",
        "REJECT LINK",
        "DEFER",
    ]
    assert all("survivor" not in option.text.casefold() for option in item.options)


def test_process_local_workbench_fails_closed_when_context_changes():
    ctx, first, _second = _context()
    report = DuplicateReport(
        memory_count=2,
        findings=(
            DuplicateFinding(
                left=first,
                right=next(memory for memory in ctx.iter_items() if memory != first),
                relation="SEMANTIC_EQUIVALENT",
                reason="Equivalent.",
            ),
        ),
    )
    session = create_quality_find_workbench("duplicates", ctx, report)
    first.content = "Changed after analysis."

    with pytest.raises(QualityFindWorkbenchError, match="no longer matches"):
        quality_find_resolution_view(session, ctx)


def test_process_local_resolution_shell_can_close_without_mutating_context():
    ctx, _first, _second = _context()
    session = create_quality_find_workbench(
        "ambiguities",
        ctx,
        AmbiguityReport(memory_count=2, findings=()),
    )
    before = ctx.to_dict()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = run_quality_find_resolution_workbench(
            session,
            ctx,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is session
    assert ctx.to_dict() == before


@pytest.mark.parametrize(
    ("module_name", "command_name", "kind"),
    [
        ("find_ambiguities", "find-ambiguities", "ambiguities"),
        ("find_conflicts", "find-conflicts", "conflicts"),
        ("find_duplicates", "find-duplicates", "duplicates"),
    ],
)
def test_flagless_tty_commands_route_to_the_shared_quality_workbench(
    isolated_store,
    monkeypatch,
    module_name,
    command_name,
    kind,
):
    store = MemoryStore()
    ctx, _first, _second = _context()
    store.create_context(ctx)
    store.set_current(ctx.name)
    observed: list[tuple[str | None, str]] = []
    module_path = f"memcommit.commands.{module_name}"

    monkeypatch.setattr(
        f"{module_path}.interactive_quality_find_available",
        lambda: True,
    )
    monkeypatch.setattr(
        f"{module_path}.run_interactive_quality_find",
        lambda _store, *, current_name, kind, analyze: (
            observed.append((current_name, kind)) or True
        ),
    )

    result = runner.invoke(app, [command_name])

    assert result.exit_code == 0, result.output
    assert observed == [(ctx.name, kind)]
