"""Read-only launcher projection for physical Ground workspace roots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from memcommit.context import Memory
from memcommit.ground_workspace import GroundWorkspace
from memcommit.ground_workspace_runtime import (
    list_ground_workspace_names,
    load_ground_workspace,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionPickerEntry,
)
from memcommit.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class GroundWorkspaceCatalogEntry:
    picker_entry: SessionPickerEntry
    workspace_uid: str
    revision: int
    context_evidence: tuple[tuple[str, str, str], ...]


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


__all__ = [
    "GroundWorkspaceCatalogEntry",
    "list_ground_workspace_catalog",
    "reload_selected_ground_workspace",
]
