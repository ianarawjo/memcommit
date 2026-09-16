"""Create and directly edit a physical Context-rooted Ground."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.commands.ground.workspace.snapshot import (
    render_ground_workspace_snapshot,
)
from memcommit.adapters.console.commands.ground.workspace.viewer.screen import (
    run_ground_workspace_viewer,
)
from memcommit.application.operations.ground.workspace_application import (
    AddGroundWorkspaceMemoryRequest,
    CreateGroundWorkspaceRequest,
    ReplaceGroundWorkspaceMemoryRequest,
)
from memcommit.application.operations.ground.workspace_history import (
    undo_ground_workspace_command,
)
from memcommit.application.operations.ground.workspace_model import (
    GroundWorkspaceError,
)
from memcommit.application.operations.ground.workspace_runtime import (
    execute_ground_workspace_creation,
    execute_ground_workspace_memory_add,
    execute_ground_workspace_memory_replace,
    ground_workspace_exists,
    load_ground_workspace,
    load_ground_workspace_navigation_contexts,
)
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    freeze_goal_focus_operand,
    revalidate_goal_focus,
)
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore

from . import open as open_workflow


def _run_named_ground_workspace(
    name: str,
    *,
    goal: str | None,
    snapshot: bool,
    set_goal: str | None = None,
    add_rule: str | None = None,
    add_example: str | None = None,
    add_relation: str | None = None,
    undo_local: bool = False,
    expected_revision: int | None = None,
) -> None:
    """Create or open one Context-rooted workspace through the new boundary."""

    # Operand interpretation and durable-Goal validation are still read-only.
    # An invalid inline Goal must not create Store infrastructure merely so it
    # can be rejected by the 40-word Ground contract.
    inspection_store = MemoryStore(create=False)
    current_name = (
        inspection_store.current_context_name()
        if inspection_store.state_file.exists()
        else None
    )
    goal_focus = (
        freeze_goal_focus_operand(
            inspection_store,
            goal,
            current_name=current_name,
            require_single=True,
        )
        if goal is not None
        else None
    )
    set_goal_focus = (
        freeze_goal_focus_operand(
            inspection_store,
            set_goal,
            current_name=current_name,
            require_single=True,
        )
        if set_goal is not None
        else None
    )
    creation_request = CreateGroundWorkspaceRequest(
        name=name,
        goal_focus=goal_focus,
    )
    edit_values = (set_goal, add_rule, add_example, add_relation)
    edit_count = sum(value is not None for value in edit_values) + int(undo_local)
    if edit_count > 1:
        raise GroundWorkspaceError(
            "Set Goal, add Rule, add Example, add relation, and Undo are "
            "separate Ground actions."
        )
    # A valid named command now owns the creation effect and may establish
    # missing Store infrastructure before taking the multi-Context lock.
    store = MemoryStore()
    exists = ground_workspace_exists(store, name)
    if exists:
        if goal is not None:
            raise GroundWorkspaceError(
                "The Ground workspace already exists; edit its /goals "
                "Context through a separately reviewed Ground action."
            )
        created = False
    else:
        if edit_count:
            raise GroundWorkspaceError(
                "Create the Ground workspace before applying a local edit."
            )
        if goal_focus is not None:
            # Resolution is not authority to copy stale Goal content. Freeze
            # first for review/provenance, then revalidate immediately before
            # the multi-Context Ground creation command crosses its write
            # boundary.
            revalidate_goal_focus(store, goal_focus)
        execute_ground_workspace_creation(
            creation_request,
            store=store,
        )
        created = True
    workspace = load_ground_workspace(store, name)
    if (
        expected_revision is not None
        and workspace.manifest.revision != expected_revision
    ):
        raise GroundWorkspaceError(
            "The Ground workspace changed after this command was reviewed."
        )
    action_receipt = ""
    if undo_local:
        undone = undo_ground_workspace_command(store, name)
        action_receipt = (
            f"Undid Ground action '{undone.source_unit.action}' "
            f"[{undone.source_unit.uid[:8]}] · revision {undone.revision}."
        )
    elif set_goal is not None:
        assert set_goal_focus is not None
        revalidate_goal_focus(store, set_goal_focus)
        goal_content = set_goal_focus.text
        goals = tuple(
            item for item in workspace.goals.iter_items() if isinstance(item, Memory)
        )
        if len(goals) > 1:
            raise GroundWorkspaceError(
                "Set Goal requires zero or one directly owned Goal Memory."
            )
        if goals:
            edited = execute_ground_workspace_memory_replace(
                ReplaceGroundWorkspaceMemoryRequest(
                    workspace_name=name,
                    lane="goals",
                    memory_uid=goals[0].uid,
                    content=goal_content,
                    expected_revision=workspace.manifest.revision,
                    goal_focus=set_goal_focus,
                ),
                store=store,
            )
        else:
            edited = execute_ground_workspace_memory_add(
                AddGroundWorkspaceMemoryRequest(
                    workspace_name=name,
                    lane="goals",
                    content=goal_content,
                    expected_revision=workspace.manifest.revision,
                    goal_focus=set_goal_focus,
                ),
                store=store,
            )
        action_receipt = (
            f"Set Goal Memory [{edited.memory_uid[:8]}] · revision {edited.revision}."
        )
    else:
        additions = (
            ("rules", add_rule, "Rule"),
            ("examples", add_example, "Example"),
            ("relations", add_relation, "relation"),
        )
        selected = next(
            (
                (lane, content, label)
                for lane, content, label in additions
                if content is not None
            ),
            None,
        )
        if selected is not None:
            lane, content, label = selected
            edited = execute_ground_workspace_memory_add(
                AddGroundWorkspaceMemoryRequest(
                    workspace_name=name,
                    lane=lane,
                    content=content,
                    expected_revision=workspace.manifest.revision,
                ),
                store=store,
            )
            action_receipt = (
                f"Added {label} Memory [{edited.memory_uid[:8]}] · "
                f"revision {edited.revision}."
            )
    workspace = load_ground_workspace(store, name)
    if created:
        typer.secho(
            f"Created Ground workspace '{safe_terminal_text(name)}' as "
            f"{len(workspace.all_contexts)} physical Contexts.",
            fg=typer.colors.GREEN,
            bold=True,
        )
    if action_receipt:
        typer.secho(action_receipt, fg=typer.colors.GREEN, bold=True)
    if open_workflow._interactive_terminal() and not snapshot and not action_receipt:
        run_ground_workspace_viewer(
            workspace,
            navigation_contexts=load_ground_workspace_navigation_contexts(
                store,
                workspace,
            ),
        )
        return
    if snapshot or not action_receipt:
        typer.echo(render_ground_workspace_snapshot(workspace))
