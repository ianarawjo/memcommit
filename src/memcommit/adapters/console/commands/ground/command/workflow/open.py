"""Discover, select, and reopen Ground work and drafts."""

from __future__ import annotations

from collections.abc import Sequence
import sys
from typing import Literal

import typer

from memcommit.adapters.console.commands.ground.session_picker import (
    GroundSessionCatalogEntry,
    ground_session_picker_location,
    list_ground_session_catalog,
    reload_selected_ground_session,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    choose_session,
)
from memcommit.adapters.console.commands.ground.workspace.viewer.screen import (
    run_ground_workspace_viewer,
)
from memcommit.adapters.console.commands.ground.workspace.catalog import (
    list_ground_workspace_catalog,
    list_ground_workspace_draft_catalog,
    reload_selected_ground_workspace,
    reload_selected_ground_workspace_draft,
)
from memcommit.application.operations.ground.model import GroundError
from memcommit.application.operations.ground.workspace_runtime import (
    load_ground_workspace_navigation_contexts,
)
from memcommit.persistence.store import MemoryStore

from . import create as create_workflow
from .session import dialogue as session_dialogue


GroundViewExit = Literal["CLOSED", "BACK_TO_PICKER"]


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _run_ground_session_picker(
    store: MemoryStore,
    *,
    catalog: Sequence[GroundSessionCatalogEntry] | None = None,
) -> None:
    """Loop over refreshed saved work until the person explicitly quits."""
    next_catalog: Sequence[GroundSessionCatalogEntry] | None = catalog
    while True:
        frozen_catalog = tuple(
            list_ground_session_catalog(store) if next_catalog is None else next_catalog
        )
        workspace_catalog = list_ground_workspace_catalog(store)
        draft_catalog = list_ground_workspace_draft_catalog(store)
        # A view can mutate the saved Ground before B returns here. Reuse the
        # optional caller snapshot only for the first picker render; every
        # later pass rediscovers identities, revisions, digests, and ordering.
        next_catalog = None
        legacy_by_key = {entry.picker_entry.key: entry for entry in frozen_catalog}
        workspace_by_key = {
            entry.picker_entry.key: entry for entry in workspace_catalog
        }
        draft_by_key = {entry.picker_entry.key: entry for entry in draft_catalog}
        receipt = choose_session(
            (
                *(entry.picker_entry for entry in workspace_catalog),
                *(entry.picker_entry for entry in draft_catalog),
                *(entry.picker_entry for entry in frozen_catalog),
            ),
            # Physical and not-yet-created work share this one session list.
            # Their row status, not a second launcher, distinguishes them.
            title="MEM GROUND · SESSIONS",
            new_receipt=SessionNewReceipt(
                kind="ground",
                argv=("mem", "ground"),
                action_label="START NEW GROUND SESSION",
                action_description=(
                    "Start blank, then choose or change its Context Save "
                    "Location above the Goal before exact save approval."
                ),
            ),
            initial_sort_mode="recent",
            initial_group_mode="context",
            catalog_label="Ground sessions",
            enter_action="open Ground",
            location=ground_session_picker_location(),
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
                "ground",
                "ground-workspace",
                "ground-workspace-draft",
            }:
                raise GroundError("Ground picker returned an invalid selection.")
            if receipt.kind == "ground-workspace":
                workspace_entry = workspace_by_key.get(receipt.key)
                if (
                    workspace_entry is None
                    or receipt.argv != workspace_entry.picker_entry.reopen_argv
                ):
                    raise GroundError(
                        "Ground picker changed the selected workspace command."
                    )
                workspace = reload_selected_ground_workspace(
                    store,
                    workspace_entry,
                )
                run_ground_workspace_viewer(
                    workspace,
                    navigation_contexts=load_ground_workspace_navigation_contexts(
                        store,
                        workspace,
                    ),
                )
                outcome = "CLOSED"
            elif receipt.kind == "ground-workspace-draft":
                draft_entry = draft_by_key.get(receipt.key)
                if (
                    draft_entry is None
                    or receipt.argv != draft_entry.picker_entry.reopen_argv
                ):
                    raise GroundError(
                        "Ground picker changed the selected draft command."
                    )
                draft = reload_selected_ground_workspace_draft(
                    store,
                    draft_entry,
                )
                outcome = create_workflow._run_new_ground_shell(draft=draft)
            else:
                entry = legacy_by_key.get(receipt.key)
                if entry is None or receipt.argv != entry.picker_entry.reopen_argv:
                    raise GroundError(
                        "Ground picker changed the selected reopen command."
                    )
                # The picker is only a read-only projection. Re-load by the
                # catalog key and compare UID, revision, and digest so neither
                # deletion nor replacement can fall through to create-or-resume.
                session = reload_selected_ground_session(store, entry)
                outcome = session_dialogue._run_existing_ground_shell(session)
        if outcome != "BACK_TO_PICKER":
            return
