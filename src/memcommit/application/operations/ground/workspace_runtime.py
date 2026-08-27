"""MemoryStore composition for physical Ground workspace creation and loading."""

from __future__ import annotations

import uuid

from memcommit.core.context import AutoCheckpoint, Context
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.application.operations.ground.workspace_model import (
    GROUND_WORKSPACE_LANES,
    GroundWorkspace,
    GroundWorkspaceError,
    GroundWorkspaceLane,
    ground_workspace_context_names,
    is_ground_workspace_manifest_memory,
    load_ground_workspace_records,
)
from memcommit.application.operations.ground.workspace_application import (
    AddGroundWorkspaceMemoryRequest,
    AdoptGroundWorkspaceMemoriesRequest,
    AdoptGroundWorkspaceMemoriesResult,
    CreateGroundWorkspaceRequest,
    CreateGroundWorkspaceResult,
    GroundWorkspaceCreationPort,
    GroundWorkspaceEditingPort,
    GroundWorkspaceEditResult,
    RemoveGroundWorkspaceMemoryRequest,
    ReplaceGroundWorkspaceMemoryRequest,
    add_ground_workspace_memory,
    adopt_ground_workspace_memories,
    create_ground_workspace,
    remove_ground_workspace_memory,
    replace_ground_workspace_memory,
)
from memcommit.application.semantic.goal_focus import FrozenGoalFocus
from memcommit.persistence.store import MemoryStore, context_record_digest, validate_context_name


