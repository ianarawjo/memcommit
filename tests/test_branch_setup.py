"""Interactive Branch setup and console ownership contracts."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.commands.branch.receipt import (
    BranchCreationReceipt,
)
from memcommit.adapters.console.commands.branch.endpoint_setup import (
    branch_endpoint_setup_spec,
    branch_exact_command_review,
    choose_branch_creation,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointSetupDraft,
    EndpointSetupValue,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _choose(keys: str, *, validated: list[str] | None = None):
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keys)
        return choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: f"{source}/branch",
            validate_name=(
                validated.append if validated is not None else lambda _name: None
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )


def test_branch_setup_uses_form_shared_from_and_new_to_rows() -> None:
    spec = branch_endpoint_setup_spec(
        ("alpha", "beta"),
        current="alpha",
        suggest_name=lambda source: f"{source}/branch",
        validate_name=lambda _name: None,
    )

    assert spec.screen_layout == "FORM"
    assert len(spec.modes) == 1
    assert spec.active_role_uids("BRANCH") == ("A", "B")
    assert spec.role_label("BRANCH", "A") == "FROM"
    assert spec.role_label("BRANCH", "B") == "TO"
    assert spec.roles[1].new_parent_locator is True
    assert spec.roles[1].selectable_names == frozenset()
    assert spec.action_label == "CREATE BRANCH AND SWITCH"
    assert spec.command_verb == "APPLY"


def test_branch_setup_returns_the_initial_form_plan() -> None:
    # Tab traverses A Browse/range, B input/parent Browse, then exact Apply.
    result = _choose("\t" * 5 + "\r")

    assert result == BranchCreationReceipt("alpha", "alpha/branch")


def test_branch_setup_runs_the_visible_edited_command() -> None:
    # A Browse/range, B input/parent Browse, then the editable command.
    result = _choose(
        "\t" * 5
        + "\x15beta/new-branch --from beta --source-descendants\r"
    )

    assert result == BranchCreationReceipt("beta", "beta/new-branch", True)


def test_branch_setup_reparents_an_untouched_exact_name() -> None:
    # Down enters TO; Right crosses its field edge into Browse Parent.
    result = _choose("\x1b[B\x1b[C\r\x1b[B\r\t\r")

    assert result == BranchCreationReceipt("alpha", "beta/branch")


def test_branch_setup_new_name_uses_operation_validator() -> None:
    validated: list[str] = []

    result = _choose("\t" * 5 + "\r", validated=validated)

    assert result == BranchCreationReceipt("alpha", "alpha/branch")
    assert validated
    assert set(validated) == {"alpha/branch"}


def test_branch_setup_cancel_returns_no_receipt() -> None:
    assert _choose("\x1b") is None


def test_branch_setup_rejects_an_existing_exact_name() -> None:
    # The parent-locator role is always require-new, so even a catalog spelling
    # remains a new-name validation failure instead of selecting that Context.
    # The command row is writable, so Escape—not a printable q—cancels after
    # the existing target is rejected without moving the upper fields.
    result = _choose("\x1b[B\x15beta\x1b[B\r\x1b")

    assert result is None


def test_branch_setup_applies_the_visible_edited_path_without_hidden_confirmation() -> (
    None
):
    result = _choose("\x1b[B\x15aaa/bbb\x1b[B\r")

    assert result == BranchCreationReceipt("alpha", "aaa/bbb")


def test_branch_setup_refreshes_untouched_name_from_selected_source() -> None:
    # Browse A, choose beta, then traverse range, B, parent Browse, and Apply.
    result = _choose("\t\r\x1b[B\r" + "\t" * 4 + "\r")

    assert result == BranchCreationReceipt("beta", "beta/branch")


def test_branch_setup_preserves_name_after_first_direct_edit() -> None:
    # Directly edit TO, then browse a different parent. Parent choice remains
    # visible but cannot rewrite the person-owned exact path.
    result = _choose("\x1b[B\x15custom/aaa/bbb\x1b[C\r\x1b[B\r\t\r")

    assert result == BranchCreationReceipt("alpha", "custom/aaa/bbb")


def test_branch_setup_stops_source_inheritance_after_direct_edit() -> None:
    shift_tab = "\x1b[Z"
    # Edit TO, return to A's Browse, select beta, then complete the form.
    result = _choose(
        "\x1b[B\x15custom/path" + shift_tab * 2 + "\r\x1b[B\r" + "\t" * 4 + "\r"
    )

    assert result == BranchCreationReceipt("beta", "custom/path")


def test_branch_setup_returns_the_visible_subtree_scope() -> None:
    # Right at A's input edge enters Browse, then range; Space toggles subtree.
    result = _choose("\x1b[C\x1b[C \x1b[B\x1b[B\r")

    assert result == BranchCreationReceipt(
        "alpha",
        "alpha/branch",
        include_descendants=True,
    )


def test_branch_exact_review_includes_source_and_scope() -> None:
    review = branch_exact_command_review(
        EndpointSetupDraft(
            "BRANCH",
            (
                EndpointSetupValue("A", "alpha", include_descendants=True),
                EndpointSetupValue("B", "draft", create=True),
            ),
        )
    )

    assert review.argv == (
        "mem",
        "branch",
        "draft",
        "--from",
        "alpha",
        "--source-descendants",
    )


def test_branch_console_package_owns_setup_and_receipt_without_facades() -> None:
    command_root = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/branch"
    retired_root = (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/tui/operations/branch"
    )

    assert (command_root / "endpoint_setup.py").is_file()
    assert (command_root / "receipt.py").is_file()
    assert not (command_root / "dialog.py").exists()
    assert not tuple(retired_root.glob("*.py"))
