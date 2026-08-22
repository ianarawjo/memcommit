"""Interactive contract tests for deterministic Replace."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.interfaces.tui.operations.replace import (
    ReplaceTuiOutcome,
    ReplaceTuiSetup,
    run_replace_tui,
)
from memcommit.replace_application import (
    FrozenReplaceContext,
    FrozenReplacePlan,
    FrozenReplaceSource,
    ReplaceApplyResult,
    ReplaceRequest,
    ReplaceSourceMemory,
    apply_replace,
    plan_replace,
)


class _Port:
    def __init__(self) -> None:
        self.applied: list[FrozenReplacePlan] = []

    def freeze(self, _request: ReplaceRequest) -> FrozenReplaceSource:
        return FrozenReplaceSource(
            (
                FrozenReplaceContext(
                    name="alpha",
                    uid="context-1",
                    digest="digest-1",
                    memories=(
                        ReplaceSourceMemory(
                            uid="memory-1",
                            content="Alpha needle and another needle.",
                        ),
                    ),
                ),
                FrozenReplaceContext(
                    name="alpha/child",
                    uid="context-2",
                    digest="digest-2",
                    memories=(
                        ReplaceSourceMemory(
                            uid="memory-2",
                            content="A child needle.",
                        ),
                    ),
                ),
            ),
            token=self,
        )

    def apply(self, plan: FrozenReplacePlan) -> ReplaceApplyResult:
        self.applied.append(plan)
        return ReplaceApplyResult(
            plan_digest=plan.plan_digest,
            applied=False,
            scanned_context_count=plan.scanned_context_count,
            scanned_memory_count=plan.scanned_memory_count,
            matched_memory_count=plan.matched_memory_count,
            changed_memory_count=plan.changed_memory_count,
            occurrence_count=plan.occurrence_count,
            checkpoints=(),
        )


def _setup() -> ReplaceTuiSetup:
    return ReplaceTuiSetup(
        names=("alpha", "alpha/child", "peer"),
        current_name="alpha",
        initial_targets=("alpha",),
    )


def test_replace_tui_plans_then_applies_only_after_exact_review_enter() -> None:
    port = _Port()
    requests: list[ReplaceRequest] = []

    def prepare(request: ReplaceRequest) -> FrozenReplacePlan:
        requests.append(request)
        return plan_replace(request, port=port)

    with create_pipe_input() as pipe_input:
        # Pattern -> replacement -> targets -> scope; Enter prepares. Review ->
        # To Do; Enter applies. A second Enter closes the completed workbench.
        pipe_input.send_text("\t\t\t\r\t\r\r")
        returned = run_replace_tui(
            ReplaceRequest("needle", "pin", ("alpha",)),
            setup=_setup(),
            prepare=prepare,
            apply=lambda plan: apply_replace(plan, port=port),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(returned, ReplaceTuiOutcome)
    assert returned.apply_result is not None
    assert len(requests) == 1
    assert port.applied == [returned.plan]


def test_replace_tui_closes_without_plan_or_mutation() -> None:
    port = _Port()
    requests: list[ReplaceRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_bytes(b"\x03")
        returned = run_replace_tui(
            None,
            setup=_setup(),
            prepare=lambda request: requests.append(request)
            or plan_replace(request, port=port),
            apply=lambda plan: apply_replace(plan, port=port),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []
    assert port.applied == []


def test_replace_tui_lowercase_y_copies_one_change_and_uppercase_y_the_plan() -> None:
    port = _Port()
    copied: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\ryYq")
        returned = run_replace_tui(
            ReplaceRequest("needle", "pin", ("alpha",)),
            setup=_setup(),
            prepare=lambda request: plan_replace(request, port=port),
            apply=lambda plan: apply_replace(plan, port=port),
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(returned, ReplaceTuiOutcome)
    assert len(copied) == 2
    assert copied[0].startswith("alpha · MEMORY memory-1")
    assert copied[1].startswith("REPLACE PLAN · READY FOR REVIEW")
    assert port.applied == []


def test_replace_tui_projects_descendants_as_exact_checked_execution_set() -> None:
    port = _Port()
    requests: list[ReplaceRequest] = []

    def prepare(request: ReplaceRequest) -> FrozenReplacePlan:
        requests.append(request)
        return plan_replace(request, port=port)

    with create_pipe_input() as pipe_input:
        # Pattern -> replacement -> targets -> scope; move to lexical range,
        # select descendants, then Enter plans the exact checked tree rows.
        pipe_input.send_text("\t\t\t\x1b[B\x1b[C\rq")
        returned = run_replace_tui(
            ReplaceRequest("needle", "pin", ("alpha",)),
            setup=_setup(),
            prepare=prepare,
            apply=lambda plan: apply_replace(plan, port=port),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(returned, ReplaceTuiOutcome)
    assert requests[0].target_names == ("alpha", "alpha/child")
    assert requests[0].include_descendants is False
