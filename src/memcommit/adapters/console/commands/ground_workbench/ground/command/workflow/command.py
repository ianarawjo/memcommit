"""Route ``mem ground`` requests to physical workspace workflows."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.ground_workbench.ground.contracts import (
    GroundError,
    validate_ground_contract_name,
)
from memcommit.application.operations.ground_workbench.ground.dialogue import GroundDialogueError
from memcommit.application.operations.ground_workbench.ground.workspace_draft import (
    GroundWorkspaceDraftError,
)
from memcommit.application.operations.ground_workbench.ground.workspace_draft_store import (
    GroundWorkspaceDraftStore,
)
from memcommit.application.operations.ground_workbench.ground.workspace_history import (
    GroundWorkspaceHistoryError,
)
from memcommit.application.operations.ground_workbench.ground.workspace_model import GroundWorkspaceError
from memcommit.application.operations.ground_workbench.ground.workspace_runtime import (
    ground_workspace_exists,
)
from memcommit.persistence.store import MemoryStore, validate_context_name

from . import create as create_workflow
from . import edit as edit_workflow
from . import inspect as inspect_workflow
from . import open as open_workflow


@dataclass(frozen=True)
class GroundCommandRequest:
    """Physical Ground CLI input passed into workflow routing."""

    ground_name: str | None = None
    request: str | None = None
    sessions: bool = False
    goal: str | None = None
    set_goal: str | None = None
    add_rule: str | None = None
    add_example: str | None = None
    add_relation: str | None = None
    undo_local: bool = False
    if_ground_revision: int | None = None
    snapshot: bool = False
    resume_draft: str | None = None


def _fail(message: str) -> None:
    typer.secho(
        f"Ground error: {safe_terminal_text(message)}",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(1)


def run_ground_command(command_request: GroundCommandRequest) -> None:
    """Execute one physical Ground command without owning Typer metadata."""

    ground_name = command_request.ground_name
    request = command_request.request
    edit_requested = any(
        value is not None
        for value in (
            command_request.set_goal,
            command_request.add_rule,
            command_request.add_example,
            command_request.add_relation,
        )
    ) or command_request.undo_local
    named_option_requested = (
        command_request.goal is not None
        or edit_requested
        or command_request.snapshot
        or command_request.if_ground_revision is not None
    )

    if command_request.resume_draft is not None:
        if (
            command_request.sessions
            or ground_name is not None
            or request is not None
            or named_option_requested
        ):
            _fail(
                "--resume-draft cannot be combined with another Ground "
                "target, request, or action."
            )
        if not open_workflow._interactive_terminal():
            _fail("--resume-draft requires an interactive terminal.")
        try:
            draft_store = GroundWorkspaceDraftStore(MemoryStore(create=False))
            draft = draft_store.load(command_request.resume_draft)
            if ground_workspace_exists(draft_store.store, draft.workspace_name):
                raise GroundWorkspaceDraftError(
                    f"Ground workspace '{draft.workspace_name}' already "
                    "exists; open the physical workspace instead."
                )
            outcome = create_workflow._run_new_ground_shell(draft=draft)
            if outcome == "BACK_TO_PICKER":
                open_workflow._run_ground_session_picker(draft_store.store)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            _fail(str(error))
        return

    if command_request.sessions and (ground_name is not None or request is not None):
        _fail("--sessions cannot be combined with a Ground name or request.")
    if command_request.sessions and named_option_requested:
        _fail("--sessions cannot be combined with Ground workspace options.")
    if request is not None and ground_name is not None:
        _fail("Choose either GROUND_NAME_OR_REQUEST or --request, not both.")
    if request is not None and named_option_requested:
        _fail("--request cannot be combined with Ground workspace options.")

    initial_request = request
    if ground_name is not None:
        try:
            validate_ground_contract_name(ground_name)
        except GroundError:
            try:
                if "/" not in ground_name:
                    raise ValueError("not an explicit Context-rooted name")
                validate_context_name(ground_name)
            except ValueError:
                if named_option_requested:
                    _fail(
                        "A natural-language starting request cannot be combined "
                        "with Ground workspace options."
                    )
                initial_request = ground_name
                ground_name = None
        if ground_name is not None:
            try:
                validate_context_name(ground_name)
            except ValueError as error:
                _fail(str(error))

    if initial_request is not None:
        try:
            initial_request = create_workflow._validated_start_request(initial_request)
        except GroundDialogueError as error:
            _fail(str(error))
        if open_workflow._interactive_terminal():
            store = MemoryStore(create=False)
            outcome = create_workflow._run_new_ground_shell(initial_request)
            if outcome == "BACK_TO_PICKER":
                open_workflow._run_ground_session_picker(store)
        else:
            typer.echo(inspect_workflow.render_ground_start(initial_request))
        return

    if ground_name is not None:
        try:
            edit_workflow._run_named_ground_workspace(
                ground_name,
                goal=command_request.goal,
                snapshot=command_request.snapshot,
                set_goal=command_request.set_goal,
                add_rule=command_request.add_rule,
                add_example=command_request.add_example,
                add_relation=command_request.add_relation,
                undo_local=command_request.undo_local,
                expected_revision=command_request.if_ground_revision,
            )
        except (
            FileExistsError,
            FileNotFoundError,
            GroundWorkspaceError,
            GroundWorkspaceHistoryError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            _fail(str(error))
        return

    if named_option_requested:
        _fail(
            "GROUND_NAME is required when using options. Run 'mem ground' "
            "without options to start from a blank Ground."
        )
    if command_request.sessions and not open_workflow._interactive_terminal():
        _fail("--sessions requires an interactive terminal.")
    if open_workflow._interactive_terminal():
        try:
            open_workflow._run_ground_session_picker(MemoryStore(create=False))
        except (GroundError, OSError, TypeError, ValueError) as error:
            _fail(str(error))
    else:
        typer.echo(inspect_workflow.render_ground_start())
