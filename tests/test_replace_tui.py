"""Interactive contract tests for compact deterministic Replace."""

from __future__ import annotations

import ast
from pathlib import Path

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.commands.replace.proposal import render_replace_plan
from memcommit.adapters.console.commands.replace.receipt import (
    render_replace_apply_result,
)
from memcommit.adapters.console.commands.replace.workbench import (
    ReplaceTuiSetup,
    run_replace_tui,
)
from memcommit.application.operations.replace.application import (
    FrozenReplaceContext,
    FrozenReplacePlan,
    FrozenReplaceSource,
    ReplaceApplyResult,
    ReplaceCheckpoint,
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
        checkpoints = tuple(
            ReplaceCheckpoint(
                context_name=context.context_name,
                context_uid=context.context_uid,
                checkpoint_uid=f"checkpoint-{index}",
            )
            for index, context in enumerate(plan.contexts, start=1)
            if context.changed_matches
        )
        return ReplaceApplyResult(
            plan_digest=plan.plan_digest,
            applied=bool(checkpoints),
            scanned_context_count=plan.scanned_context_count,
            scanned_memory_count=plan.scanned_memory_count,
            matched_memory_count=plan.matched_memory_count,
            changed_memory_count=plan.changed_memory_count,
            occurrence_count=plan.occurrence_count,
            checkpoints=checkpoints,
        )


def _setup() -> ReplaceTuiSetup:
    return ReplaceTuiSetup(
        names=("alpha", "alpha/child", "peer"),
        current_name="alpha",
        initial_targets=("alpha",),
    )


def test_replace_tui_executes_once_from_find_and_replacement_inputs() -> None:
    port = _Port()
    requests: list[ReplaceRequest] = []

    def execute(request: ReplaceRequest) -> ReplaceApplyResult:
        requests.append(request)
        return apply_replace(plan_replace(request, port=port), port=port)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("needle\rpin\r")
        returned = run_replace_tui(
            None,
            setup=_setup(),
            execute=execute,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(returned, ReplaceApplyResult)
    assert returned.applied is True
    assert requests == [ReplaceRequest("needle", "pin", ("alpha",))]
    assert len(port.applied) == 1


def test_replace_tui_closes_without_execution() -> None:
    port = _Port()
    requests: list[ReplaceRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_bytes(b"\x03")
        returned = run_replace_tui(
            None,
            setup=_setup(),
            execute=lambda request: requests.append(request)
            or apply_replace(plan_replace(request, port=port), port=port),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []
    assert port.applied == []


def test_replace_tui_projects_descendants_as_exact_checked_execution_set() -> None:
    port = _Port()
    requests: list[ReplaceRequest] = []

    def execute(request: ReplaceRequest) -> ReplaceApplyResult:
        requests.append(request)
        return apply_replace(plan_replace(request, port=port), port=port)

    with create_pipe_input() as pipe_input:
        # The compact form starts at Find. Shift-Tab reaches Range; Right
        # includes descendants; Tab returns to Find. The first Enter stages
        # Replace With and the second executes the exact visible checked set.
        pipe_input.send_text("\x1b[Z\x1b[Z\x1b[Z\x1b[C\t\t\t\r\r")
        returned = run_replace_tui(
            ReplaceRequest("needle", "pin", ("alpha",)),
            setup=_setup(),
            execute=execute,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(returned, ReplaceApplyResult)
    assert requests[0].target_names == ("alpha", "alpha/child")
    assert requests[0].include_descendants is False


def test_replace_tui_uses_primary_screen_and_erases_when_done() -> None:
    path = (
        Path(__file__).parents[1]
        / "src/memcommit/adapters/console/commands/replace/workbench/screen.py"
    )
    module = ast.parse(path.read_text(encoding="utf-8"))
    application_calls = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "Application")
            or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "Application"
            )
        )
    ]

    assert len(application_calls) == 1
    keywords = {keyword.arg: keyword.value for keyword in application_calls[0].keywords}
    assert isinstance(keywords["full_screen"], ast.Constant)
    assert keywords["full_screen"].value is False
    assert isinstance(keywords["erase_when_done"], ast.Constant)
    assert keywords["erase_when_done"].value is True


def test_replace_console_owns_workbench_proposal_and_receipt_without_facades() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    command_root = repository_root / "src/memcommit/adapters/console/commands/replace"

    assert (command_root / "workbench/model.py").is_file()
    assert (command_root / "workbench/screen.py").is_file()
    assert (command_root / "proposal.py").is_file()
    assert (command_root / "receipt.py").is_file()
    assert not (
        repository_root / "src/memcommit/adapters/interfaces/cli/replace.py"
    ).exists()
    assert not tuple(
        (
            repository_root / "src/memcommit/adapters/interfaces/tui/operations/replace"
        ).glob("*.py")
    )


def test_replace_proposal_and_receipt_present_distinct_command_states() -> None:
    port = _Port()
    plan = plan_replace(ReplaceRequest("needle", "pin", ("alpha",)), port=port)

    proposal = render_replace_plan(plan)
    assert proposal.startswith("REPLACE PLAN · READY FOR REVIEW")
    assert f"PLAN DIGEST · {plan.plan_digest}" in proposal

    receipt = render_replace_apply_result(apply_replace(plan, port=port))
    assert receipt.startswith("Replaced 3 occurrences in 2 Memories")
    assert "PLAN" not in receipt
