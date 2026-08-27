"""Contracts for Update's shared Endpoint Setup adapter."""

from __future__ import annotations

from click import Group, Option
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest
from typer.main import get_command

import memcommit.adapters.console.commands.update.setup as update_setup_command
import memcommit.adapters.console.commands.update.command as update_command
import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.interfaces.tui.components.endpoint_setup import EndpointSetupMemory
from memcommit.adapters.interfaces.tui.operations.update import (
    UpdateEndpointSelection,
    UpdateTuiSetup,
    choose_update_endpoint_setup,
    update_endpoint_setup_spec,
)


SOURCE_UID = "11111111-1111-4111-8111-111111111111"
TARGET_UID = "22222222-2222-4222-8222-222222222222"


def _setup() -> UpdateTuiSetup:
    return UpdateTuiSetup(
        names=("source", "target"),
        source_name="source",
        target_name="target",
        current_context="source",
    )


def _load(role_uid: str, context_name: str):
    uid = SOURCE_UID if context_name == "source" else TARGET_UID
    return (
        EndpointSetupMemory(
            context_name,
            uid,
            f"{role_uid} exact Memory in {context_name}.",
        ),
    )


def test_update_setup_projects_two_independent_shared_endpoint_roles() -> None:
    spec = update_endpoint_setup_spec(_setup())

    assert spec.initial_mode_uid == "UPDATE"
    assert tuple(role.uid for role in spec.roles) == ("A", "B")
    assert all(role.allow_descendants for role in spec.roles)
    assert all(role.allow_memory_focus for role in spec.roles)
    assert spec.roles[0].selected_name == "source"
    assert spec.roles[1].selected_name == "target"


def test_update_cli_exposes_common_and_role_specific_scope_controls() -> None:
    command = get_command(app)
    assert isinstance(command, Group)
    update = command.commands["update"]
    spellings = {
        spelling
        for parameter in update.params
        if isinstance(parameter, Option)
        for spelling in (*parameter.opts, *parameter.secondary_opts)
    }

    assert {"-d", "--direct", "-r", "--recursive"} <= spellings
    assert {
        "--source-descendants",
        "--source-root-only",
        "--source-only",
        "--target-descendants",
        "--target-root-only",
        "--target-only",
    } <= spellings


@pytest.mark.parametrize(
    ("keys", "source_descendants", "target_descendants"),
    (
        ("\t\t\t\t\t\t\r", False, False),
        ("\t\x1b[C\t\t\t\t\t\r", True, False),
        ("\t\t\t\t\x1b[C\t\t\r", False, True),
        ("\t\x1b[C\t\t\t\x1b[C\t\t\r", True, True),
    ),
)
def test_update_setup_returns_all_independent_range_combinations(
    keys: str,
    source_descendants: bool,
    target_descendants: bool,
) -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keys)
        selected = choose_update_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == UpdateEndpointSelection(
        "source",
        "target",
        source_descendants=source_descendants,
        target_descendants=target_descendants,
    )


def test_update_setup_can_focus_one_exact_memory_per_side() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\x1b[B\r\t\t\t\x1b[B\r\t\r")
        selected = choose_update_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == UpdateEndpointSelection(
        "source",
        "target",
        source_memory_uid=SOURCE_UID,
        target_memory_uid=TARGET_UID,
    )


def test_update_setup_keeps_source_memory_and_target_descendants_independent() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\x1b[B\r\t\t\x1b[C\t\t\r")
        selected = choose_update_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == UpdateEndpointSelection(
        "source",
        "target",
        target_descendants=True,
        source_memory_uid=SOURCE_UID,
    )


def test_update_setup_rejects_identical_or_unknown_defaults() -> None:
    with pytest.raises(ValueError, match="distinct available"):
        UpdateTuiSetup(
            names=("source", "target"),
            source_name="source",
            target_name="source",
        )
    with pytest.raises(ValueError, match="distinct available"):
        UpdateTuiSetup(
            names=("source", "target"),
            source_name="source",
            target_name="missing",
        )


def test_update_command_composition_preserves_a_frozen_readable_catalog(
    monkeypatch,
) -> None:
    source = ops.init("source")
    source_memory = ops.add(source, "Source Memory.")
    granted_target = ops.init("granted/target")
    target_memory = ops.add(granted_target, "Granted target Memory.")
    contexts = {source.name: source, granted_target.name: granted_target}
    loaded: list[str] = []

    class Store:
        def list_context_names(self):
            return [source.name]

        def current_context_name(self):
            return source.name

    class Access:
        def __init__(self, *, granted: bool):
            self.is_granted = granted

    class Catalog:
        def list_context_names(self):
            return [source.name, granted_target.name]

        def access_for(self, name: str):
            return Access(granted=name == granted_target.name)

        def load(self, name: str):
            loaded.append(name)
            return contexts[name]

    monkeypatch.setattr(
        update_setup_command,
        "freeze_profile_readable_context_catalog",
        lambda *_args, **_kwargs: Catalog(),
    )
    monkeypatch.setattr(
        update_setup_command,
        "context_access_display_facts",
        lambda _access: "READ GRANT",
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\x1b[B\r\t\t\t\x1b[B\r\t\r")
        receipt = update_setup_command.choose_update_setup(
            Store(),  # type: ignore[arg-type]
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == update_setup_command.UpdateSetupReceipt(
        source.name,
        granted_target.name,
        source_memory_uid=source_memory.uid,
        target_memory_uid=target_memory.uid,
    )
    assert loaded == [source.name, granted_target.name]


def test_empty_update_launcher_forwards_the_reviewed_memory_uids(
    isolated_store,
    monkeypatch,
) -> None:
    store = update_setup_command.MemoryStore()

    class TTY:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(update_command.sys, "stdin", TTY())
    monkeypatch.setattr(update_command.sys, "stdout", TTY())
    monkeypatch.setattr(
        update_command,
        "choose_session",
        lambda _entries, **kwargs: kwargs["new_receipt"],
    )
    monkeypatch.setattr(
        update_command,
        "choose_update_setup",
        lambda _store: update_setup_command.UpdateSetupReceipt(
            "source",
            "target",
            source_memory_uid=SOURCE_UID,
            target_memory_uid=TARGET_UID,
        ),
    )
    invoked: list[dict[str, object]] = []
    monkeypatch.setattr(update_command, "cmd", lambda **kwargs: invoked.append(kwargs))

    update_command._browse_saved_update(store)

    assert invoked == [
        {
            "source_name": "source",
            "target_name": "target",
            "source_descendants": False,
            "target_descendants": False,
            "source_memory": SOURCE_UID,
            "target_memory": TARGET_UID,
        }
    ]
