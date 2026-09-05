"""Application-boundary contracts for ordinary Context initialization."""

from __future__ import annotations

import ast
from pathlib import Path
import uuid

import pytest

import memcommit.application.operations.init.application as context_init_application
from memcommit.application.operations.init.application import (
    ContextInitError,
    ContextInitRequest,
    CreatedContext,
    plan_context_init,
    run_context_init,
)
import memcommit.application.operations.init.runtime as context_init_runtime
from memcommit.application.operations.init.runtime import (
    execute_context_init,
    prepare_context_init,
)
from memcommit.adapters.console.commands.init.choose_name import (
    ContextInitTuiSetup,
    run_context_init_tui,
)
import memcommit.application.capabilities.ops as ops
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def _created(name: str, seed: int) -> CreatedContext:
    return CreatedContext(
        name=name,
        uid=str(uuid.UUID(int=seed)),
    )


class _RecordingInitPort:
    def __init__(self, created: tuple[CreatedContext, ...]):
        self.created = created
        self.plans = []

    def apply(self, plan):
        self.plans.append(plan)
        return self.created


def test_single_context_plan_owns_require_new_checkpoint_policy():
    request = ContextInitRequest(
        name="project",
        create_parents=False,
        expected_current="previous",
    )
    plan = plan_context_init(request)

    assert plan.request == request
    assert plan.require_all_new
    assert len(plan.entries) == 1
    [entry] = plan.entries
    assert entry.name == "project"
    assert entry.checkpoint_args == {"name": "project"}
    assert entry.checkpoint_description == "Initialized context 'project'"


def test_parent_plan_preserves_order_and_per_context_checkpoint_evidence():
    request = ContextInitRequest(
        name="project/work/notes",
        create_parents=True,
        expected_current=None,
    )
    plan = plan_context_init(request)

    assert not plan.require_all_new
    assert [entry.name for entry in plan.entries] == [
        "project",
        "project/work",
        "project/work/notes",
    ]
    assert plan.entries[0].checkpoint_args == {
        "name": "project",
        "parents": True,
        "requested_name": "project/work/notes",
    }
    assert plan.entries[0].checkpoint_description == (
        "Initialized namespace parent 'project' for 'project/work/notes'"
    )
    assert plan.entries[-1].checkpoint_description == (
        "Initialized context 'project/work/notes'"
    )


def test_run_context_init_returns_created_and_reused_names_from_one_port():
    request = ContextInitRequest(
        name="project/work",
        create_parents=True,
        expected_current="project",
    )
    port = _RecordingInitPort((_created("project/work", 2),))

    result = run_context_init(request, port=port)

    assert len(port.plans) == 1
    assert result.requested_name == "project/work"
    assert result.created_names == ("project/work",)
    assert result.reused_names == ("project",)
    assert result.current_name == "project/work"


def test_run_context_init_rejects_a_receipt_outside_the_plan():
    request = ContextInitRequest(
        name="project/work",
        create_parents=True,
        expected_current=None,
    )
    port = _RecordingInitPort((_created("outside", 3),))

    with pytest.raises(ContextInitError, match="outside its creation plan"):
        run_context_init(request, port=port)


