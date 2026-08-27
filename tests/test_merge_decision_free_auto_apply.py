"""Decision-free Merge review bypass and recovery contracts."""

from __future__ import annotations

import typer
from typer.testing import CliRunner

import memcommit.commands.merge.command as merge_command
import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.context import Memory
from memcommit.interfaces.tui.operations.merge import merge_endpoint_setup_spec
from memcommit.interfaces.tui.operations.merge.model import MergeTuiSetup
from memcommit.merge_application import (
    FrozenMergePlan,
    MergeAddition,
    MergeContextResult,
    MergeItemKind,
    MergeReach,
    MergeRequest,
    MergeResult,
)
from memcommit.merge_runtime import execute_merge
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def test_setup_discloses_conditional_auto_apply() -> None:
    spec = merge_endpoint_setup_spec(
        MergeTuiSetup(
            names=("source", "target"),
            selectable_names=frozenset({"source", "target"}),
            selected_source="source",
            target_names=("source", "target"),
            target_selectable_names=frozenset({"source", "target"}),
            target_context="target",
            initial_recursive=False,
            current_context="target",
        )
    )

    assert spec.action_label == "REVIEW MERGE PLAN"
    assert spec.subtitle == "REVIEW REQUIRED CONFLICTS BEFORE APPLY"


def _plan(*, granted: bool, with_addition: bool) -> FrozenMergePlan:
    request = MergeRequest(
        source_locator="source",
        target_locator="target",
        reach=MergeReach.DIRECT,
    )
    additions = (
        (MergeAddition(uid="new-memory", kind=MergeItemKind.MEMORY),)
        if with_addition
        else ()
    )
    context = MergeContextResult(
        source_name="source",
        source_uid="source-uid",
        target_name="target",
        target_uid="target-uid",
        target_created=False,
        additions=additions,
    )
    return FrozenMergePlan(
        request=request,
        source_name=context.source_name,
        source_uid=context.source_uid,
        source_digest="source-digest",
        target_name=context.target_name,
        target_uid=context.target_uid,
        target_digest="target-digest",
        additions=additions,
        contexts=(context,),
        cross_profile_memory_only=False,
        token=object(),
        mutates_granted_authority=granted,
    )


def _result(plan: FrozenMergePlan) -> MergeResult:
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
        cross_profile_memory_only=plan.cross_profile_memory_only,
    )


def _invoke_bare_merge(monkeypatch, plan: FrozenMergePlan) -> tuple[object, list[str]]:
    port = object()
    events: list[str] = []

    class FakeStore:
        def current_context_name(self) -> str:
            return "target"

    monkeypatch.setattr(merge_command, "MemoryStore", FakeStore)
    monkeypatch.setattr(
        merge_command,
        "MemoryStoreMergePort",
        lambda _store, *, current_name: port,
    )
    monkeypatch.setattr(merge_command, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        merge_command,
        "build_merge_tui_setup",
        lambda _port, *, initial_recursive, requested_target: object(),
    )
    monkeypatch.setattr(
        merge_command,
        "choose_merge_setup",
        lambda _setup: plan.request,
    )
    monkeypatch.setattr(
        merge_command,
        "prepare_merge",
        lambda request, *, port: plan,
    )

    def apply(request, *, port, frozen_plan, **_kwargs):
        assert request == plan.request
        assert frozen_plan is plan
        events.append("apply")
        return _result(plan)

    def review(frozen, *, apply_plan, **_kwargs):
        assert frozen is plan
        events.append("review")
        return apply_plan(frozen)

    monkeypatch.setattr(merge_command, "run_merge", apply)
    monkeypatch.setattr(merge_command, "run_merge_plan_review", review)
    monkeypatch.setattr(
        merge_command,
        "run_merge_conflict_review",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("a decision-free plan must not open conflict review")
        ),
    )
    monkeypatch.setattr(
        merge_command,
        "render_merge_plain",
        lambda _result: events.append("receipt"),
    )

    command_app = typer.Typer()

    @command_app.callback()
    def root() -> None:
        """Keep the focused test application in command-group mode."""

    command_app.command("merge")(merge_command.cmd)
    invoked = runner.invoke(command_app, ["merge"])
    return invoked, events


def test_local_decision_free_merge_skips_duplicate_review_and_applies(monkeypatch):
    invoked, events = _invoke_bare_merge(
        monkeypatch,
        _plan(granted=False, with_addition=True),
    )

    assert invoked.exit_code == 0, invoked.output
    assert events == ["apply", "receipt"]


def test_local_verified_noop_also_skips_review_but_keeps_receipt(monkeypatch):
    invoked, events = _invoke_bare_merge(
        monkeypatch,
        _plan(granted=False, with_addition=False),
    )

    assert invoked.exit_code == 0, invoked.output
    assert events == ["apply", "receipt"]


def test_granted_authority_decision_free_merge_retains_final_review(monkeypatch):
    invoked, events = _invoke_bare_merge(
        monkeypatch,
        _plan(granted=True, with_addition=False),
    )

    assert invoked.exit_code == 0, invoked.output
    assert events == ["review", "apply", "receipt"]


def test_verified_noop_checkpoint_remains_one_undo_redo_unit(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    source.add(Memory(uid="same", content="same"))
    store.create_context(source, None)
    target = ops.init("target")
    target.add(Memory(uid="same", content="same"))
    store.create_context(target, None)
    store.set_current("target")

    result = execute_merge(MergeRequest(source_locator="source"), store=store)

    assert result.additions == ()
    assert len(result.checkpoint_uids) == 1
    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output + undone.stderr
    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output + redone.stderr
    assert store.load_direct("target").memories["same"].content == "same"
