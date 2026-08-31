"""Interactive and public CLI contracts for structural Merge reach."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
import memcommit.adapters.console.commands.direct_changes.merge.endpoint_setup as merge_setup
from memcommit.adapters.console.commands.direct_changes.merge.endpoint_setup import (
    MergeSetup,
    build_merge_setup,
    choose_merge_request,
    merge_setup_spec,
)
from memcommit.adapters.console.commands.direct_changes.merge.workbench.conflicts import (
    merge_resolution_exact_review,
    merge_resolution_spec,
    run_merge_conflict_review,
)
from memcommit.adapters.console.commands.direct_changes.merge.workbench.review import (
    merge_exact_command_review,
    merge_plan_exact_command_review,
    project_merge_plan,
    run_merge_plan_review,
)
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory
from memcommit.adapters.console.terminal.components.resolution import ResolutionOutcome
from memcommit.adapters.console.terminal.components.resolution.inline_shell import (
    render_inline_resolution_item,
    run_inline_resolution_workbench,
)
from memcommit.application.operations.direct_changes.merge.application import (
    FrozenMergePlan,
    MergeAddition,
    MergeConflict,
    MergeConflictKind,
    MergeContextResult,
    MergeDecision,
    MergeError,
    MergeItemKind,
    MergeItemSnapshot,
    MergeReach,
    MergeRequest,
    MergeResolution,
    MergeResult,
    prepare_merge,
    run_merge,
)
from memcommit.application.operations.direct_changes.merge.runtime import MemoryStoreMergePort
from memcommit.adapters.console.terminal.components.selection.model import SelectionOption
from memcommit.adapters.console.terminal.components.selection.state import FlatSelectionState
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _setup(*, recursive: bool = False) -> MergeSetup:
    return MergeSetup(
        names=("source", "target"),
        selectable_names=frozenset({"source", "target"}),
        selected_source="source",
        target_names=("source", "target", "target-b"),
        target_selectable_names=frozenset({"source", "target", "target-b"}),
        target_context="target",
        initial_recursive=recursive,
        current_context="target",
    )


def _result(request: MergeRequest) -> MergeResult:
    addition = MergeAddition(uid="memory-uid", kind=MergeItemKind.MEMORY)
    context = MergeContextResult(
        source_name="source",
        source_uid="source-uid",
        target_name="target",
        target_uid="target-uid",
        target_created=False,
        additions=(addition,),
    )
    return MergeResult(
        source_name=context.source_name,
        source_uid=context.source_uid,
        target_name=context.target_name,
        target_uid=context.target_uid,
        reach=request.reach,
        additions=context.additions,
        contexts=(context,),
        checkpoint_uid="checkpoint-uid",
        checkpoint_uids=("checkpoint-uid",),
        cross_profile_memory_only=False,
    )


def _plan(request: MergeRequest | None = None) -> FrozenMergePlan:
    request = request or MergeRequest(
        source_locator="source",
        target_locator="target",
        reach=MergeReach.DIRECT,
    )
    result = _result(request)
    return FrozenMergePlan(
        request=request,
        source_name=result.source_name,
        source_uid=result.source_uid,
        source_digest="source-digest",
        target_name=result.target_name,
        target_uid=result.target_uid,
        target_digest="target-digest",
        additions=result.additions,
        contexts=result.contexts,
        cross_profile_memory_only=False,
        token=object(),
    )


def _conflict_plan() -> FrozenMergePlan:
    plan = _plan()
    conflict = MergeConflict(
        uid="merge-conflict:test",
        kind=MergeConflictKind.CONTENT_DIVERGENCE,
        source_name="source",
        target_name="target",
        source=MergeItemSnapshot(
            "memory-uid",
            MergeItemKind.MEMORY,
            "Memory [memory-u]",
            "source revision",
        ),
        targets=(
            MergeItemSnapshot(
                "memory-uid",
                MergeItemKind.MEMORY,
                "Memory [memory-u]",
                "target revision",
            ),
        ),
        reason="The same Memory identity has different content.",
    )
    context = replace(plan.contexts[0], additions=(), conflicts=(conflict,))
    return replace(
        plan,
        additions=(),
        contexts=(context,),
        conflicts=(conflict,),
    )


def _multi_conflict_plan(count: int = 3) -> FrozenMergePlan:
    plan = _conflict_plan()
    conflicts = tuple(
        replace(
            plan.conflicts[0],
            uid=f"merge-conflict:test-{index}",
            source=replace(
                plan.conflicts[0].source,
                uid=f"memory-{index}",
                description=f"Memory [memory-{index}]",
                content=f"complete source value {index}",
            ),
            targets=(
                replace(
                    plan.conflicts[0].targets[0],
                    uid=f"memory-{index}",
                    description=f"Memory [memory-{index}]",
                    content=f"complete target value {index}",
                ),
            ),
        )
        for index in range(1, count + 1)
    )
    context = replace(plan.contexts[0], conflicts=conflicts)
    return replace(plan, contexts=(context,), conflicts=conflicts)


def _resolved_result(
    plan: FrozenMergePlan,
    resolutions: tuple[MergeResolution, ...],
) -> MergeResult:
    return MergeResult(
        source_name=plan.source_name,
        source_uid=plan.source_uid,
        target_name=plan.target_name,
        target_uid=plan.target_uid,
        reach=plan.request.reach,
        additions=plan.additions,
        contexts=plan.contexts,
        checkpoint_uid="checkpoint-uid",
        checkpoint_uids=("checkpoint-uid",),
        cross_profile_memory_only=False,
        unchanged=plan.unchanged,
        conflicts=plan.conflicts,
        resolutions=resolutions,
    )


def test_frozen_plan_projection_exposes_complete_mapping_before_apply() -> None:
    document = project_merge_plan(_plan())
    rendered = "".join(
        text for _style, text in document.render(focused_uid="MERGE:PLAN:SUMMARY")
    )

    assert [section.kind for section in document.sections] == [
        "SUMMARY",
        "CONTEXT_PLAN",
    ]
    assert "STATUS · READY FOR REVIEW" in rendered
    assert "source → target" in rendered
    assert "TARGET · EXISTING" in rendered
    assert "MEMORY · [memory-u]" in rendered


def test_plan_review_applies_only_the_exact_frozen_plan() -> None:
    plan = _plan()
    applied: list[FrozenMergePlan] = []
    with create_pipe_input() as pipe_input:
        # Viewer owns first focus. Tab reaches the exact frozen-plan action;
        # one Enter applies and a second closes the durable receipt.
        pipe_input.send_text("\t\r\r")
        returned = run_merge_plan_review(
            plan,
            apply_plan=lambda frozen: applied.append(frozen) or _result(frozen.request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == _result(plan.request)
    assert applied == [plan]


def test_plan_review_cancel_does_not_apply() -> None:
    plan = _plan()
    applied: list[FrozenMergePlan] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_merge_plan_review(
            plan,
            apply_plan=lambda frozen: applied.append(frozen) or _result(frozen.request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert applied == []


def test_conflict_workbench_bulk_review_applies_one_exact_whole_set() -> None:
    plan = _multi_conflict_plan()
    applied: list[tuple[MergeResolution, ...]] = []
    with create_pipe_input() as pipe_input:
        # Tab reaches the separate Controls frame without traversing conflicts.
        # Up focuses Bulk, Right chooses TAKE ALL SOURCE, and Enter stages it
        # before the exact review/apply/close sequence.
        pipe_input.send_text("\t\x1b[A\x1b[C\r\r\r\r")
        returned = run_merge_conflict_review(
            plan,
            apply_plan=lambda frozen, resolutions: (
                applied.append(resolutions) or _resolved_result(frozen, resolutions)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert applied == [
        tuple(
            MergeResolution(
                f"merge-conflict:test-{index}",
                MergeDecision.TAKE_SOURCE,
            )
            for index in range(1, 4)
        )
    ]


def test_conflict_workbench_arrows_change_one_inline_choice_before_apply() -> None:
    plan = _conflict_plan()
    applied: list[tuple[MergeResolution, ...]] = []
    with create_pipe_input() as pipe_input:
        # Target is staged initially. Left chooses Source; Tab jumps directly
        # to Apply in the separate Controls frame, then review/apply/close.
        pipe_input.send_text("\x1b[D\t\r\r\r")
        returned = run_merge_conflict_review(
            plan,
            apply_plan=lambda frozen, resolutions: (
                applied.append(resolutions) or _resolved_result(frozen, resolutions)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert applied[0][0].decision is MergeDecision.TAKE_SOURCE


def test_inline_conflict_workbench_copies_one_row_or_the_complete_set() -> None:
    plan = _multi_conflict_plan()
    copied: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("yYq")
        returned = run_merge_conflict_review(
            plan,
            apply_plan=lambda _frozen, _resolutions: pytest.fail(
                "Copying and closing must not apply Merge."
            ),
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert len(copied) == 2
    assert "complete source value 1" in copied[0]
    assert "complete target value 1" in copied[0]
    assert "complete source value 3" not in copied[0]
    assert "complete source value 3" in copied[1]
    assert "complete target value 3" in copied[1]


def test_conflict_workbench_stages_keep_target_and_apply_is_ready_at_entry() -> None:
    plan = _conflict_plan()
    applied: list[tuple[MergeResolution, ...]] = []
    with create_pipe_input() as pipe_input:
        # One Tab reaches Apply regardless of item count. No item decision is
        # required because KEEP TARGET is visibly staged for every conflict.
        pipe_input.send_text("\t\r\r\r")
        returned = run_merge_conflict_review(
            plan,
            apply_plan=lambda frozen, resolutions: (
                applied.append(resolutions) or _resolved_result(frozen, resolutions)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert applied == [
        (MergeResolution("merge-conflict:test", MergeDecision.KEEP_TARGET),)
    ]


def test_conflict_workbench_retains_distinct_choices_for_three_conflicts() -> None:
    plan = _multi_conflict_plan()
    applied: list[tuple[MergeResolution, ...]] = []
    with create_pipe_input() as pipe_input:
        # Choose Source for rows 1 and 3, retain Target for row 2, then Tab
        # directly to the independently focused Apply action.
        pipe_input.send_text("\x1b[D\x1b[B\x1b[B\x1b[D\t\r\r\r")
        returned = run_merge_conflict_review(
            plan,
            apply_plan=lambda frozen, resolutions: (
                applied.append(resolutions) or _resolved_result(frozen, resolutions)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert [resolution.decision for resolution in applied[0]] == [
        MergeDecision.TAKE_SOURCE,
        MergeDecision.KEEP_TARGET,
        MergeDecision.TAKE_SOURCE,
    ]


def test_conflict_workbench_tab_skips_150_rows_and_preserves_staged_defaults() -> None:
    plan = _multi_conflict_plan(150)
    applied: list[tuple[MergeResolution, ...]] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\r\r\r")
        returned = run_merge_conflict_review(
            plan,
            apply_plan=lambda frozen, resolutions: (
                applied.append(resolutions) or _resolved_result(frozen, resolutions)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert len(applied[0]) == 150
    assert {resolution.decision for resolution in applied[0]} == {
        MergeDecision.KEEP_TARGET
    }


def test_conflict_workbench_shift_tab_restores_the_retained_conflict_cursor() -> None:
    plan = _multi_conflict_plan()
    applied: list[tuple[MergeResolution, ...]] = []
    with create_pipe_input() as pipe_input:
        # Retain row 2 while visiting Controls, return to that row, choose its
        # Source value, then jump back to Apply.
        pipe_input.send_text("\x1b[B\t\x1b[Z\x1b[D\t\r\r\r")
        returned = run_merge_conflict_review(
            plan,
            apply_plan=lambda frozen, resolutions: (
                applied.append(resolutions) or _resolved_result(frozen, resolutions)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert [resolution.decision for resolution in applied[0]] == [
        MergeDecision.KEEP_TARGET,
        MergeDecision.TAKE_SOURCE,
        MergeDecision.KEEP_TARGET,
    ]


def test_inline_workbench_derives_bulk_state_when_individual_rows_all_agree() -> None:
    spec = merge_resolution_spec(_multi_conflict_plan())
    applied: list[ResolutionOutcome] = []
    with create_pipe_input() as pipe_input:
        # Select Source independently on all three rows. The Controls summary
        # must normalize that uniform set to TAKE_SOURCE without requiring the
        # explicit Bulk control.
        pipe_input.send_text("\x1b[D\x1b[B\x1b[D\x1b[B\x1b[D\t\r\r\r")
        returned = run_inline_resolution_workbench(
            spec,
            apply_outcome=lambda outcome: applied.append(outcome) or outcome,
            receipt_text=lambda _outcome: "recorded",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert applied[0].bulk_uid == MergeDecision.TAKE_SOURCE.value


def test_merge_resolution_spec_has_no_custom_choice() -> None:
    spec = merge_resolution_spec(_conflict_plan())

    assert [choice.uid for choice in spec.items[0].choices] == [
        "KEEP_TARGET",
        "TAKE_SOURCE",
    ]


def test_conflict_review_exact_command_names_the_selected_target() -> None:
    review = merge_resolution_exact_review(
        _conflict_plan(),
        ResolutionOutcome((("merge-conflict:test", "KEEP_TARGET"),)),
    )

    assert review.argv[:6] == (
        "mem",
        "merge",
        "source",
        "target",
        "--direct",
        "--resolve",
    )
    assert any("Add 0 items" in effect for effect in review.effects)


def test_merge_resolution_uses_inline_full_value_choices_without_viewer() -> None:
    spec = merge_resolution_spec(_conflict_plan())

    assert spec.show_viewer is False
    assert spec.inline_choice_layout is True
    assert spec.title == "MERGE REVIEW · 1 conflict"
    assert spec.subtitle == "CHOOSE EACH"
    assert spec.items[0].default_choice_uid == "KEEP_TARGET"
    assert [choice.label for choice in spec.items[0].inline_choices] == [
        "SOURCE",
        "TARGET",
    ]
    assert [choice.content for choice in spec.items[0].inline_choices] == [
        "source revision",
        "target revision",
    ]


def test_inline_conflict_renderer_never_elides_long_or_multiline_memory() -> None:
    source = "source first line\n" + ("source-complete-value " * 20) + "SOURCE-END"
    target = "target first line\n" + ("target-complete-value " * 20) + "TARGET-END"
    plan = _conflict_plan()
    conflict = replace(
        plan.conflicts[0],
        source=replace(plan.conflicts[0].source, content=source),
        targets=(replace(plan.conflicts[0].targets[0], content=target),),
    )
    context = replace(plan.contexts[0], conflicts=(conflict,))
    spec = merge_resolution_spec(
        replace(plan, contexts=(context,), conflicts=(conflict,))
    )
    item = spec.items[0]
    state = FlatSelectionState(
        tuple(
            SelectionOption(choice.choice_uid, choice.label)
            for choice in item.inline_choices
            if choice.selectable
        ),
        cursor_uid="KEEP_TARGET",
        selected_uid="KEEP_TARGET",
        allow_empty=False,
    )

    rendered = "".join(
        text
        for _style, text in render_inline_resolution_item(
            item,
            state,
            ordinal=1,
            focused=True,
        )
    )

    assert source in rendered
    assert target in rendered
    assert "SOURCE-END" in rendered
    assert "TARGET-END" in rendered


def test_store_backed_frozen_plan_is_read_only_until_review_apply(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("source")
    addition = ops.add(source, "planned only")
    store.create_context(source)
    target = ops.init("target")
    store.create_context(target)
    store.set_current(target.name)
    port = MemoryStoreMergePort.capture(store)
    request = MergeRequest(
        source_locator="source",
        target_locator="target",
        reach=MergeReach.DIRECT,
    )
    plan = prepare_merge(request, port=port)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_merge_plan_review(
            plan,
            apply_plan=lambda frozen: run_merge(
                request,
                port=port,
                frozen_plan=frozen,
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert addition.uid not in store.load_direct("target").memories
    assert store.list_checkpoints("target") == []


def test_frozen_plan_exact_review_names_actual_counts() -> None:
    review = merge_plan_exact_command_review(_plan())

    assert review.argv == (
        "mem",
        "merge",
        "source",
        "target",
        "--direct",
    )
    assert any("1 Context mapping" in effect for effect in review.effects)
    assert any("1 checkpoint" in effect for effect in review.effects)


def test_plan_review_failure_stays_visible_then_exits_without_receipt() -> None:
    plan = _plan()
    applied: list[FrozenMergePlan] = []

    def fail(frozen: FrozenMergePlan) -> MergeResult:
        applied.append(frozen)
        raise RuntimeError("injected Merge failure")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\rq")
        with pytest.raises(MergeError, match="injected Merge failure"):
            run_merge_plan_review(
                plan,
                apply_plan=fail,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

    assert applied == [plan]


def test_exact_review_names_recursive_path_and_selected_target() -> None:
    review = merge_exact_command_review(
        "source",
        "target",
        recursive=True,
    )

    assert review.argv == (
        "mem",
        "merge",
        "source",
        "target",
        "--recursive",
    )
    assert any("by relative path" in effect for effect in review.effects)
    assert any("Target subtree 'target'" in effect for effect in review.effects)
    assert any("selected Target 'target'" in effect for effect in review.effects)


def test_meld_style_setup_projects_coupled_reach_and_selectable_target() -> None:
    spec = merge_setup_spec(_setup())

    assert tuple(mode.uid for mode in spec.modes) == ("DIRECT", "DESCENDANTS")
    assert spec.roles[0].uid == "A"
    assert spec.roles[0].fixed is False
    assert spec.roles[1].uid == "B"
    assert spec.roles[1].selected_name == "target"
    assert spec.roles[1].fixed is False
    assert spec.roles[1].selectable_names == frozenset({"source", "target", "target-b"})
    assert spec.roles[0].selectable_names == frozenset({"source", "target"})


def test_merge_same_source_and_target_is_rejected_at_continue_not_picker() -> None:
    setup = MergeSetup(
        names=("target",),
        selectable_names=frozenset({"target"}),
        selected_source="target",
        target_names=("target",),
        target_selectable_names=frozenset({"target"}),
        target_context="target",
        current_context="target",
    )
    with create_pipe_input() as pipe_input:
        # MODE -> Source -> Target -> Continue. Both rows remain selectable, while
        # Continue owns the invalid same-Context result and keeps the TUI open.
        pipe_input.send_text("\t\t\t\rq")
        request = choose_merge_request(
            setup,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert request is None


def test_meld_style_setup_returns_typed_recursive_request() -> None:
    with create_pipe_input() as pipe_input:
        # A multi-shape setup starts on MODE. Right selects recursive, then
        # Source, Target, and Continue are the next visible focus surfaces.
        pipe_input.send_text("\x1b[C\t\t\t\r")
        request = choose_merge_request(
            _setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert request == MergeRequest(
        source_locator="source",
        target_locator="target",
        reach=MergeReach.DESCENDANTS,
    )


def test_meld_style_setup_returns_the_selected_target() -> None:
    with create_pipe_input() as pipe_input:
        # MODE -> Source -> Target. Move from target to target-b, select it,
        # then continue with the reviewed draft.
        pipe_input.send_text("\t\t\x1b[B\r\t\r")
        request = choose_merge_request(
            _setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert request == MergeRequest(
        source_locator="source",
        target_locator="target-b",
        reach=MergeReach.DIRECT,
    )


def test_meld_style_setup_cancel_returns_no_request() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        request = choose_merge_request(
            _setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert request is None


def test_tui_setup_freezes_source_and_target_catalogs_with_current_default(
    isolated_store,
) -> None:
    store = MemoryStore()
    store.create_context(ops.init("source"))
    store.create_context(ops.init("target"))
    store.set_current("target")

    setup = build_merge_setup(
        MemoryStoreMergePort.capture(store),
        initial_recursive=True,
    )

    assert setup.names == ("source", "target")
    assert setup.selectable_names == frozenset({"source", "target"})
    assert setup.selected_source == "source"
    assert setup.target_names == ("source", "target")
    assert setup.target_selectable_names == frozenset({"source", "target"})
    assert setup.target_context == "target"
    assert setup.current_context == "target"
    assert setup.initial_recursive is True


def test_tui_setup_uses_profile_readable_breadth_without_query_only_routes(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    for name in ("local-source", "other-local", "target"):
        store.create_context(ops.init(name))
    store.set_current("target")
    observed = []

    def freeze_profile(_store, selected_access):
        observed.append(selected_access.display_name)
        return SimpleNamespace(
            local_names=("local-source", "other-local", "target"),
            virtual_names=("granted/query-only", "granted/readable"),
            selectable_virtual_names=frozenset({"granted/readable"}),
            virtual_annotations={
                "granted/readable": "READ GRANT",
                "granted/query-only": "QUERY GRANT",
            },
        )

    monkeypatch.setattr(
        merge_setup,
        "freeze_profile_context_navigation",
        freeze_profile,
    )

    setup = build_merge_setup(
        MemoryStoreMergePort.capture(store),
        initial_recursive=False,
    )

    assert observed == ["target"]
    assert setup.names == (
        "granted/readable",
        "local-source",
        "other-local",
        "target",
    )
    assert setup.selectable_names == frozenset(
        {"granted/readable", "local-source", "other-local", "target"}
    )
    assert setup.annotations == (("granted/readable", "READ GRANT"),)
    assert setup.target_names == ("local-source", "other-local", "target")
    assert setup.target_selectable_names == frozenset(
        {"local-source", "other-local", "target"}
    )
    assert setup.target_annotations == ()
    assert "granted/query-only" not in setup.names


def test_tui_target_catalog_includes_only_create_authorized_grants(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    for name in ("source", "target"):
        store.create_context(ops.init(name))
    store.set_current("target")
    real_resolve = merge_setup.resolve_context_access

    def resolve(store, operand, *, current_name, required_permission):
        if operand == "granted/create":
            assert required_permission == "CREATE"
            return SimpleNamespace(display_name=operand)
        if operand == "granted/read":
            raise RuntimeError("READ-only Grant")
        return real_resolve(
            store,
            operand,
            current_name=current_name,
            required_permission=required_permission,
        )

    monkeypatch.setattr(merge_setup, "resolve_context_access", resolve)
    monkeypatch.setattr(
        merge_setup,
        "freeze_profile_context_navigation",
        lambda _store, _selected: SimpleNamespace(
            local_names=("source", "target"),
            virtual_names=("granted/create", "granted/read"),
            selectable_virtual_names=frozenset({"granted/read"}),
            virtual_annotations={
                "granted/create": "CREATE GRANT",
                "granted/read": "READ GRANT",
            },
        ),
    )

    setup = build_merge_setup(
        MemoryStoreMergePort.capture(store),
        initial_recursive=False,
    )

    assert setup.names == ("granted/read", "source", "target")
    assert setup.target_names == ("granted/create", "source", "target")
    assert setup.target_annotations == (("granted/create", "CREATE GRANT"),)


def test_tui_setup_uses_an_explicit_target_without_switching_current(
    isolated_store,
) -> None:
    store = MemoryStore()
    for name in ("source", "target", "target-b"):
        store.create_context(ops.init(name))
    store.set_current("target")

    setup = build_merge_setup(
        MemoryStoreMergePort.capture(store),
        initial_recursive=False,
        requested_target="target-b",
    )

    assert setup.target_context == "target-b"
    assert setup.current_context == "target"
    assert store.current_context_name() == "target"


def test_cli_recursive_merge_creates_path_aligned_target_descendant(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("source")
    store.create_context(source)
    child = ops.init("source/child")
    child_memory = ops.add(child, "recursive child fact")
    store.create_context(child)
    target = ops.init("target")
    store.create_context(target)
    store.set_current(target.name)

    result = runner.invoke(app, ["merge", "source", "--recursive"])

    assert result.exit_code == 0, result.output
    assert "MERGE RECORDED · 'source' → 'target' · DESCENDANTS" in result.output
    assert "CREATED CONTEXTS 1" in result.output
    assert "CHECKPOINTS 2" in result.output
    merged_child = store.load_direct("target/child")
    assert child_memory.uid not in merged_child.memories
    assert [
        item.content for item in merged_child.iter_items() if isinstance(item, Memory)
    ] == ["recursive child fact"]


def test_cli_recursive_root_only_receipt_uses_singular_counts(isolated_store) -> None:
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "root fact")
    store.create_context(source)
    target = ops.init("target")
    store.create_context(target)
    store.set_current(target.name)

    result = runner.invoke(app, ["merge", "source", "--recursive"])

    assert result.exit_code == 0, result.output
    assert "CREATED CONTEXTS 0" in result.output
    assert "CHECKPOINTS 1" in result.output


def test_cli_merge_into_explicit_target_without_a_current_context(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("source")
    addition = ops.add(source, "explicit target fact")
    store.create_context(source)
    store.create_context(ops.init("target"))

    result = runner.invoke(app, ["merge", "source", "--into", "target"])

    assert result.exit_code == 0, result.output + result.stderr
    merged = store.load_direct("target")
    assert addition.uid not in merged.memories
    assert any(
        isinstance(item, Memory) and item.content == "explicit target fact"
        for item in merged.iter_items()
    )
    assert store.current_context_name() is None


def test_cli_merge_accepts_a_positional_target_and_rejects_a_duplicate_alias(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("source")
    addition = ops.add(source, "positional target fact")
    store.create_context(source)
    store.create_context(ops.init("target"))

    result = runner.invoke(app, ["merge", "source", "target"])
    duplicate = runner.invoke(
        app,
        ["merge", "source", "target", "--into", "other"],
    )

    assert result.exit_code == 0, result.output + result.stderr
    merged = store.load_direct("target")
    assert addition.uid not in merged.memories
    assert any(
        isinstance(item, Memory) and item.content == "positional target fact"
        for item in merged.iter_items()
    )
    assert store.current_context_name() is None
    assert duplicate.exit_code == 2
    assert "Target was supplied both positionally and with --into" in duplicate.stderr


def test_cli_merge_accepts_directional_aliases_and_relative_source(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("practice/1")
    addition = ops.add(source, "directional alias fact")
    store.create_context(source)
    store.create_context(ops.init("practice/2"))
    store.set_current("practice/2")

    result = runner.invoke(app, ["merge", "--from", "../1"])

    assert result.exit_code == 0, result.output + result.stderr
    merged = store.load_direct("practice/2")
    assert addition.uid not in merged.memories
    assert any(
        isinstance(item, Memory) and item.content == "directional alias fact"
        for item in merged.iter_items()
    )
    assert "'practice/1' → 'practice/2'" in result.output


def test_cli_merge_accepts_complete_from_to_pair_without_current(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("source")
    addition = ops.add(source, "complete directional pair")
    store.create_context(source)
    store.create_context(ops.init("target"))

    result = runner.invoke(
        app,
        ["merge", "--from", "source", "--to", "target"],
    )

    assert result.exit_code == 0, result.output + result.stderr
    merged = store.load_direct("target")
    assert addition.uid not in merged.memories
    assert any(
        isinstance(item, Memory) and item.content == "complete directional pair"
        for item in merged.iter_items()
    )
    assert store.current_context_name() is None


def test_cli_merge_rejects_duplicate_directional_spellings_before_store_access(
    isolated_store,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        MemoryStore,
        "current_context_name",
        lambda _store: (_ for _ in ()).throw(
            AssertionError("duplicate endpoints opened the Store")
        ),
    )

    source = runner.invoke(app, ["merge", "one", "--from", "two"])
    target = runner.invoke(
        app,
        ["merge", "source", "target", "--to", "other"],
    )
    aliases = runner.invoke(
        app,
        ["merge", "source", "--into", "one", "--to", "two"],
    )

    assert source.exit_code == 2
    assert "Source was supplied both positionally and with --from" in source.stderr
    assert target.exit_code == 2
    assert "Target was supplied both positionally and with --to" in target.stderr
    assert aliases.exit_code == 2
    assert "--into and --to" in aliases.stderr


def test_cli_rejects_conflicting_reach_flags(isolated_store) -> None:
    result = runner.invoke(app, ["merge", "source", "--direct", "--recursive"])

    assert result.exit_code == 2
    assert "choose either --direct or --recursive" in result.stderr


def test_cli_requires_source_outside_a_tty(isolated_store) -> None:
    store = MemoryStore()
    target = ops.init("target")
    store.create_context(target)
    store.set_current(target.name)

    result = runner.invoke(app, ["merge"])

    assert result.exit_code == 1
    assert "requires SOURCE outside a TTY" in result.stderr
