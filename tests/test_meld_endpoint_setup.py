"""Contracts for Meld's shared Endpoint Setup adapter."""

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

from memcommit.adapters.console.commands.meld import command as meld_command
import memcommit.adapters.console.commands.meld.endpoint_setup as meld_setup_command
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointSetupMemory,
)
from memcommit.adapters.console.commands.meld.endpoint_setup import (
    MeldEndpointSelection,
    MeldTuiSetup,
    build_meld_tui_setup,
    choose_meld_endpoint_setup,
    meld_endpoint_setup_spec,
)
from memcommit.persistence.store import MemoryStore


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
    assert spec.roles[2].existing_label == "EMPTY · EXISTING"
    assert spec.action_label == "START MELD"


def test_meld_setup_offers_only_empty_session_free_local_results(
    isolated_store,
) -> None:
    store = MemoryStore()
    left = ops.init("meld/catalog/a")
    ops.add(left, "Source A.")
    right = ops.init("meld/catalog/b")
    ops.add(right, "Source B.")
    empty = ops.init("meld/catalog/empty")
    occupied = ops.init("meld/catalog/occupied")
    ops.add(occupied, "Existing result content.")
    for context in (left, right, empty, occupied):
        store.save(context)

    setup = build_meld_tui_setup(store)

    assert setup.eligible_target_names == frozenset({empty.name})


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


def test_compact_directional_from_and_to_support_in_place_caret_edits() -> None:
    with create_pipe_input() as pipe_input:
        # Switch to Directional and edit the final segment of each prefilled
        # endpoint in place. Left belongs to the writable field's caret, not
        # row navigation; Delete and insertion must change the exact operands.
        pipe_input.send_text(
            "\x1b[C\x1b[B"
            "\x1b[D\x1b[D\x1b[C\x1b[3~b\r\x1b[B"
            "\x1b[D\x1b[D\x1b[C\x1b[3~a\r\x1b[B\r"
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
        "meld/b",
        "meld/a",
    )


def test_compact_directional_browse_replaces_both_exact_endpoint_fields() -> None:
    with create_pipe_input() as pipe_input:
        # Browse A from meld/a to meld/b, then move vertically from A's Browse
        # control and Browse B from meld/b to meld/a. Each catalog choice must
        # replace the writable field that builds the final command operands.
        pipe_input.send_text("\x1b[C\x1b[B\t\r\x1b[B\r\x1b[B\t\r\x1b[A\r\x1b[B\r")
        selected = choose_meld_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == MeldEndpointSelection(
        "directional",
        "meld/b",
        "meld/a",
    )


def test_compact_input_right_edge_enters_browse_then_left_returns_to_edit() -> None:
    with create_pipe_input() as pipe_input:
        # Right inside a field remains caret motion. At the final character it
        # crosses into Browse; choosing there writes the same field, and Left
        # returns to that exact input so the catalog value can be edited again.
        pipe_input.send_text(
            "\x1b[C\x1b[B\x1b[C\r\x1b[B\r\x1b[D\x1b[D\x1b[3~a\r\x1b[B\x1b[B\r"
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


def test_compact_arrows_follow_visible_endpoint_rows() -> None:
    with create_pipe_input() as pipe_input:
        # MODE ↓ A ↓ B ↓ C. Horizontal Browse/range controls remain in the
        # Tab order instead of intercepting vertical row navigation.
        pipe_input.send_text("\x1b[B" * 3 + "meld/arrow-result\r\r\x03")
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
        target_name="meld/arrow-result",
        create_target=True,
    )


@pytest.mark.parametrize("horizontal_tabs", (2, 3))
def test_compact_arrows_leave_browse_and_reach_by_endpoint_row(
    horizontal_tabs: int,
) -> None:
    with create_pipe_input() as pipe_input:
        # Focus A's Browse or descendant control with Tab. Down still lands
        # on B's primary field, then C, matching their vertical placement.
        pipe_input.send_text(
            "\t" * horizontal_tabs + "\x1b[B" * 2 + "meld/row-result\r\r\x03"
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
        "meld/a",
        "meld/b",
        target_name="meld/row-result",
        create_target=True,
    )


