"""Interactive and public CLI contracts for structural Merge reach."""

from __future__ import annotations

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
    merge_exact_command_review,
    run_merge_tui,
)
from memcommit.merge_application import (
    MergeAddition,
    MergeContextResult,
    MergeError,
    MergeItemKind,
    MergeReach,
    MergeRequest,
    MergeResult,
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


def test_tui_direct_merge_executes_only_from_exact_review() -> None:
    requests: list[MergeRequest] = []
    with create_pipe_input() as pipe_input:
        # Source owns first focus. Tab reaches the exact command; one Enter
        # applies it and a second closes the durable success receipt.
        pipe_input.send_text("\t\r\r")
        returned = run_merge_tui(
            setup=_setup(),
            execute=lambda request: requests.append(request) or _result(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == _result(requests[0])
    assert requests == [MergeRequest(source_locator="source", reach=MergeReach.DIRECT)]


def test_tui_recursive_range_reaches_the_same_typed_application() -> None:
    requests: list[MergeRequest] = []
    with create_pipe_input() as pipe_input:
        # Shift-Tab reaches Range above Source, Right selects descendants,
        # then two Tabs reach the exact command.
        pipe_input.send_text("\x1b[Z\x1b[C\t\t\r\r")
        returned = run_merge_tui(
            setup=_setup(),
            execute=lambda request: requests.append(request) or _result(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert requests == [
        MergeRequest(source_locator="source", reach=MergeReach.DESCENDANTS)
    ]


def test_tui_escape_cancels_without_calling_the_application() -> None:
    requests: list[MergeRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_merge_tui(
            setup=_setup(),
            execute=lambda request: requests.append(request) or _result(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []


def test_tui_application_failure_stays_open_and_returns_no_receipt() -> None:
    requests: list[MergeRequest] = []

    def fail(request: MergeRequest) -> MergeResult:
        requests.append(request)
        raise RuntimeError("injected Merge failure")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\rq")
        with pytest.raises(MergeError, match="injected Merge failure"):
            run_merge_tui(
                setup=_setup(),
                execute=fail,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

    assert requests == [MergeRequest(source_locator="source", reach=MergeReach.DIRECT)]


def test_exact_review_names_recursive_path_and_frozen_target() -> None:
    review = merge_exact_command_review(
        "source",
        "target",
        recursive=True,
    )

    assert review.argv == ("mem", "merge", "source", "--recursive")
    assert any("complete relative path" in effect for effect in review.effects)
    assert any("Target subtree 'target'" in effect for effect in review.effects)


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
