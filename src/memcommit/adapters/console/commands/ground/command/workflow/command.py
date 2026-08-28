"""Route one parsed ``mem ground`` request to its owning workflow."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from memcommit.adapters.console.commands.ground.session_picker import (
    list_ground_session_catalog,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.ground.dialogue import (
    GroundDialogueError,
)
from memcommit.application.operations.ground.model import (
    GroundError,
    validate_ground_contract_name,
)
from memcommit.application.operations.ground.workspace_draft import (
    GroundWorkspaceDraftError,
)
from memcommit.application.operations.ground.workspace_draft_store import (
    GroundWorkspaceDraftStore,
)
from memcommit.application.operations.ground.workspace_history import (
    GroundWorkspaceHistoryError,
)
from memcommit.application.operations.ground.workspace_model import (
    GroundWorkspaceError,
)
from memcommit.application.operations.ground.workspace_runtime import (
    ground_workspace_exists,
)
from memcommit.persistence.store import MemoryStore, validate_context_name

from . import create as create_workflow
from . import edit as edit_workflow
from . import inspect as inspect_workflow
from . import open as open_workflow
from .session import command as session_command


@dataclass(frozen=True)
class GroundCommandRequest:
    """Validated CLI-shaped input passed into Ground workflow routing."""

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
    scope: list[str] | None = None
    description: str | None = None
    raw_context: str | None = None
    derived_context: str | None = None
    publication_target: str | None = None
    placement_target: list[str] | None = None
    blocked_target: list[str] | None = None
    focus_target: str | None = None
    select: int | None = None
    propose_source: str | None = None
    propose_example: str | None = None
    example_rule: list[str] | None = None
    example_source: str | None = None
    example_target: list[str] | None = None
    example_input: str | None = None
    example_expected: str | None = None
    propose_rule: str | None = None
    propose_rule_target: list[str] | None = None
    fit_rule: str | None = None
    propose_target: list[str] | None = None
    expected: str | None = None
    rationale: str | None = None
    case_role: str | None = None
    disposition: str | None = None
    set_example_use: str | None = None
    use: str | None = None
    rule_provenance: str | None = None
    decide: str | None = None
    action: str | None = None
    response: str | None = None
    revise_target: str | None = None
    revise_goal: str | None = None
    requirement_text: str | None = None
    minimum_cases: int | None = None
    blocked_reason: str | None = None
    change_reason: str | None = None
    upgrade_propositions: bool = False
    snapshot: bool = False
    replace_ground: bool = False
    if_ground_version: str | None = None
    if_context_version: list[str] | None = None
    resume_draft: str | None = None


def run_ground_command(command_request: GroundCommandRequest) -> None:
    """Execute one parsed Ground command without owning Typer metadata."""
    ground_name = command_request.ground_name
    request = command_request.request
    sessions = command_request.sessions
    goal = command_request.goal
    set_goal = command_request.set_goal
    add_rule = command_request.add_rule
    add_example = command_request.add_example
    add_relation = command_request.add_relation
    undo_local = command_request.undo_local
    if_ground_revision = command_request.if_ground_revision
    scope = command_request.scope
    focus_target = command_request.focus_target
    select = command_request.select
    snapshot = command_request.snapshot
    replace_ground = command_request.replace_ground
    if_ground_version = command_request.if_ground_version
    if_context_version = command_request.if_context_version
    resume_draft = command_request.resume_draft

    physical_edit_requested = (
        any(
            value is not None
            for value in (set_goal, add_rule, add_example, add_relation)
        )
        or undo_local
    )
    session_actions = session_command.SessionActionSelection.from_request(
        command_request
    )
    action_count = session_actions.count

    seed_conflict_requested = (
        any(
            value is not None
            for value in (
                goal,
                scope,
                focus_target,
                select,
            )
        )
        or action_count > 0
        or physical_edit_requested
        or snapshot
        or replace_ground
        or if_ground_version is not None
        or bool(if_context_version)
        or if_ground_revision is not None
    )
    initial_request: str | None = request
    if resume_draft is not None:
        if (
            sessions
            or ground_name is not None
            or request is not None
            or seed_conflict_requested
        ):
            typer.secho(
                "Ground error: --resume-draft cannot be combined with "
                "another Ground target, request, or action.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not open_workflow._interactive_terminal():
            typer.secho(
                "Ground error: --resume-draft requires an interactive terminal.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            draft_store = GroundWorkspaceDraftStore(MemoryStore(create=False))
            draft = draft_store.load(resume_draft)
            if ground_workspace_exists(draft_store.store, draft.workspace_name):
                raise GroundWorkspaceDraftError(
                    f"Ground workspace '{draft.workspace_name}' already "
                    "exists; open the physical workspace instead."
                )
            outcome = create_workflow._run_new_ground_shell(draft=draft)
            if outcome == "BACK_TO_PICKER":
                open_workflow._run_ground_session_picker(draft_store.store)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            typer.secho(
                f"Ground error: {safe_terminal_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        return
    if sessions and (ground_name is not None or request is not None):
        typer.secho(
            "Ground error: --sessions cannot be combined with a Ground "
            "name or starting request.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if sessions and seed_conflict_requested:
        typer.secho(
            "Ground error: --sessions cannot be combined with Ground "
            "creation, view, or mutation options.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if request is not None and ground_name is not None:
        typer.secho(
            "Ground error: choose either GROUND_NAME_OR_REQUEST or "
            "--request, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if request is not None and seed_conflict_requested:
        typer.secho(
            "Ground error: --request starts an unsaved chat and cannot "
            "be combined with Ground options.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if ground_name is not None:
        try:
            validate_ground_contract_name(ground_name)
        except GroundError:
            try:
                # Physical workspaces use the ordinary Context namespace. A
                # slash disambiguates that exact name from the established
                # natural-language positional shorthand. Flat workspace names
                # continue to use the portable Ground-name grammar.
                if "/" not in ground_name:
                    raise ValueError("not an explicit Context-rooted name")
                validate_context_name(ground_name)
            except ValueError:
                if seed_conflict_requested:
                    typer.secho(
                        "Ground error: a natural-language starting request "
                        "cannot be combined with Ground options. Use a valid "
                        "Context-rooted GROUND_NAME for named actions.",
                        fg=typer.colors.RED,
                        err=True,
                    )
                    raise typer.Exit(1)
                # A value that cannot identify an explicit workspace remains
                # the person's first unsaved turn.
                initial_request = ground_name
                ground_name = None
        if ground_name is not None:
            try:
                validate_context_name(ground_name)
            except ValueError as error:
                typer.secho(
                    f"Ground error: {safe_terminal_text(str(error))}",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
    if initial_request is not None:
        try:
            initial_request = create_workflow._validated_start_request(initial_request)
        except GroundDialogueError as error:
            typer.secho(
                f"Ground error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if open_workflow._interactive_terminal():
            store = MemoryStore(create=False)
            outcome = create_workflow._run_new_ground_shell(initial_request)
            if outcome == "BACK_TO_PICKER":
                open_workflow._run_ground_session_picker(store)
        else:
            typer.echo(inspect_workflow.render_ground_start(initial_request))
        return

    legacy_named_exists = False
    if ground_name is not None and not physical_edit_requested:
        try:
            legacy_named_exists = (
                MemoryStore(create=False).load_ground_session(ground_name) is not None
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            legacy_named_exists = False

    physical_workspace_route = (
        ground_name is not None
        and not legacy_named_exists
        and scope is None
        and action_count == 0
        and focus_target is None
        and not replace_ground
        and if_ground_version is None
        and not if_context_version
    )
    if physical_workspace_route:
        try:
            edit_workflow._run_named_ground_workspace(
                ground_name,
                goal=goal,
                snapshot=snapshot,
                set_goal=set_goal,
                add_rule=add_rule,
                add_example=add_example,
                add_relation=add_relation,
                undo_local=undo_local,
                expected_revision=if_ground_revision,
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
            typer.secho(
                f"Ground error: {safe_terminal_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        return

    if ground_name is not None:
        try:
            is_physical_workspace = ground_workspace_exists(
                MemoryStore(create=False),
                ground_name,
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            is_physical_workspace = False
        if is_physical_workspace:
            typer.secho(
                "Ground error: this is a physical Ground workspace; the "
                "requested legacy session option cannot write a parallel "
                "Ground JSON record.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    plain_named_tui_requested = (
        ground_name is not None
        and open_workflow._interactive_terminal()
        and action_count == 0
        and goal is None
        and scope is None
        and focus_target is None
        and not snapshot
        and not replace_ground
        and if_ground_version is None
        and not if_context_version
    )
    if ground_name is None:
        option_requested = (
            any(
                value is not None
                for value in (
                    goal,
                    scope,
                    focus_target,
                    select,
                )
            )
            or action_count > 0
            or physical_edit_requested
            or snapshot
            or replace_ground
            or if_ground_version is not None
            or bool(if_context_version)
            or if_ground_revision is not None
        )
        if option_requested:
            typer.secho(
                "Ground error: GROUND_NAME is required when using options. "
                "Run 'mem ground' without options to start from a blank "
                "Ground.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if sessions and not open_workflow._interactive_terminal():
            typer.secho(
                "Ground error: --sessions requires an interactive terminal.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if open_workflow._interactive_terminal():
            try:
                store = MemoryStore(create=False)
                catalog = list_ground_session_catalog(store)
                # The launcher is the stable first screen even for an empty
                # Store. New Ground is a pinned creation action, not an
                # implicit provider-named session.
                open_workflow._run_ground_session_picker(store, catalog=catalog)
            except (GroundError, OSError, TypeError, ValueError) as error:
                typer.secho(
                    f"Ground error: {error}",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
        else:
            typer.echo(inspect_workflow.render_ground_start())
        return

    session_command.run_ground_session_command(
        command_request,
        ground_name=ground_name,
        selection=session_actions,
        plain_named_tui_requested=plain_named_tui_requested,
    )
