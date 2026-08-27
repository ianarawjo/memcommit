"""Read-only launcher projection for physical Ground workspace roots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from memcommit.context import Memory
from memcommit.application.operations.ground.workspace_model import GroundWorkspace
from memcommit.application.operations.ground.workspace_draft import (
    GroundWorkspaceDraft,
    ground_workspace_draft_digest,
)
from memcommit.application.operations.ground.workspace_draft_store import GroundWorkspaceDraftStore
from memcommit.application.operations.ground.workspace_runtime import (
    ground_workspace_exists,
    list_ground_workspace_names,
    load_ground_workspace,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionPickerEntry,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class GroundWorkspaceCatalogEntry:
    picker_entry: SessionPickerEntry
    workspace_uid: str
    revision: int
    context_evidence: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class GroundWorkspaceDraftCatalogEntry:
    picker_entry: SessionPickerEntry
    draft_uid: str
    draft_revision: int
    draft_digest: str


def _latest_timestamp(store: MemoryStore, workspace: GroundWorkspace) -> float:
    timestamps = [
        checkpoint.get("timestamp")
        for context in workspace.all_contexts
        for checkpoint in store.list_checkpoints(context.name)[:1]
    ]
    parsed = [
        datetime.fromisoformat(value).timestamp()
        for value in timestamps
        if isinstance(value, str)
    ]
    return max(parsed, default=0.0)


def _goal_text(workspace: GroundWorkspace) -> str:
    goals = tuple(
        item for item in workspace.goals.iter_items() if isinstance(item, Memory)
    )
    if not goals:
        return "(Goal not yet stated)"
    if len(goals) == 1:
        return goals[0].content
    return f"({len(goals)} Goal Memories; review required)"


def _entry_evidence(
    workspace: GroundWorkspace,
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (context.uid, context.name, context_record_digest(context))
        for context in workspace.all_contexts
    )


def list_ground_workspace_catalog(
    store: MemoryStore,
) -> tuple[GroundWorkspaceCatalogEntry, ...]:
    entries: list[GroundWorkspaceCatalogEntry] = []
    for name in list_ground_workspace_names(store):
        workspace = load_ground_workspace(store, name)
        counts = {
            lane: len(tuple(workspace.lane(lane).iter_items()))
            for lane in ("goals", "rules", "examples", "contexts", "relations")
        }
        detail = "\n".join(
            (
                f"Goal: {display_escape_text(_goal_text(workspace))}",
                "Physical Contexts: 6 · "
                + " · ".join(
                    f"{lane.title()} {count}" for lane, count in counts.items()
                ),
                "Global current Context is not changed when this workspace opens.",
            )
        )
        picker = SessionPickerEntry(
            kind="ground-workspace",
            key=workspace.name,
            title=workspace.name,
            status=(
                f"{workspace.manifest.status} · rev "
                f"{workspace.manifest.revision} · PHYSICAL"
            ),
            subtitle=_goal_text(workspace),
            group=(workspace.name.rpartition("/")[0] or "Ground workspaces"),
            sort_timestamp=_latest_timestamp(store, workspace),
            detail=detail,
            reopen_argv=("mem", "ground", workspace.name),
        )
        entries.append(
            GroundWorkspaceCatalogEntry(
                picker_entry=picker,
                workspace_uid=workspace.uid,
                revision=workspace.manifest.revision,
                context_evidence=_entry_evidence(workspace),
            )
        )
    return tuple(entries)


def list_ground_workspace_draft_catalog(
    store: MemoryStore,
) -> tuple[GroundWorkspaceDraftCatalogEntry, ...]:
    """Project hidden resume receipts without treating them as workspaces."""

    entries: list[GroundWorkspaceDraftCatalogEntry] = []
    draft_store = GroundWorkspaceDraftStore(store)
    for draft in draft_store.list():
        # A successful create followed by an interrupted receipt cleanup must
        # never produce two visible objects for one physical workspace.
        if ground_workspace_exists(store, draft.workspace_name):
            continue
        modified = datetime.fromisoformat(draft.updated_at)
        detail = "\n".join(
            (
                f"Goal: {display_escape_text(draft.goal)}",
                f"Save Location: {display_escape_text(draft.workspace_name)}",
                "Physical Contexts: 0 · manifest 0 · checkpoints 0",
                "Resume receipt only; exact creation approval is still required.",
            )
        )
        picker = SessionPickerEntry(
            kind="ground-workspace-draft",
            key=draft.uid,
            title=draft.workspace_name,
            status=f"DRAFT · rev {draft.revision} · NOT CREATED",
            subtitle=draft.goal,
            group=(
                draft.workspace_name.rpartition("/")[0]
                or "Ground drafts"
            ),
            sort_timestamp=modified.timestamp(),
            detail=detail,
            reopen_argv=(
                "mem",
                "ground",
                "--resume-draft",
                draft.uid,
            ),
        )
        entries.append(
            GroundWorkspaceDraftCatalogEntry(
                picker_entry=picker,
                draft_uid=draft.uid,
                draft_revision=draft.revision,
                draft_digest=ground_workspace_draft_digest(draft),
            )
        )
    return tuple(entries)


def reload_selected_ground_workspace(
    store: MemoryStore,
    entry: GroundWorkspaceCatalogEntry,
) -> GroundWorkspace:
    workspace = load_ground_workspace(store, entry.picker_entry.key)
    if (
        workspace.uid != entry.workspace_uid
        or workspace.manifest.revision != entry.revision
        or _entry_evidence(workspace) != entry.context_evidence
    ):
        raise ValueError(
            f"Selected Ground workspace '{entry.picker_entry.key}' changed "
            "while the list was open; reopen the list."
        )
    return workspace


def reload_selected_ground_workspace_draft(
    store: MemoryStore,
    entry: GroundWorkspaceDraftCatalogEntry,
) -> GroundWorkspaceDraft:
    draft = GroundWorkspaceDraftStore(store).load(entry.draft_uid)
    if (
        draft.revision != entry.draft_revision
        or ground_workspace_draft_digest(draft) != entry.draft_digest
    ):
        raise ValueError(
            f"Selected Ground draft '{draft.workspace_name}' changed while "
            "the list was open; reopen the list."
        )
    if ground_workspace_exists(store, draft.workspace_name):
        raise ValueError(
            f"Ground workspace '{draft.workspace_name}' already exists; "
            "open the physical workspace instead."
        )
    return draft


__all__ = [
    "GroundWorkspaceDraftCatalogEntry",
    "GroundWorkspaceCatalogEntry",
    "list_ground_workspace_draft_catalog",
    "list_ground_workspace_catalog",
    "reload_selected_ground_workspace_draft",
    "reload_selected_ground_workspace",
]
