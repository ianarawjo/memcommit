"""Interactive Add draft and terminal-flow contracts."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.application.context_access.granted_context_navigation import (
    GrantedContextNavigation,
)
from memcommit.application.operations.add.application import (
    AddedMemory,
    AddRequest,
    AddResult,
)
from memcommit.adapters.console.commands.add.workbench import (
    AddDraftState,
    AddWorkbenchSetup,
    build_add_workbench_setup,
    run_add_workbench,
)
import memcommit.adapters.console.commands.add.workbench.setup as add_workbench_setup
from memcommit.persistence.store import MemoryStore


def _setup(*names: str, selected: str = "target") -> AddWorkbenchSetup:
    return AddWorkbenchSetup(
        names=names or ("target",),
        selectable_names=frozenset(names or ("target",)),
        selected_context=selected,
        current_context=selected,
    )


def _result(request: AddRequest) -> AddResult:
    return AddResult(
        context_name=request.context_locator or "target",
        context_uid="context-uid",
        memories=tuple(
            AddedMemory(uid=f"memory-{index}", content=content)
            for index, content in enumerate(request.contents, start=1)
        ),
        checkpoint_uid="checkpoint-uid",
    )


def test_build_workbench_setup_freezes_local_targets_and_specified_selection(
    isolated_store,
) -> None:
    store = MemoryStore()
    store.create_context(ops.init("beta"))
    store.create_context(ops.init("alpha"))
    store.set_current("beta")

    setup = build_add_workbench_setup(
        store,
        current_context_name="beta",
        specified_context_locator="alpha",
    )

    assert setup.names == ("alpha", "beta")
    assert setup.selectable_names == frozenset({"alpha", "beta"})
    assert setup.selected_context == "alpha"
    assert setup.current_context == "beta"


def test_build_workbench_setup_prefers_nearest_selectable_parent(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    store.create_context(ops.init("alpha"))
    store.create_context(ops.init("alpha/project"))
    monkeypatch.setattr(
        add_workbench_setup,
        "freeze_granted_context_navigation",
        lambda _store: GrantedContextNavigation((), {}, frozenset()),
    )

    setup = build_add_workbench_setup(
        store,
        current_context_name="alpha/project/task",
        specified_context_locator=None,
    )

    assert setup.selected_context == "alpha/project"


def test_build_workbench_setup_uses_catalog_fallback_without_selectable_parent(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    store.create_context(ops.init("zeta"))
    store.create_context(ops.init("alpha"))
    monkeypatch.setattr(
        add_workbench_setup,
        "freeze_granted_context_navigation",
        lambda _store: GrantedContextNavigation((), {}, frozenset()),
    )

    setup = build_add_workbench_setup(
        store,
        current_context_name="unrelated/task",
        specified_context_locator=None,
    )

    assert setup.selected_context == "alpha"


def test_build_workbench_setup_rejects_an_empty_target_catalog(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    monkeypatch.setattr(
        add_workbench_setup,
        "freeze_granted_context_navigation",
        lambda _store: GrantedContextNavigation((), {}, frozenset()),
    )

    with pytest.raises(
        ValueError,
        match="Interactive Add requires a local or CREATE-granted target Context",
    ):
        build_add_workbench_setup(
            store,
            current_context_name=None,
            specified_context_locator=None,
        )


def test_draft_state_preserves_multiline_text_and_cancelled_new_draft() -> None:
    state = AddDraftState()
    state.begin_edit()
    state.save_edit("First line.\nSecond line.")
    state.new()
    state.cancel_edit()

    assert state.drafts == ["First line.\nSecond line."]
    assert state.ready_contents == ("First line.\nSecond line.",)


def test_draft_state_supports_ordered_create_edit_and_delete() -> None:
    state = AddDraftState()
    state.begin_edit()
    state.save_edit("First")
    state.new()
    state.save_edit("Second")
    state.move(-1)
    state.begin_edit()
    state.save_edit("First revised")
    state.move(1)
    state.delete_selected()

    assert state.ready_contents == ("First revised",)
    assert state.cursor == 0


def test_workbench_e_to_edit_adds_multiple_explicit_multiline_drafts() -> None:
    requests: list[AddRequest] = []

    def execute(request: AddRequest) -> AddResult:
        requests.append(request)
        return _result(request)

    with create_pipe_input() as pipe_input:
        # Initial focus is the draft surface. Enter is an editor newline,
        # Ctrl-S saves locally, N starts another draft, and the To Do Enter is
        # the only durable action. A final Enter closes the success receipt.
        pipe_input.send_text("eFirst line.\rSecond line.\x13nAnother.\x13\t\r\r")
        returned = run_add_workbench(
            setup=_setup(),
            execute=execute,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == _result(requests[0])
    assert len(requests) == 1
    assert requests[0].contents == (
        "First line.\nSecond line.",
        "Another.",
    )
    assert requests[0].context_locator == "target"


def test_workbench_context_selector_changes_exact_add_target() -> None:
    requests: list[AddRequest] = []
    with create_pipe_input() as pipe_input:
        # Shift-Tab reaches the shared Context selector, Up selects alpha,
        # Enter stages it, Tab returns to drafts, and the normal draft flow
        # executes against that exact selected Context.
        pipe_input.send_text("\x1b[Z\x1b[A\r\teOnly alpha receives this.\x13\t\r\r")
        returned = run_add_workbench(
            setup=_setup("alpha", "target", selected="target"),
            execute=lambda request: requests.append(request) or _result(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert requests[0].context_locator == "alpha"


def test_workbench_escape_cancels_without_calling_application() -> None:
    requests: list[AddRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_add_workbench(
            setup=_setup(),
            execute=lambda request: requests.append(request) or _result(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []


def test_workbench_ctrl_c_cancels_without_calling_application() -> None:
    requests: list[AddRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("eUncommitted draft.\x03")
        returned = run_add_workbench(
            setup=_setup(),
            execute=lambda request: requests.append(request) or _result(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []
