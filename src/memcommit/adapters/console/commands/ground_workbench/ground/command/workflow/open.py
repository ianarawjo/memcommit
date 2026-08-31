"""Discover, select, and reopen physical Ground work and drafts."""

from __future__ import annotations

import sys
from typing import Literal

import typer

from memcommit.adapters.console.commands.ground_workbench.ground.workspace.catalog import (
    list_ground_workspace_catalog,
    list_ground_workspace_draft_catalog,
    reload_selected_ground_workspace,
    reload_selected_ground_workspace_draft,
)
from memcommit.adapters.console.commands.ground_workbench.ground.workspace.viewer.screen import (
    run_ground_workspace_viewer,
)
from memcommit.adapters.console.terminal.components.operation_launcher.location import (
    session_picker_location,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    choose_session,
)
from memcommit.application.operations.ground_workbench.ground.contracts import GroundError
from memcommit.application.operations.ground_workbench.ground.workspace_runtime import (
    load_ground_workspace_navigation_contexts,
)
from memcommit.persistence.store import MemoryStore

from . import create as create_workflow


GroundViewExit = Literal["CLOSED", "BACK_TO_PICKER"]


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _run_ground_session_picker(store: MemoryStore) -> None:
    """Loop over physical work and drafts until the person quits."""

    while True:
        workspace_catalog = list_ground_workspace_catalog(store)
        draft_catalog = list_ground_workspace_draft_catalog(store)
        workspace_by_key = {
            entry.picker_entry.key: entry for entry in workspace_catalog
        }
        draft_by_key = {entry.picker_entry.key: entry for entry in draft_catalog}
        receipt = choose_session(
            (
                *(entry.picker_entry for entry in workspace_catalog),
                *(entry.picker_entry for entry in draft_catalog),
            ),
            title="MEM GROUND · WORKSPACES",
            new_receipt=SessionNewReceipt(
                kind="ground",
                argv=("mem", "ground"),
                action_label="START NEW GROUND WORKSPACE",
                action_description=(
                    "Start blank, then choose or change its Context Save "
                    "Location above the Goal before exact save approval."
                ),
            ),
            initial_sort_mode="recent",
            initial_group_mode="context",
            catalog_label="Ground workspaces",
            enter_action="open Ground",
            location=session_picker_location(store),
        )
        if receipt is None:
            typer.echo("Ground selection cancelled.")
            return
        if isinstance(receipt, SessionNewReceipt):
            if receipt.kind != "ground" or receipt.argv != ("mem", "ground"):
                raise GroundError("Ground picker returned an invalid new receipt.")
            outcome = create_workflow._run_new_ground_shell()
        else:
            if not isinstance(receipt, SessionOpenReceipt) or receipt.kind not in {
                "ground-workspace",
                "ground-workspace-draft",
            }:
                raise GroundError("Ground picker returned an invalid selection.")
            if receipt.kind == "ground-workspace":
                entry = workspace_by_key.get(receipt.key)
                if entry is None or receipt.argv != entry.picker_entry.reopen_argv:
                    raise GroundError(
                        "Ground picker changed the selected workspace command."
                    )
                workspace = reload_selected_ground_workspace(store, entry)
                run_ground_workspace_viewer(
                    workspace,
                    navigation_contexts=load_ground_workspace_navigation_contexts(
                        store,
                        workspace,
                    ),
                )
                outcome = "CLOSED"
            else:
                entry = draft_by_key.get(receipt.key)
                if entry is None or receipt.argv != entry.picker_entry.reopen_argv:
                    raise GroundError(
                        "Ground picker changed the selected draft command."
                    )
                draft = reload_selected_ground_workspace_draft(store, entry)
                outcome = create_workflow._run_new_ground_shell(draft=draft)
        if outcome != "BACK_TO_PICKER":
            return
