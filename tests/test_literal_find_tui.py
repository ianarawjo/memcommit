"""Interactive contract tests for provider-free deterministic Find."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.interfaces.tui.operations.find import (
    LiteralFindTuiOutcome,
    LiteralFindTuiSetup,
    run_literal_find_tui,
)
from memcommit.literal_find_application import (
    FrozenLiteralFindSource,
    LiteralFindRequest,
    LiteralFindSourceItem,
    run_literal_find,
)


class _Source:
    def freeze(self, _request):
        return FrozenLiteralFindSource(
            (
                LiteralFindSourceItem(
                    context_name="alpha",
                    context_uid="context-1",
                    kind="memory",
                    item_uid="memory-1",
                    content="Alpha needle and another needle.",
                ),
            )
        )


def _execute(request: LiteralFindRequest):
    return run_literal_find(request, source_port=_Source())


def _setup() -> LiteralFindTuiSetup:
    return LiteralFindTuiSetup(
        names=("alpha", "alpha/child", "peer"),
        current_name="alpha",
        initial_targets=("alpha",),
    )


def test_find_tui_runs_only_after_enter_and_returns_complete_result() -> None:
    requests: list[LiteralFindRequest] = []

    def execute(request: LiteralFindRequest):
        requests.append(request)
        return _execute(request)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\rq")
        returned = run_literal_find_tui(
            LiteralFindRequest(pattern="needle", target_names=("alpha",)),
            setup=_setup(),
            execute=execute,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(returned, LiteralFindTuiOutcome)
    assert returned.result.occurrence_count == 2
    assert requests == [
        LiteralFindRequest(pattern="needle", target_names=("alpha",))
    ]


def test_find_tui_closes_without_execution() -> None:
    requests: list[LiteralFindRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_bytes(b"\x03")
        returned = run_literal_find_tui(
            None,
            setup=_setup(),
            execute=lambda request: requests.append(request) or _execute(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []


def test_find_tui_lowercase_y_copies_focused_and_uppercase_y_copies_all() -> None:
    copied: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\ryYq")
        returned = run_literal_find_tui(
            LiteralFindRequest(pattern="needle", target_names=("alpha",)),
            setup=_setup(),
            execute=_execute,
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(returned, LiteralFindTuiOutcome)
    assert len(copied) == 2
    assert copied[0].startswith("alpha · MEMORY · memory-1")
    assert copied[1].startswith("FIND RESULTS")


def test_find_tui_projects_descendants_as_exact_checked_execution_set() -> None:
    requests: list[LiteralFindRequest] = []
    with create_pipe_input() as pipe_input:
        # Pattern -> targets -> scope; move to lexical range, select descendants,
        # then Enter runs the exact checked rows visible in the tree.
        pipe_input.send_text("\t\t\x1b[B\x1b[C\rq")
        returned = run_literal_find_tui(
            LiteralFindRequest(pattern="needle", target_names=("alpha",)),
            setup=_setup(),
            execute=lambda request: requests.append(request) or _execute(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(returned, LiteralFindTuiOutcome)
    assert requests[0].target_names == ("alpha", "alpha/child")
    assert requests[0].include_descendants is False
