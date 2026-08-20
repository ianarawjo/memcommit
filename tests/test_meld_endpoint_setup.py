"""Contracts for Meld's shared Endpoint Setup adapter."""

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

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

    assert spec.screen_layout == "COMPACT_FORM"
    assert tuple(mode.label for mode in spec.modes) == (
        "SYMMETRIC · CREATE SEPARATE RESULT",
        "DIRECTIONAL · UPDATE EXISTING",
    )
    assert spec.active_role_uids("SYMMETRIC") == ("A", "B", "C")
    assert spec.active_role_uids("DIRECTIONAL") == ("A", "B")
    assert spec.role_label("SYMMETRIC", "A") == "FROM"
    assert spec.role_label("SYMMETRIC", "B") == "WITH"
    assert spec.role_label("SYMMETRIC", "C") == "TO"
    assert spec.role_label("DIRECTIONAL", "A") == "FROM"
    assert spec.role_label("DIRECTIONAL", "B") == "TO"
    assert spec.role_allows_memory_focus("SYMMETRIC", "A") is False
    assert spec.role_allows_memory_focus("DIRECTIONAL", "A") is True
    assert spec.roles[2].allow_new is True
    assert spec.roles[2].prefer_new is True
    assert spec.action_label == "START MELD"


def test_meld_setup_returns_an_existing_symmetric_result() -> None:
    with create_pipe_input() as pipe_input:
        # MODE -> A/B Browse and range controls -> C exact input.
        pipe_input.send_text("\t" * 7 + "meld/empty\r\r")
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
        pipe_input.send_text("\t" * 7 + "meld/new-result\r\r")
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


def test_compact_setup_keeps_each_operand_directly_editable() -> None:
    with create_pipe_input() as pipe_input:
        # Replace A, B, and C independently through their exact-name fields.
        pipe_input.send_text(
            "\t\x15meld/b\t\t\t\x15meld/a\t\t\tmeld/manually-positioned-result\r\r"
        )
        selected = choose_meld_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == MeldEndpointSelection(
        "symmetric",
        "meld/b",
        "meld/a",
        target_name="meld/manually-positioned-result",
        create_target=True,
    )


def test_compact_result_catalog_shows_only_eligible_existing_targets() -> None:
    with create_pipe_input() as pipe_input:
        # C's explicit Browse opens only eligible empty targets, not A/B sources.
        pipe_input.send_text("\t" * 8 + "\r\r\t\r")
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


def test_compact_mode_down_enters_endpoint_without_changing_mode() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B" + "\t" * 6 + "meld/down-result\r\r")
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
        target_name="meld/down-result",
        create_target=True,
    )


def test_compact_symmetric_mode_keeps_both_independent_descendant_flags() -> None:
    with create_pipe_input() as pipe_input:
        # MODE -> A/range, broaden A -> B/range, broaden B -> C/new -> Continue.
        pipe_input.send_text("\t\t\t\x1b[C\t\t\t\x1b[C\tmeld/recursive-result\r\r")
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
        target_name="meld/recursive-result",
        create_target=True,
        left_descendants=True,
        right_descendants=True,
    )


@pytest.mark.parametrize(
    ("left_key", "right_key", "left_descendants", "right_descendants"),
    (
        ("", "", False, False),
        ("\x1b[C", "", True, False),
        ("", "\x1b[C", False, True),
        ("\x1b[C", "\x1b[C", True, True),
    ),
)
def test_compact_directional_mode_keeps_each_cli_descendant_combination(
    left_key: str,
    right_key: str,
    left_descendants: bool,
    right_descendants: bool,
) -> None:
    with create_pipe_input() as pipe_input:
        # Select Directional, visit each independent range, then Continue.
        pipe_input.send_text(
            "\x1b[C" + "\t" * 3 + left_key + "\t" * 4 + right_key + "\t\t\r"
        )
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
        left_descendants=left_descendants,
        right_descendants=right_descendants,
    )


def test_compact_descendant_arrows_set_values_instead_of_toggling() -> None:
    with create_pipe_input() as pipe_input:
        # Select Directional, reach A's checkbox, repeat Right, then Continue.
        pipe_input.send_text("\x1b[C" + "\t" * 3 + "\x1b[C\x1b[C" + "\t" * 6 + "\r")
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
        left_descendants=True,
    )


def test_directional_meld_omits_c_and_can_focus_one_incoming_memory() -> None:
    with create_pipe_input() as pipe_input:
        # Switch mode, select A's Memory, then cross B to the action.
        pipe_input.send_text("\x1b[C" + "\t" * 4 + "\x1b[B\r" + "\t" * 5 + "\r")
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
        pipe_input.send_text("\t" * 7 + empty.name + "\r\r")
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
