"""Interactive contract tests for provider-free deterministic Find."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.interfaces.tui.operations.find import (
    LiteralFindTuiOutcome,
    LiteralFindTuiSetup,
    run_literal_find_tui,
)
from memcommit.application.operations.find.literal_application import (
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
                    source_position=1,
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
    assert copied[0].startswith(
        "1 [memory-1] Alpha needle and another needle. [alpha m1]"
    )
    assert "SPANS" not in copied[0]
    assert copied[1].startswith("FIND RESULTS")
    assert "SPANS" not in copied[1]


def test_find_tui_whole_copy_keeps_initial_all_readable_label() -> None:
    copied: list[str] = []
    setup = _setup()
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\rYq")
        returned = run_literal_find_tui(
            LiteralFindRequest(
                pattern="needle",
                target_names=setup.names,
            ),
            setup=LiteralFindTuiSetup(
                names=setup.names,
                current_name=setup.current_name,
                initial_targets=setup.names,
            ),
            execute=_execute,
            clipboard_writer=copied.append,
            initial_all_readable_contexts=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(returned, LiteralFindTuiOutcome)
    assert "SCOPE · ALL READABLE CONTEXTS" in copied[0]
    assert "SCOPE · alpha + alpha/child + peer" not in copied[0]


def test_find_tui_projects_descendants_as_exact_checked_execution_set() -> None:
    requests: list[LiteralFindRequest] = []
    with create_pipe_input() as pipe_input:
        # The compact form starts at Pattern even though Scope is above it.
        # Shift-Tab reaches Range; Right includes descendants; Tab returns to
        # Pattern, whose Enter runs the exact visible checked set.
        pipe_input.send_text("\x1b[Z\x1b[Z\x1b[Z\x1b[C\t\t\t\rq")
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