def test_compact_action_up_returns_to_the_last_endpoint_row() -> None:
    with create_pipe_input() as pipe_input:
        # MODE ↓ A ↓ B ↓ C ↓ START, then Up reverses to C's primary field.
        pipe_input.send_text("\x1b[B" * 4 + "\x1b[A" + "meld/revisited-result\r\r\x03")
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
        target_name="meld/revisited-result",
        create_target=True,
    )


def test_compact_exact_input_keeps_left_arrow_for_caret_editing() -> None:
    with create_pipe_input() as pipe_input:
        # Reach the writable C field, type one missing character, move the
        # caret Left inside that exact name, and repair it in place.
        pipe_input.send_text("\x1b[B" * 3 + "meld/reslt\x1b[D\x1b[Du\r\r\x03")
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
        target_name="meld/result",
        create_target=True,
    )


def test_compact_symmetric_mode_keeps_both_independent_descendant_flags() -> None:
    with create_pipe_input() as pipe_input:
        # MODE -> A/range, broaden A -> B/range, broaden B -> C/new -> Continue.
        pipe_input.send_text("\t\t\t \t\t\t \tmeld/recursive-result\r\r")
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
    ("left_toggle", "right_toggle", "left_descendants", "right_descendants"),
    (
        ("", "", False, False),
        (" ", "", True, False),
        ("", " ", False, True),
        (" ", " ", True, True),
    ),
)
def test_compact_directional_mode_keeps_each_cli_descendant_combination(
    left_toggle: str,
    right_toggle: str,
    left_descendants: bool,
    right_descendants: bool,
) -> None:
    with create_pipe_input() as pipe_input:
        # Select Directional, visit each independent range, then Continue.
        pipe_input.send_text(
            "\x1b[C" + "\t" * 3 + left_toggle + "\t" * 4 + right_toggle + "\t\t\r"
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


def test_compact_descendant_space_toggles_the_checked_value() -> None:
    with create_pipe_input() as pipe_input:
        # Left/Right now own row navigation; Space owns the checkbox value.
        pipe_input.send_text("\x1b[C" + "\t" * 3 + " " + "\t" * 6 + "\r")
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


def test_compact_left_right_traverse_browse_reach_and_memory() -> None:
    with create_pipe_input() as pipe_input:
        # Enter A's row, Tab once out of the caret-owning input, then use
        # Right to cross Browse -> reach -> Memory before opening its list.
        pipe_input.send_text("\x1b[C\x1b[B\t\x1b[C\x1b[C\r\x1b[B\r\x1b[B\x1b[B\r\x03")
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


def test_compact_left_from_memory_returns_to_reach_without_changing_it() -> None:
    with create_pipe_input() as pipe_input:
        # Reach Memory by row arrows, return Left to the reach checkbox, then
        # toggle it explicitly with Space before moving vertically to START.
        pipe_input.send_text("\x1b[C\x1b[B\t\x1b[C\x1b[C\x1b[D \x1b[B\x1b[B\r\x03")
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
        # Switch mode, open A's Memory list explicitly, select its first
        # Memory, then cross B to the action.
        pipe_input.send_text("\x1b[C" + "\t" * 4 + "\r\x1b[B\r" + "\t" * 5 + "\r")
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


def test_compact_directional_memory_button_does_not_trap_row_arrows() -> None:
    with create_pipe_input() as pipe_input:
        # Directional MODE, then Tab to A Memory. Down moves to B's primary
        # field and a second Down reaches START without opening the list.
        pipe_input.send_text("\x1b[C" + "\t" * 4 + "\x1b[B\x1b[B\r\x03")
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
    )


def test_compact_directional_memory_list_continues_at_its_edge() -> None:
    with create_pipe_input() as pipe_input:
        # Enter opens A's two-row Whole Context/Memory list. Down reaches the
        # Memory, another Down leaves the list for B, and Down reaches START.
        pipe_input.send_text("\x1b[C" + "\t" * 4 + "\r\x1b[B\x1b[B\x1b[B\r\x03")
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
