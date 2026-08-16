"""Interactive and public CLI contracts for structural Merge reach."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.interfaces.tui.operations.merge.adapter as merge_tui_adapter
from memcommit.cli import app
from memcommit.interfaces.tui.operations.merge import (
    MergeTuiSetup,
    build_merge_tui_setup,
    choose_merge_setup,
    merge_exact_command_review,
    merge_endpoint_setup_spec,
    merge_plan_exact_command_review,
    merge_resolution_spec,
    project_merge_plan,
    run_merge_conflict_review,
    run_merge_plan_review,
)
from memcommit.merge_application import (
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
from memcommit.merge_runtime import MemoryStoreMergePort
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _setup(*, recursive: bool = False) -> MergeTuiSetup:
    return MergeTuiSetup(
        names=("source", "target"),
        selectable_names=frozenset({"source"}),
        selected_source="source",
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
    assert "STATUS · FROZEN · NOT APPLIED" in rendered
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
    plan = _conflict_plan()
    applied: list[tuple[MergeResolution, ...]] = []
    with create_pipe_input() as pipe_input:
        # Viewer → Items → To Do, K opens the fused bulk exact review, then
        # Enter applies and the next Enter closes the visible receipt.
        pipe_input.send_text("\t\tk\r\r")
        returned = run_merge_conflict_review(
            plan,
            apply_plan=lambda frozen, resolutions: (
                applied.append(resolutions)
                or _resolved_result(frozen, resolutions)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert applied == [
        (
            MergeResolution(
                "merge-conflict:test",
                MergeDecision.KEEP_TARGET,
            ),
        )
    ]


def test_conflict_workbench_item_choice_and_clipboard_contract() -> None:
    plan = _conflict_plan()
    copied: list[str] = []
    applied: list[tuple[MergeResolution, ...]] = []
    with create_pipe_input() as pipe_input:
        # y/Y copy the focused and complete report. Open the item, choose the
        # first real response, then separately enter final review and Apply.
        pipe_input.send_text("yY\t\r\t\r\t\t\r\r\r")
        returned = run_merge_conflict_review(
            plan,
            apply_plan=lambda frozen, resolutions: (
                applied.append(resolutions)
                or _resolved_result(frozen, resolutions)
            ),
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert len(copied) == 2
    assert "MERGE PLAN" in copied[0]
    assert "MAPPING 1/1" in copied[1]
    assert applied[0][0].decision is MergeDecision.KEEP_TARGET


def test_merge_resolution_spec_has_no_custom_choice() -> None:
    spec = merge_resolution_spec(_conflict_plan())

    assert [choice.uid for choice in spec.items[0].choices] == [
        "KEEP_TARGET",
        "TAKE_SOURCE",
    ]


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

    assert review.argv == ("mem", "merge", "source", "--direct")
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


def test_exact_review_names_recursive_path_and_frozen_target() -> None:
    review = merge_exact_command_review(
        "source",
        "target",
        recursive=True,
    )

    assert review.argv == ("mem", "merge", "source", "--recursive")
    assert any("complete relative path" in effect for effect in review.effects)
    assert any("Target subtree 'target'" in effect for effect in review.effects)


def test_meld_style_setup_projects_coupled_reach_and_frozen_target() -> None:
    spec = merge_endpoint_setup_spec(_setup())

    assert tuple(mode.uid for mode in spec.modes) == ("DIRECT", "DESCENDANTS")
    assert spec.roles[0].uid == "A"
    assert spec.roles[0].fixed is False
    assert spec.roles[1].uid == "B"
    assert spec.roles[1].selected_name == "target"
    assert spec.roles[1].fixed is True


def test_meld_style_setup_returns_typed_recursive_request() -> None:
    with create_pipe_input() as pipe_input:
        # A multi-shape setup starts on MODE. Right selects recursive, then
        # Source and Continue are the next two visible focus surfaces.
        pipe_input.send_text("\x1b[C\t\t\r")
        request = choose_merge_setup(
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


def test_meld_style_setup_cancel_returns_no_request() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        request = choose_merge_setup(
            _setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert request is None


def test_tui_setup_freezes_local_source_and_current_target(isolated_store) -> None:
    store = MemoryStore()
    store.create_context(ops.init("source"))
    store.create_context(ops.init("target"))
    store.set_current("target")

    setup = build_merge_tui_setup(
        MemoryStoreMergePort.capture(store),
        initial_recursive=True,
    )

    assert setup.names == ("source", "target")
    assert setup.selectable_names == frozenset({"source"})
    assert setup.selected_source == "source"
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
            selectable_virtual_names=frozenset({"granted/readable"}),
            virtual_annotations={
                "granted/readable": "READ GRANT",
                "granted/query-only": "QUERY GRANT",
            },
        )

    monkeypatch.setattr(
        merge_tui_adapter,
        "freeze_profile_context_navigation",
        freeze_profile,
    )

    setup = build_merge_tui_setup(
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
        {"granted/readable", "local-source", "other-local"}
    )
    assert setup.annotations == (("granted/readable", "READ GRANT"),)
    assert "granted/query-only" not in setup.names


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
    assert "Recursively merged 'source' into 'target'" in result.output
    assert "2 Contexts, 1 created" in result.output
    assert child_memory.uid in store.load_direct("target/child").memories


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
    assert "1 Context, 0 created" in result.output
    assert "1 checkpoint." in result.output


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
