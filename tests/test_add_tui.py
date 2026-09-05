"""Interactive compact Add and read-only Viewer contracts."""

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
    AddWorkbenchSetup,
    build_add_workbench_setup,
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


def _run(keys: str, *, names=("target",), selected="target", execute=None, load=None):
    from memcommit.adapters.console.commands.add.workbench.screen import _AddWorkbench

    requests = []
    rows = {name: [] for name in names}

    def save(request):
        requests.append(request)
        result = _result(request)
        rows[result.context_name].extend(result.memories)
        return result

    with create_pipe_input() as pipe_input:
        workbench = _AddWorkbench(
            setup=_setup(*names, selected=selected),
            execute=execute or save,
            load_memories=load or (lambda name: tuple(rows[name])),
            app_input=pipe_input,
            app_output=DummyOutput(),
        )
        pipe_input.send_text(keys)
        result = workbench.run()
    return result, requests, workbench


def test_enter_adds_repeated_memories_and_close_returns_each_receipt():
    results, requests, screen = _run("First Memory.\rSecond Memory.\r\x1b")
    assert [request.contents for request in requests] == [
        ("First Memory.",),
        ("Second Memory.",),
    ]
    assert results == tuple(_result(request) for request in requests)
    assert screen.memory_input.text == ""
    assert "First Memory." in screen.viewer.text_area.text
    assert "Second Memory." in screen.viewer.text_area.text


def test_context_selection_refreshes_viewer_and_changes_only_selected_target():
    # ADD -> CONTEXT -> open tree -> alpha -> commit -> VIEWER -> ADD.
    results, requests, screen = _run(
        "\t\r\x1b[A\r\t\tOnly alpha.\r\x1b",
        names=("alpha", "target"),
        load=lambda name: (AddedMemory(uid=name, content=f"Contents of {name}"),),
    )
    assert results[0].context_name == "alpha"
    assert requests[0].context_locator == "alpha"
    assert "Contents of alpha" in screen.viewer.text_area.text
    assert "Contents of target" not in screen.viewer.text_area.text


def test_context_browser_back_discards_hover_and_keeps_input():
    results, requests, screen = _run(
        "Kept draft\t\r\x1b[A\x7f\t\t\r\x1b",
        names=("alpha", "target"),
    )
    assert requests[0].context_locator == "target"
    assert requests[0].contents == ("Kept draft",)
    assert not screen.context.is_open
    assert len(results) == 1


@pytest.mark.parametrize("keys", ["\x1b", "Uncommitted\x03", "\r\x1b"])
def test_close_interrupt_and_blank_enter_do_not_call_application(keys):
    results, requests, _screen = _run(keys)
    assert results == ()
    assert requests == []


@pytest.mark.parametrize("line_ending", ["\n", "\r", "\r\n"])
def test_backspace_edits_input_and_multiline_paste_is_rejected(line_ending):
    results, requests, screen = _run(
        f"Keepx\x7f\x1b[200~first{line_ending}second\x1b[201~\r\x1b"
    )
    assert requests[0].contents == ("Keep",)
    assert len(results) == len(requests) == 1
    assert "first" not in screen.viewer.text_area.text
    assert "second" not in screen.viewer.text_area.text
    assert screen.memory_input.text == ""


def test_failed_add_retains_input_for_retry_without_a_success_receipt():
    attempts = []

    def execute(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise RuntimeError("write failed")
        return _result(request)

    results, _, screen = _run("Retry me\r\r\x1b", execute=execute)
    assert len(results) == 1
    assert attempts[0] == attempts[1]
    assert attempts[1].contents == ("Retry me",)
    assert screen.memory_input.text == ""


def test_viewer_failure_after_save_clears_input_without_retrying_saved_memory():
    loads = []

    def load(name):
        loads.append(name)
        if len(loads) == 1:
            return (AddedMemory(uid="old", content="Old Viewer contents"),)
        raise RuntimeError("read revoked")

    results, requests, screen = _run("Saved once\r\r\x1b", load=load)
    assert len(results) == len(requests) == 1
    assert screen.memory_input.text == ""
    assert "Old Viewer contents" not in screen.viewer.text_area.text
    assert "Memories unavailable" in screen.viewer.text_area.text


def test_viewer_load_error_clears_previous_context_without_disabling_add():
    def load(name):
        if name == "alpha":
            raise OSError("Memory list temporarily unavailable")
        return (AddedMemory(uid="old", content="Previous Context contents"),)

    results, requests, screen = _run(
        "\t\r\x1b[A\r\t\tNew Memory\r\x1b",
        names=("alpha", "target"),
        load=load,
    )
    assert len(results) == len(requests) == 1
    assert requests[0].context_locator == "alpha"
    assert "Previous Context contents" not in screen.viewer.text_area.text
    assert "Memories unavailable" in screen.viewer.text_area.text