def test_context_init_application_has_no_command_typer_or_tui_imports():
    source = Path(context_init_application.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    forbidden = tuple(
        name
        for name in imported
        if name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.adapters.console.commands")
        or name.startswith("memcommit.adapters.interfaces")
    )
    assert forbidden == ()


def test_execute_context_init_creates_and_selects_without_terminal_output(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    snapshot = prepare_context_init(store)

    result = execute_context_init(
        ContextInitRequest(
            name="runtime-context",
            create_parents=False,
            expected_current=snapshot.expected_current,
        ),
        store=store,
    )

    assert result.created_names == ("runtime-context",)
    assert result.reused_names == ()
    assert store.current_context_name() == "runtime-context"
    assert store.load_direct("runtime-context").uid == result.created[0].uid
    [checkpoint] = store.list_checkpoints("runtime-context")
    assert checkpoint["command"] == "init"
    assert checkpoint["args"] == {"name": "runtime-context"}
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_execute_context_init_reuses_parent_and_records_new_descendants(
    isolated_store,
):
    store = MemoryStore()
    parent = ops.init("project")
    store.create_context(parent)
    store.set_current(parent.name)
    snapshot = prepare_context_init(store)

    result = execute_context_init(
        ContextInitRequest(
            name="project/work/notes",
            create_parents=True,
            expected_current=snapshot.expected_current,
        ),
        store=store,
    )

    assert result.reused_names == ("project",)
    assert result.created_names == ("project/work", "project/work/notes")
    assert store.current_context_name() == "project/work/notes"
    assert store.list_checkpoints("project") == []
    [work_checkpoint] = store.list_checkpoints("project/work")
    [leaf_checkpoint] = store.list_checkpoints("project/work/notes")
    expected_args = {
        "parents": True,
        "requested_name": "project/work/notes",
    }
    assert work_checkpoint["args"] == {
        "name": "project/work",
        **expected_args,
    }
    assert leaf_checkpoint["args"] == {
        "name": "project/work/notes",
        **expected_args,
    }


def test_parent_mode_can_reuse_the_complete_existing_hierarchy(isolated_store):
    store = MemoryStore()
    parent = ops.init("project")
    leaf = ops.init("project/work")
    store.create_context(parent)
    store.create_context(leaf)
    store.set_current(parent.name)
    snapshot = prepare_context_init(store)

    result = execute_context_init(
        ContextInitRequest(
            name="project/work",
            create_parents=True,
            expected_current=snapshot.expected_current,
        ),
        store=store,
    )

    assert result.created == ()
    assert result.reused_names == ("project", "project/work")
    assert store.current_context_name() == "project/work"
    assert store.list_checkpoints("project") == []
    assert store.list_checkpoints("project/work") == []


def test_exact_mode_collision_preserves_current_and_existing_context(
    isolated_store,
):
    store = MemoryStore()
    existing = ops.init("existing")
    store.create_context(existing)
    store.set_current(existing.name)
    snapshot = prepare_context_init(store)

    with pytest.raises(ContextInitError, match="context 'existing' already exists"):
        execute_context_init(
            ContextInitRequest(
                name="existing",
                create_parents=False,
                expected_current=snapshot.expected_current,
            ),
            store=store,
        )

    assert store.current_context_name() == "existing"
    assert store.load_direct("existing").uid == existing.uid
    assert store.list_checkpoints("existing") == []


def test_current_change_rolls_back_the_new_context_batch(isolated_store):
    store = MemoryStore()
    snapshot = prepare_context_init(store)
    other = ops.init("other")
    store.create_context(other)
    store.set_current(other.name)

    with pytest.raises(
        ConcurrentContextUpdateError,
        match="current Context changed",
    ):
        execute_context_init(
            ContextInitRequest(
                name="project/work",
                create_parents=True,
                expected_current=snapshot.expected_current,
            ),
            store=store,
        )

    assert store.current_context_name() == "other"
    assert not store.context_exists("project")
    assert not store.context_exists("project/work")


def test_context_init_tui_returns_a_request_without_executing_storage():
    observed = {}

    def choose(view):
        observed["view"] = view
        return "project/work"

    request = run_context_init_tui(
        setup=ContextInitTuiSetup(
            expected_current="project",
            context_names=("project",),
            validate_name=lambda value: value,
        ),
        create_parents=True,
        chooser=choose,
    )

    assert request == ContextInitRequest(
        name="project/work",
        create_parents=True,
        expected_current="project",
    )
    assert observed["view"].label == "CONTEXT"
    assert observed["view"].state == "CREATE MISSING PARENTS"
    assert observed["view"].context_names == ()
    assert observed["view"].current_context == "project"
    assert observed["view"].heading == "MEM INIT"
    assert observed["view"].submit_hint == "Enter create and switch"


def test_context_init_tui_cancel_returns_no_request():
    result = run_context_init_tui(
        setup=ContextInitTuiSetup(
            expected_current=None,
            context_names=(),
            validate_name=lambda value: value,
        ),
        create_parents=False,
        chooser=lambda _view: None,
    )

    assert result is None


def test_context_init_console_owns_setup_and_receipt_without_facades():
    repository_root = Path(__file__).resolve().parents[1]
    command_root = repository_root / "src/memcommit/adapters/console/commands/init"
    retired_tui_root = (
        repository_root
        / "src/memcommit/adapters/interfaces/tui/operations/context_init"
    )

    assert (command_root / "choose_name.py").is_file()
    assert (command_root / "receipt.py").is_file()
    assert not tuple(retired_tui_root.glob("*.py"))
    assert not (
        repository_root / "src/memcommit/adapters/interfaces/cli/context_init.py"
    ).exists()


def test_context_init_runtime_has_no_typer_or_tui_imports():
    source = Path(context_init_runtime.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    forbidden = tuple(
        name
        for name in imported
        if name == "typer" or name.startswith("prompt_toolkit")
    )
    assert forbidden == ()
