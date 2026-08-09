"""Interactive Branch setup contracts."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.branch_dialog import (
    BranchCreationReceipt,
    choose_branch_creation,
)


def test_branch_dialog_prefills_from_current_and_can_choose_another_source() -> None:
    with create_pipe_input() as pipe_input:
        # The exact name starts focused. Tab wraps to Source, Down moves to
        # beta, Enter selects it and refreshes the untouched suggestion, then
        # Enter submits the resulting exact name.
        pipe_input.send_text("\t\x1b[B\r\r")
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}-branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("beta", "beta-branch")


def test_branch_dialog_does_not_overwrite_a_person_edited_name() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x15experiment\t\x1b[B\r\r")
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}-branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("beta", "experiment")


def test_branch_dialog_uses_one_vertical_source_to_new_name_flow() -> None:
    with create_pipe_input() as pipe_input:
        # The exact-name editor starts focused. Up enters the Source rows;
        # Down chooses another cursor, then Enter confirms that Source and
        # returns to the new-name row in the same compound frame.
        pipe_input.send_text("\x1b[A\x1b[B\r\r")
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}-branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("beta", "beta-branch")
