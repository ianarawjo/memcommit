"""Interactive import setup and frozen-approval boundaries."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.terminal.components.context_reach_dialog import choose_context_reach
from memcommit.adapters.console.terminal.components.command_editor.model import CommandReview
from memcommit.adapters.console.terminal.components.command_editor.approval import approve_exact_command
from memcommit.adapters.console.terminal.components.exact_name_dialog import choose_exact_name
from memcommit.adapters.console.terminal.components.flat_selection_dialog import choose_flat_option
from memcommit.adapters.console.commands.resource_import.workbench import freeze_import_source_catalog
from memcommit.adapters.console.terminal.components.primitives import ExactNameFieldView
from memcommit.application.operations.profile.config import ProfileEntry, ProfileRegistry
from memcommit.adapters.console.terminal.components.selection import SelectionOption


runner = CliRunner(mix_stderr=False)


def test_import_source_catalog_hides_active_and_removed_profiles():
    active = ProfileEntry("active-uid", "active", "MANAGED")
    source = ProfileEntry("source-uid", "source", "MANAGED")
    removed = ProfileEntry("removed-uid", "removed", "MANAGED")
    registry = ProfileRegistry(
        generation=3,
        active_uid=active.uid,
        profiles=(active, source, removed),
        removed_profile_uids=(removed.uid,),
    )

    catalog = freeze_import_source_catalog(registry)

    assert catalog.active_profile_uid == active.uid
    assert tuple(entry.name for entry in catalog.sources) == ("source",)
    assert all(entry.uid != active.uid for entry in catalog.sources)


def test_flat_selection_dialog_uses_shared_checked_state():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        selected = choose_flat_option(
            (
                SelectionOption("ONE", "ONE"),
                SelectionOption("TWO", "TWO"),
            ),
            title="TEST SELECTION",
            detail="Choose one value.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is not None
    assert selected.uid == "TWO"


def test_exact_name_dialog_validates_edited_value():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x15new-name\r")
        selected = choose_exact_name(
            ExactNameFieldView(
                value="old-name",
                label="NEW NAME",
                validate=lambda value: value == "new-name"
                or (_ for _ in ()).throw(ValueError("wrong name")),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "new-name"


def test_context_reach_dialog_uses_shared_exact_subtree_control():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[C\r")
        selected = choose_context_reach(
            title="TEST RANGE",
            detail="Choose a range.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is True


def test_exact_command_review_uses_enter_and_retains_a_alias():
    review = CommandReview(
        argv=("mem", "import", "context", "source"),
        effects=("Create one Context.",),
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        approved = approve_exact_command(
            review,
            title="TEST REVIEW",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("A")
        legacy_approved = approve_exact_command(
            review,
            title="TEST REVIEW",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        cancelled = approve_exact_command(
            review,
            title="TEST REVIEW",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert approved is True
    assert legacy_approved is True
    assert cancelled is False


def test_flagless_import_requires_tty_outside_interactive_setup(isolated_store):
    result = runner.invoke(app, ["import"])

    assert result.exit_code == 1
    assert "Interactive import setup requires a terminal" in result.stderr
