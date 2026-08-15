"""Contracts for Meld's shared Endpoint Setup adapter."""

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.commands.meld as meld_command
import memcommit.commands.meld_setup as meld_setup_command
import memcommit.ops as ops
from memcommit.interfaces.tui.components.endpoint_setup import EndpointSetupMemory
from memcommit.interfaces.tui.operations.meld import (
    MeldEndpointSelection,
    MeldTuiSetup,
    choose_meld_endpoint_setup,
    meld_endpoint_setup_spec,
)
from memcommit.store import MemoryStore


LEFT_UID = "11111111-1111-4111-8111-111111111111"
RIGHT_UID = "22222222-2222-4222-8222-222222222222"


def _setup() -> MeldTuiSetup:
    return MeldTuiSetup(
        names=("meld/a", "meld/b", "meld/empty"),
        left_name="meld/a",
        right_name="meld/b",
        eligible_target_names=frozenset({"meld/empty"}),
        current_context="meld/a",
    )


def _load(role_uid: str, context_name: str):
    uid = LEFT_UID if role_uid == "A" else RIGHT_UID
    return (
        EndpointSetupMemory(
            context_name,
            uid,
            f"{role_uid} exact Memory in {context_name}.",
        ),
    )


def test_meld_setup_projects_mode_dependent_shared_roles() -> None:
    spec = meld_endpoint_setup_spec(_setup())

    assert spec.active_role_uids("SYMMETRIC") == ("A", "B", "C")
    assert spec.active_role_uids("DIRECTIONAL") == ("A", "B")
    assert spec.role_label("SYMMETRIC", "C").startswith("C · RESULT")
    assert spec.role_allows_memory_focus("SYMMETRIC", "A") is False
    assert spec.role_allows_memory_focus("DIRECTIONAL", "A") is True
    assert spec.roles[2].allow_new is True
    assert spec.roles[2].prefer_new is True


def test_meld_setup_returns_an_existing_symmetric_result() -> None:
    with create_pipe_input() as pipe_input:
        # MODE -> A/range -> B/range -> C; choose existing C, cross NEW, run.
        pipe_input.send_text("\t" * 5 + "\r\t\t\r")
        selected = choose_meld_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == MeldEndpointSelection(
        "symmetric",
        "meld/a",
        "meld/b",
        target_name="meld/empty",
    )


def test_meld_setup_confirms_a_new_symmetric_result() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t" * 6 + "meld/new-result\r\r")
        selected = choose_meld_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == MeldEndpointSelection(
        "symmetric",
        "meld/a",
        "meld/b",
        target_name="meld/new-result",
        create_target=True,
    )


def test_directional_meld_omits_c_and_can_focus_one_incoming_memory() -> None:
    with create_pipe_input() as pipe_input:
        # Switch mode, select A's Memory, then cross B to the action.
        pipe_input.send_text("\x1b[C\t\t\t\x1b[B\r" + "\t" * 4 + "\r")
        selected = choose_meld_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == MeldEndpointSelection(
        "directional",
        "meld/a",
        "meld/b",
        left_memory_uid=LEFT_UID,
    )


def test_meld_command_uses_the_new_setup_composition() -> None:
    assert meld_command.choose_meld_setup is meld_setup_command.choose_meld_setup


def test_meld_command_setup_preserves_existing_empty_target(isolated_store) -> None:
    store = MemoryStore()
    left = ops.init("meld/a")
    ops.add(left, "Left peer Memory.")
    right = ops.init("meld/b")
    ops.add(right, "Right peer Memory.")
    empty = ops.init("meld/empty")
    for context in (left, right, empty):
        store.create_context(context)
    store.set_current(left.name)

    frozen = meld_setup_command.build_meld_tui_setup(store)
    assert frozen.names == (left.name, right.name, empty.name)
    assert frozen.eligible_target_names == frozenset({empty.name})

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t" * 5 + "\r\t\t\r")
        receipt = meld_setup_command.choose_meld_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == meld_setup_command.MeldSetupReceipt(
        "symmetric",
        left.name,
        right.name,
        target_name=empty.name,
    )