class MemoryStoreGroundWorkspaceCreationPort(GroundWorkspaceCreationPort):
    """Publish the complete workspace under one Store command boundary."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def create(
        self,
        workspace: GroundWorkspace,
        *,
        goal_focus: FrozenGoalFocus | None = None,
    ) -> GroundWorkspace:
        for context in workspace.all_contexts:
            validate_portable_context_name(context.name)
        context_membership = [
            {"uid": context.uid, "name": context.name}
            for context in workspace.all_contexts
        ]
        entries = tuple(
            (
                context,
                AutoCheckpoint(
                    command="ground-init",
                    args={
                        "ground_workspace": {
                            "version": 1,
                            "workspace_uid": workspace.uid,
                            "workspace_name": workspace.name,
                            "lane": (
                                "root"
                                if context.name == workspace.name
                                else context.name.removeprefix(workspace.name + "/")
                            ),
                        },
                        "command_contexts": context_membership,
                        "goal_focus": (
                            None if goal_focus is None else goal_focus.receipt_record()
                        ),
                    },
                    description=(
                        f"Initialized Ground workspace '{workspace.name}'"
                        if context.name == workspace.name
                        else f"Initialized Ground workspace lane '{context.name}'"
                    ),
                ),
            )
            for context in workspace.all_contexts
        )
        created = self._store.create_missing_contexts(
            entries,
            make_current=None,
            require_all_new=True,
        )
        if tuple(context.uid for context in created) != tuple(
            context.uid for context in workspace.all_contexts
        ):
            raise GroundWorkspaceError(
                "Ground workspace Store receipt did not contain every Context."
            )
        return load_ground_workspace(self._store, workspace.name)


class MemoryStoreGroundWorkspaceEditingPort(GroundWorkspaceEditingPort):
    """Commit Ground edits as root-scoped, multi-Context command units."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def load(self, name: str) -> GroundWorkspace:
        return load_ground_workspace(self._store, name)

    def commit_edit(
        self,
        workspace: GroundWorkspace,
        *,
        lane: GroundWorkspaceLane,
        memory_uid: str,
        action: str,
        goal_focus: FrozenGoalFocus | None = None,
    ) -> tuple[GroundWorkspace, str]:
        if action not in {"add-memory", "replace-memory", "remove-memory"}:
            raise GroundWorkspaceError("Ground workspace edit action is invalid.")
        lane_context = workspace.lane(lane)
        changed = (workspace.root, lane_context)
        command_uid = str(uuid.uuid4())
        membership = [
            {"uid": context.uid, "name": context.name}
            for context in changed
        ]
        ground_command = {
            "version": 1,
            "kind": "edit",
            "workspace_uid": workspace.uid,
            "workspace_name": workspace.name,
            "command_uid": command_uid,
            "action": action,
            "lane": lane,
            "memory_uid": memory_uid,
            "revision": workspace.manifest.revision,
            "goal_focus": (
                None if goal_focus is None else goal_focus.receipt_record()
            ),
        }
        entries = []
        for context in changed:
            expected_digest = getattr(context, "_store_digest", None)
            if not isinstance(expected_digest, str):
                raise GroundWorkspaceError(
                    "Ground workspace edit is missing its Context CAS base."
                )
            entries.append(
                (
                    context,
                    AutoCheckpoint(
                        command="ground",
                        args={
                            "ground_workspace_command": ground_command,
                            "command_contexts": membership,
                        },
                        description=(
                            f"{action.replace('-', ' ').title()} "
                            f"[{memory_uid[:8]}] in Ground lane "
                            f"'{lane_context.name}'."
                        ),
                    ),
                    expected_digest,
                )
            )
        self._store.save_context_command_batch(entries)
        committed = load_ground_workspace(self._store, workspace.name)
        if (
            committed.manifest.revision != workspace.manifest.revision
            or context_record_digest(committed.root)
            != context_record_digest(workspace.root)
            or context_record_digest(committed.lane(lane))
            != context_record_digest(lane_context)
        ):
            raise GroundWorkspaceError(
                "Ground workspace edit receipt does not match the committed state."
            )
        return committed, command_uid

    def commit_adoption(
        self,
        workspace: GroundWorkspace,
        *,
        request: AdoptGroundWorkspaceMemoriesRequest,
        memory_uids: tuple[str, ...],
    ) -> tuple[GroundWorkspace, str]:
        """Publish a complete semantic proposal as one undoable Ground unit."""

        lane_context = workspace.lane(request.lane)
        changed = (workspace.root, lane_context)
        command_uid = str(uuid.uuid4())
        membership = [
            {"uid": context.uid, "name": context.name}
            for context in changed
        ]
        ground_command = {
            "version": 1,
            "kind": "edit",
            "workspace_uid": workspace.uid,
            "workspace_name": workspace.name,
            "command_uid": command_uid,
            "action": f"adopt-{request.source_operation}",
            "lane": request.lane,
            "memory_uids": list(memory_uids),
            "revision": workspace.manifest.revision,
            "semantic_result": {
                "operation": request.source_operation,
                "analysis_digest": request.analysis_digest,
            },
        }
        entries = []
        for context in changed:
            expected_digest = getattr(context, "_store_digest", None)
            if not isinstance(expected_digest, str):
                raise GroundWorkspaceError(
                    "Ground semantic adoption is missing its Context CAS base."
                )
            entries.append(
                (
                    context,
                    AutoCheckpoint(
                        command="ground",
                        args={
                            "ground_workspace_command": ground_command,
                            "command_contexts": membership,
                        },
                        description=(
                            f"Adopted {len(memory_uids)} {request.source_operation.title()} "
                            f"proposal Memories in Ground lane '{lane_context.name}'."
                        ),
                    ),
                    expected_digest,
                )
            )
        changed_names = {context.name for context in changed}
        source_bindings = tuple(
            binding
            for binding in request.source_bindings
            if binding[0] not in changed_names
        )
        self._store.save_context_command_batch(
            entries,
            source_bindings=source_bindings,
        )
        committed = load_ground_workspace(self._store, workspace.name)
        if (
            committed.manifest.revision != workspace.manifest.revision
            or context_record_digest(committed.root)
            != context_record_digest(workspace.root)
            or context_record_digest(committed.lane(request.lane))
            != context_record_digest(lane_context)
        ):
            raise GroundWorkspaceError(
                "Ground semantic adoption receipt does not match the committed state."
            )
        return committed, command_uid


def load_ground_workspace(store: MemoryStore, name: str) -> GroundWorkspace:
    """Load one exact physical workspace without following embedded content."""

    names = ground_workspace_context_names(name)
    for context_name in names:
        validate_context_name(context_name)
    loaded = tuple(store.load_direct(context_name) for context_name in names)
    return load_ground_workspace_records(
        loaded[0],
        **dict(zip(GROUND_WORKSPACE_LANES, loaded[1:], strict=True)),
    )


