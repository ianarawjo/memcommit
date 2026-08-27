"""Shared setup and process-local Resolution contracts for quality finders."""

from __future__ import annotations

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.shared.quality_find_workbench import (
    QualityFindSetupReceipt,
    choose_quality_find_setup,
    run_interactive_quality_find,
    run_quality_find_resolution_workbench,
)
from memcommit.application.reviewing.quality.findings import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.application.reviewing.quality.workbench import (
    QualityFindSourceFrame,
    QualityFindWorkbenchError,
    create_quality_find_workbench,
    quality_find_resolution_view,
)
from memcommit.application.reviewing.read_report import ReadReportRecent, ReadReportTarget
from memcommit.adapters.console.responses.resolution import response_target_from_item
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def _context():
    ctx = ops.init("quality/source")
    first = ops.add(ctx, "The main entrance opens at 8:00.")
    second = ops.add(ctx, "The main entrance remains closed until 9:00.")
    return ctx, first, second


def test_flagless_setup_exposes_multiple_targets_and_descendant_range():
    with create_pipe_input() as pipe_input:
        # Scope row 1 keeps MULTIPLE; row 2 selects INCLUDE DESCENDANTS.
        pipe_input.send_text("\t\x1b[B\x1b[C\t\r")
        receipt = choose_quality_find_setup(
            ("root", "root/child", "peer"),
            current="root",
            kind="conflicts",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == QualityFindSetupReceipt(
        target_names=("root",),
        context_names=("root", "root/child"),
        selection_mode="MULTIPLE",
        include_descendants=True,
    )


def test_flagless_setup_can_check_multiple_independent_contexts():
    with create_pipe_input() as pipe_input:
        # Peer is the next visible row while root remains collapsed.
        pipe_input.send_text("\x1b[B\r\t\t\r")
        receipt = choose_quality_find_setup(
            ("root", "root/child", "peer"),
            current="root",
            kind="duplicates",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.context_names == ("root", "peer")
    assert receipt.selection_mode == "MULTIPLE"
    assert receipt.include_descendants is False


def test_flagless_setup_projects_profile_as_one_exclusive_virtual_target():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[A\r\t\t\r")
        receipt = choose_quality_find_setup(
            ("root", "peer"),
            current="root",
            kind="duplicates",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == QualityFindSetupReceipt(
        target_names=(),
        context_names=("root", "peer"),
        selection_mode="MULTIPLE",
        include_descendants=False,
        profile_selected=True,
    )


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
        "memcommit.adapters.console.commands.shared.quality_find_workbench.choose_quality_find_setup",
        lambda *_args, **_kwargs: None,
    )

    completed = run_interactive_quality_find(
        store,
        current_name=ctx.name,
        kind="conflicts",
        analyze=lambda selected: analyzed.append(selected.context_name),
    )

    assert completed is False
    assert analyzed == []


def test_interactive_orchestration_builds_one_cross_context_analysis_frame(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("quality/root")
    child = ops.init("quality/root/child")
    root_memory = ops.add(root, "The entrance opens at 8:00.")
    child_memory = ops.add(child, "The entrance opens at eight.")
    store.create_context(root)
    store.create_context(child)
    store.set_current(root.name)
    observed: list[QualityFindSourceFrame] = []

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench.choose_quality_find_setup",
        lambda *_args, **_kwargs: QualityFindSetupReceipt(
            target_names=(root.name,),
            context_names=(root.name, child.name),
            selection_mode="SINGLE",
            include_descendants=True,
        ),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench."
        "run_quality_find_resolution_workbench",
        lambda *_args, **_kwargs: None,
    )

    def analyze(source):
        observed.append(source)
        return ConflictReport(memory_count=2, pair_count=1, findings=())

    completed = run_interactive_quality_find(
        store,
        current_name=root.name,
        kind="conflicts",
        analyze=analyze,
    )

    assert completed is True
    source = observed[0]
    assert source.context_names == (root.name, child.name)
    assert [memory.content for memory in source.analysis_context().iter_items()] == [
        root_memory.content,
        child_memory.content,
    ]
    assert source.memory_context_names == {
        root_memory.uid: root.name,
        child_memory.uid: child.name,
    }


def test_interactive_orchestration_replays_recent_target_without_saved_session(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("quality/recent")
    child = ops.init("quality/recent/child")
    ops.add(root, "First duplicate candidate.")
    ops.add(child, "First duplicate candidate.")
    store.create_context(root)
    store.create_context(child)
    store.set_current(root.name)
    target = ReadReportTarget(
        operation="dedun",
        context_names=(root.name, child.name),
        target_names=(root.name,),
        selection_mode="SINGLE",
        ranges=("RECURSIVE",),
    )
    recent = ReadReportRecent(
        attempt_uid="recent-attempt",
        target=target,
        started_at="2026-08-16T12:00:00+00:00",
    )
    observed: list[QualityFindSourceFrame] = []
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench.read_report_recents",
        lambda *_args, **_kwargs: (recent,),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench.choose_read_report_recent",
        lambda *_args, **_kwargs: target,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench.revalidate_read_report_recent",
        lambda *_args, **_kwargs: target,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench.choose_quality_find_setup",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("a recent target must bypass fresh setup")
        ),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench."
        "run_quality_find_resolution_workbench",
        lambda *_args, **_kwargs: None,
    )

    completed = run_interactive_quality_find(
        store,
        current_name=root.name,
        kind="duplicates",
        analyze=lambda source: (
            observed.append(source) or DuplicateReport(memory_count=2, findings=())
        ),
    )

    assert completed is True
    assert observed[0].context_names == (root.name, child.name)
    assert observed[0].include_descendants is True


def test_profile_recent_reexpands_the_current_frozen_readable_catalog(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    original = ops.init("quality/profile/original")
    added_later = ops.init("quality/profile/added-later")
    ops.add(original, "An original Profile Memory.")
    ops.add(added_later, "A newly readable Profile Memory.")
    store.create_context(original)
    store.create_context(added_later)
    store.set_current(original.name)
    target = ReadReportTarget(
        operation="dedun",
        # This is the effective Profile membership recorded by the old run.
        context_names=(original.name,),
        target_names=(),
        selection_mode="MULTIPLE",
        ranges=("DIRECT",),
        profile_selected=True,
    )
    recent = ReadReportRecent(
        attempt_uid="profile-recent-attempt",
        target=target,
        started_at="2026-08-16T12:00:00+00:00",
    )
    observed: list[QualityFindSourceFrame] = []
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench.read_report_recents",
        lambda *_args, **_kwargs: (recent,),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench.choose_read_report_recent",
        lambda *_args, **_kwargs: target,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench.revalidate_read_report_recent",
        lambda *_args, **_kwargs: target,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.shared.quality_find_workbench."
        "run_quality_find_resolution_workbench",
        lambda *_args, **_kwargs: None,
    )

    completed = run_interactive_quality_find(
        store,
        current_name=original.name,
        kind="duplicates",
        analyze=lambda source: (
            observed.append(source) or DuplicateReport(memory_count=2, findings=())
        ),
    )

    assert completed is True
    assert set(observed[0].context_names) == {original.name, added_later.name}
    assert observed[0].target_names == ()
    assert observed[0].profile_selected is True


def test_quality_find_profile_receipts_reject_mixed_ordinary_roots():
    with pytest.raises(ValueError, match="valid Context range"):
        QualityFindSetupReceipt(
            target_names=("quality/profile",),
            context_names=("quality/profile",),
            selection_mode="MULTIPLE",
            include_descendants=False,
            profile_selected=True,
        )

    profile = ops.init("quality/profile")
    with pytest.raises(QualityFindWorkbenchError, match="target roots"):
        QualityFindSourceFrame.create(
            (profile,),
            target_names=(profile.name,),
            selection_mode="MULTIPLE",
            profile_selected=True,
        )


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


def test_conflict_projection_keeps_pair_question_and_no_fabricated_choices():
    ctx, first, second = _context()
    report = ConflictReport(
        memory_count=2,
        pair_count=1,
        findings=(
            ConflictFinding(
                left=first,
                right=second,
                conflict="YES",
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
    assert evidence.classification == "YES"


def test_cross_context_finding_keeps_each_memorys_source_context():
    left_context = ops.init("quality/left")
    right_context = ops.init("quality/right")
    ops.add(left_context, "The entrance opens at 8:00.")
    ops.add(right_context, "The entrance stays closed until 9:00.")
    source = QualityFindSourceFrame.create(
        (left_context, right_context),
        selection_mode="MULTIPLE",
    )
    aggregate = source.analysis_context()
    aggregate_memories = tuple(aggregate.iter_items())
    report = ConflictReport(
        memory_count=2,
        pair_count=1,
        findings=(
            ConflictFinding(
                aggregate_memories[0],
                aggregate_memories[1],
                "YES",
                "The opening states conflict.",
                "Which schedule applies?",
            ),
        ),
    )

    item = quality_find_resolution_view(
        create_quality_find_workbench("conflicts", source, report),
        source,
    ).items[0]

    assert item.issue_presentation is not None
    assert [
        evidence.context_name
        for evidence in item.issue_presentation.evidence[0].sources
    ] == [left_context.name, right_context.name]


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
    assert item.kind == "SEMANTIC DUN"
    assert "semantic-DUN evidence" in item.question
    assert all("survivor" not in option.text.casefold() for option in item.options)


def test_shared_redundancy_report_projects_caller_owned_operation_identity():
    ctx, first, second = _context()
    session = create_quality_find_workbench(
        "duplicates",
        ctx,
        DuplicateReport(
            memory_count=2,
            findings=(
                DuplicateFinding(
                    left=first,
                    right=second,
                    relation="SEMANTIC_EQUIVALENT",
                    reason="Equivalent.",
                ),
            ),
        ),
    )

    dedun = quality_find_resolution_view(session, ctx)
    finder = quality_find_resolution_view(
        session,
        ctx,
        operation_label="FIND REDUNDANCIES",
    )

    assert (dedun.operation, dedun.title) == ("DEDUN", "MEM DEDUN")
    assert (finder.operation, finder.title) == (
        "FIND REDUNDANCIES",
        "MEM FIND REDUNDANCIES",
    )


def test_redundancy_view_includes_exact_dup_inside_complete_dun_report():
    ctx, first, second = _context()
    session = create_quality_find_workbench(
        "duplicates",
        ctx,
        DuplicateReport(
            memory_count=2,
            findings=(
                DuplicateFinding(
                    left=first,
                    right=second,
                    relation="EXACT",
                    reason="Stored content is identical.",
                ),
            ),
        ),
    )

    view = quality_find_resolution_view(
        session,
        ctx,
        operation_label="FIND REDUNDANCIES",
    )

    assert len(view.items) == 1
    assert view.items[0].kind == "DUP / EXACT"
    assert view.items[0].options == ()
    assert view.items[0].response_state == "NOT_APPLICABLE"
    assert view.items[0].effective_obligation == "NONE"
    assert view.status.endswith("0/0 ANSWERED")
    assert response_target_from_item(view, view.items[0], read_only=False) is None
    assert ("PROPOSED ABSORPTIONS", "1") in {
        (metric.label, metric.value) for metric in view.metrics
    }
    assert "REDUNDANCIES" in view.overview
    assert "1 cleanup group and 1 proposed absorption" in view.overview


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


def test_process_local_finding_browser_can_close_without_mutating_context():
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
    assert session.responses == {}


def test_conflict_workbench_hands_off_the_selected_typed_finding():
    ctx, first, second = _context()
    session = create_quality_find_workbench(
        "conflicts",
        ctx,
        ConflictReport(
            memory_count=2,
            pair_count=1,
            findings=(
                ConflictFinding(
                    first,
                    second,
                    "YES",
                    "The entrance hours conflict.",
                    "Which opening time is authoritative?",
                ),
            ),
        ),
    )
    observed = []

    with create_pipe_input() as pipe_input:
        # Find itself stays read-only; Enter explicitly leaves for Resolve.
        pipe_input.send_text("\r")
        result = run_quality_find_resolution_workbench(
            session,
            ctx,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            handoff_handler=observed.append,
        )

    assert result is session
    assert len(observed) == 1
    assert observed[0].finding_uid == f"conflict:{first.uid}:{second.uid}"
    assert observed[0].route == "RESOLVE"
    assert session.responses == {}


def test_conflict_workbench_legacy_handoff_letter_is_inert():
    ctx, first, second = _context()
    session = create_quality_find_workbench(
        "conflicts",
        ctx,
        ConflictReport(
            memory_count=2,
            pair_count=1,
            findings=(
                ConflictFinding(
                    first,
                    second,
                    "YES",
                    "The entrance hours conflict.",
                    "Which opening time is authoritative?",
                ),
            ),
        ),
    )
    observed = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("r\x1b")
        result = run_quality_find_resolution_workbench(
            session,
            ctx,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            handoff_handler=observed.append,
        )

    assert result is session
    assert observed == []
    assert session.responses == {}


@pytest.mark.parametrize(
    ("module_name", "command_name", "kind", "operation_name", "has_handoff"),
    [
        ("find_ambiguities", "find-ambiguities", "ambiguities", None, False),
        ("find_conflicts", "find-conflicts", "conflicts", None, False),
    ],
)
def test_explicit_select_commands_route_to_the_shared_quality_workbench(
    isolated_store,
    monkeypatch,
    module_name,
    command_name,
    kind,
    operation_name,
    has_handoff,
):
    store = MemoryStore()
    ctx, _first, _second = _context()
    store.create_context(ctx)
    store.set_current(ctx.name)
    observed: list[tuple[str | None, str, str | None, bool]] = []
    module_path = f"memcommit.adapters.console.commands.{module_name}.command"

    monkeypatch.setattr(
        f"{module_path}.interactive_quality_find_available",
        lambda: True,
    )
    monkeypatch.setattr(
        f"{module_path}.run_interactive_quality_find",
        lambda _store, *, current_name, kind, analyze, **kwargs: (
            observed.append(
                (
                    current_name,
                    kind,
                    kwargs.get("operation_name"),
                    kwargs.get("duplicate_handoff_handler") is not None,
                )
            )
            or True
        ),
    )

    result = runner.invoke(app, [command_name, "--select"])

    assert result.exit_code == 0, result.output
    assert observed == [(ctx.name, kind, operation_name, has_handoff)]


def test_find_redundancies_has_no_initial_selector_route(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _first, _second = _context()
    store.create_context(ctx)
    store.set_current(ctx.name)
    observed: list[str] = []
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_duplicates.command.ops.find_redundancies",
        lambda source, *_args, **_kwargs: (
            observed.append(source.name) or DuplicateReport(memory_count=2, findings=())
        ),
    )

    result = runner.invoke(app, ["find-redundancies"])
    select_result = runner.invoke(app, ["find-redundancies", "--select"])

    assert result.exit_code == 0, result.output
    assert observed == [ctx.name]
    assert "0 groups · 0 proposed absorptions" in result.output
    assert select_result.exit_code == 2
    assert "No such option: --select" in select_result.output


def test_repeated_dedun_bypasses_report_recents_and_target_setup(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _first, _second = _context()
    store.create_context(ctx)
    store.set_current(ctx.name)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_duplicates.command.ops.find_redundancies",
        lambda *_args, **_kwargs: DuplicateReport(memory_count=2, findings=()),
    )

    first = runner.invoke(app, ["dedun"])
    second = runner.invoke(app, ["dedun"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert first.output == second.output
    assert "No redundancies" in second.output
