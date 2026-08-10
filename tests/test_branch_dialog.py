"""Interactive Branch setup contracts."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.branch_dialog import (
    BranchCreationReceipt,
    choose_branch_creation,
)


def test_branch_setup_uses_common_from_and_new_to_frames() -> None:
    with create_pipe_input() as pipe_input:
        # FROM starts focused. Tab enters the TO tree; a second Tab reaches
        # APPLY while the preconfirmed new-name row remains the staged choice.
        pipe_input.send_text("\t\t\r")
        result = choose_branch_creation(
            ("alpha", "empty"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("alpha", "alpha/branch")


def test_branch_setup_reparents_an_untouched_exact_name() -> None:
    with create_pipe_input() as pipe_input:
        # Tab enters TO's parent tree. Choosing beta rewrites only the still
        # untouched alpha/ prefix, then Tab reaches Apply.
        pipe_input.send_text("\t\x1b[B\r\t\r")
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("alpha", "beta/branch")


def test_branch_setup_new_name_uses_operation_validator() -> None:
    validated: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\r")
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=validated.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("alpha", "alpha/branch")
    assert validated == ["alpha/branch"]


def test_branch_setup_cancel_returns_no_receipt() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is None


def test_branch_setup_rejects_an_existing_exact_name() -> None:
    with create_pipe_input() as pipe_input:
        # Open the exact-name field, enter an existing catalog name, Tab to
        # Apply, and cancel after Apply rejects that currently visible value.
        pipe_input.send_text("\t\x1b[B\x1b[B\x15beta\t\rq")
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is None


def test_branch_setup_applies_the_visible_edited_path_without_hidden_confirmation() -> None:
    with create_pipe_input() as pipe_input:
        # The parent-locator variant treats the exact field as authoritative:
        # Tab may leave it without restoring the earlier preconfirmed value.
        pipe_input.send_text("\t\x1b[B\x1b[B\x15aaa/bbb\t\r")
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("alpha", "aaa/bbb")


def test_branch_setup_refreshes_untouched_name_from_selected_source() -> None:
    with create_pipe_input() as pipe_input:
        # Choose beta in FROM, then traverse TO to APPLY without editing its
        # preconfirmed new-name suggestion.
        pipe_input.send_text("\x1b[B\r\t\t\r")
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("beta", "beta/branch")


def test_branch_setup_preserves_name_after_first_direct_edit() -> None:
    with create_pipe_input() as pipe_input:
        down = "\x1b[B"
        shift_tab = "\x1b[Z"
        # Enter TO's exact-name row, replace and confirm the whole path, return
        # to its parent tree, choose beta, then Apply. Parent browsing must not
        # replace a person-edited exact draft.
        pipe_input.send_text(
            "\t" + down * 2 + "\x15custom/aaa/bbb\r" + shift_tab
            + "\r\t\r"
        )
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("alpha", "custom/aaa/bbb")


def test_branch_setup_stops_source_inheritance_after_direct_edit() -> None:
    with create_pipe_input() as pipe_input:
        down = "\x1b[B"
        shift_tab = "\x1b[Z"
        # Edit and confirm B, return through its parent tree to A, then choose
        # beta. Source changes, but the shared draft no longer inherits it.
        pipe_input.send_text(
            "\t" + down * 2 + "\x15custom/path\r"
            + shift_tab * 2 + down + "\r\t\t\r"
        )
        result = choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=lambda name: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == BranchCreationReceipt("beta", "custom/path")