def ground_workspace_exists(store: MemoryStore, name: str) -> bool:
    """Return whether the exact root is a valid complete Ground workspace."""

    try:
        load_ground_workspace(store, name)
    except (FileNotFoundError, GroundWorkspaceError, OSError, ValueError):
        return False
    return True


def list_ground_workspace_names(store: MemoryStore) -> tuple[str, ...]:
    """Discover local workspace roots by their first-class manifest Memory."""

    roots: list[str] = []
    for name in store.list_context_names():
        try:
            context = store.load_direct(name)
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            continue
        if sum(
            is_ground_workspace_manifest_memory(item)
            for item in context.iter_items()
        ) != 1:
            continue
        try:
            load_ground_workspace(store, name)
        except (FileNotFoundError, GroundWorkspaceError, OSError, ValueError):
            continue
        roots.append(name)
    return tuple(sorted(roots))


def load_ground_workspace_navigation_contexts(
    store: MemoryStore,
    workspace: GroundWorkspace,
) -> tuple[Context, ...]:
    """Load fixed lanes plus real local descendants under ``/contexts``.

    Lexical descendants are navigation rows, not hidden aggregate members.
    Embedded and granted pointers remain typed direct items in their owner
    Context and therefore do not become fabricated namespace rows.
    """

    prefix = workspace.contexts.name + "/"
    descendant_names = tuple(
        name
        for name in store.list_context_names()
        if name.startswith(prefix)
    )
    return (
        *workspace.all_contexts,
        *(store.load_direct(name) for name in descendant_names),
    )


def execute_ground_workspace_creation(
    request: CreateGroundWorkspaceRequest,
    *,
    store: MemoryStore,
) -> CreateGroundWorkspaceResult:
    """Execute one Ground workspace creation without terminal dependencies."""

    return create_ground_workspace(
        request,
        port=MemoryStoreGroundWorkspaceCreationPort(store),
    )


def execute_ground_workspace_memory_add(
    request: AddGroundWorkspaceMemoryRequest,
    *,
    store: MemoryStore,
) -> GroundWorkspaceEditResult:
    """Execute one root-plus-lane Ground Memory addition."""

    return add_ground_workspace_memory(
        request,
        port=MemoryStoreGroundWorkspaceEditingPort(store),
    )


def execute_ground_workspace_memory_replace(
    request: ReplaceGroundWorkspaceMemoryRequest,
    *,
    store: MemoryStore,
) -> GroundWorkspaceEditResult:
    """Execute one root-plus-lane Ground Memory replacement."""

    return replace_ground_workspace_memory(
        request,
        port=MemoryStoreGroundWorkspaceEditingPort(store),
    )


def execute_ground_workspace_memory_remove(
    request: RemoveGroundWorkspaceMemoryRequest,
    *,
    store: MemoryStore,
) -> GroundWorkspaceEditResult:
    """Execute one root-plus-lane Ground Memory removal."""

    return remove_ground_workspace_memory(
        request,
        port=MemoryStoreGroundWorkspaceEditingPort(store),
    )


def execute_ground_workspace_memories_adoption(
    request: AdoptGroundWorkspaceMemoriesRequest,
    *,
    store: MemoryStore,
) -> AdoptGroundWorkspaceMemoriesResult:
    """Execute one atomic, provenance-bearing semantic Ground adoption."""

    return adopt_ground_workspace_memories(
        request,
        port=MemoryStoreGroundWorkspaceEditingPort(store),
    )


__all__ = [
    "MemoryStoreGroundWorkspaceCreationPort",
    "MemoryStoreGroundWorkspaceEditingPort",
    "execute_ground_workspace_creation",
    "execute_ground_workspace_memories_adoption",
    "execute_ground_workspace_memory_add",
    "execute_ground_workspace_memory_remove",
    "execute_ground_workspace_memory_replace",
    "ground_workspace_exists",
    "list_ground_workspace_names",
    "load_ground_workspace_navigation_contexts",
    "load_ground_workspace",
]
