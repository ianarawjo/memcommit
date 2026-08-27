"""Terminal-independent creation contract for Context-rooted Ground workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.core.context import Memory
from memcommit.application.operations.ground.model import validate_ground_goal
from memcommit.application.semantic.goal_focus import FrozenGoalFocus
from memcommit.application.operations.ground.workspace_model import (
    GroundWorkspace,
    GroundWorkspaceError,
    GroundWorkspaceLane,
    create_ground_workspace_records,
)


@dataclass(frozen=True)
class CreateGroundWorkspaceRequest:
    """One exact require-new Ground workspace creation request."""

    name: str
    goal: str = ""
    goal_focus: FrozenGoalFocus | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise GroundWorkspaceError("Ground workspace name is required.")
        if self.goal_focus is not None and not isinstance(
            self.goal_focus,
            FrozenGoalFocus,
        ):
            raise GroundWorkspaceError("Ground Goal focus must be a typed frame.")
        if self.goal and self.goal_focus is not None:
            raise GroundWorkspaceError(
                "Ground creation accepts Goal text or one Goal operand, not both."
            )
        validate_ground_goal(self.effective_goal, empty=True)

    @property
    def effective_goal(self) -> str:
        return self.goal_focus.text if self.goal_focus is not None else self.goal


@dataclass(frozen=True)
class CreateGroundWorkspaceResult:
    """Stable root and physical lane identities returned after publication."""

    name: str
    workspace_uid: str
    context_names: tuple[str, ...]
    context_uids: tuple[str, ...]
    goal_memory_uid: str | None


class GroundWorkspaceCreationPort(Protocol):
    """Validate and atomically publish one complete physical workspace."""

    def create(
        self,
        workspace: GroundWorkspace,
        *,
        goal_focus: FrozenGoalFocus | None = None,
    ) -> GroundWorkspace:
        """Create every Context require-new without changing global current."""


@dataclass(frozen=True)
class AddGroundWorkspaceMemoryRequest:
    """Add one ordinary Memory to one exact physical workspace lane."""

    workspace_name: str
    lane: GroundWorkspaceLane
    content: str
    expected_revision: int | None = None
    goal_focus: FrozenGoalFocus | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_name, str) or not self.workspace_name.strip():
            raise GroundWorkspaceError("Ground workspace name is required.")
        if not isinstance(self.content, str) or not self.content.strip():
            raise GroundWorkspaceError("Ground workspace Memory cannot be empty.")
        if self.lane == "goals":
            validate_ground_goal(self.content)
        if self.goal_focus is not None and (
            self.lane != "goals"
            or not isinstance(self.goal_focus, FrozenGoalFocus)
            or self.goal_focus.text != self.content.strip()
        ):
            raise GroundWorkspaceError(
                "A Ground Goal operand must exactly materialize into the goals lane."
            )
        if self.expected_revision is not None and (
            isinstance(self.expected_revision, bool)
            or not isinstance(self.expected_revision, int)
            or self.expected_revision < 0
        ):
            raise GroundWorkspaceError("Expected Ground revision is invalid.")


@dataclass(frozen=True)
class ReplaceGroundWorkspaceMemoryRequest:
    """Replace one directly owned Memory while preserving its identity."""

    workspace_name: str
    lane: GroundWorkspaceLane
    memory_uid: str
    content: str
    expected_revision: int | None = None
    goal_focus: FrozenGoalFocus | None = None

    def __post_init__(self) -> None:
        AddGroundWorkspaceMemoryRequest(
            workspace_name=self.workspace_name,
            lane=self.lane,
            content=self.content,
            expected_revision=self.expected_revision,
            goal_focus=self.goal_focus,
        )
        if not isinstance(self.memory_uid, str) or not self.memory_uid:
            raise GroundWorkspaceError("Ground workspace Memory UID is required.")


@dataclass(frozen=True)
class RemoveGroundWorkspaceMemoryRequest:
    """Remove one directly owned Memory from one physical lane."""

    workspace_name: str
    lane: GroundWorkspaceLane
    memory_uid: str
    expected_revision: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_name, str) or not self.workspace_name.strip():
            raise GroundWorkspaceError("Ground workspace name is required.")
        if not isinstance(self.memory_uid, str) or not self.memory_uid:
            raise GroundWorkspaceError("Ground workspace Memory UID is required.")
        if self.expected_revision is not None and (
            isinstance(self.expected_revision, bool)
            or not isinstance(self.expected_revision, int)
            or self.expected_revision < 0
        ):
            raise GroundWorkspaceError("Expected Ground revision is invalid.")


@dataclass(frozen=True)
class GroundWorkspaceEditResult:
    """Stable receipt for one committed root-plus-lane command."""

    workspace_name: str
    workspace_uid: str
    revision: int
    lane: GroundWorkspaceLane
    memory_uid: str
    command_uid: str
    affected_context_names: tuple[str, ...]


@dataclass(frozen=True)
class AdoptGroundWorkspaceMemoriesRequest:
    """Atomically adopt one exact semantic proposal into a Ground lane."""

    workspace_name: str
    lane: GroundWorkspaceLane
    contents: tuple[str, ...]
    expected_workspace_uid: str
    expected_revision: int
    expected_root_digest: str
    expected_lane_digest: str
    source_operation: str
    analysis_digest: str
    source_bindings: tuple[tuple[str, str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_name, str) or not self.workspace_name.strip():
            raise GroundWorkspaceError("Ground workspace name is required.")
        if self.lane not in {"rules", "examples"}:
            raise GroundWorkspaceError(
                "Semantic Ground adoption supports only Rules or Examples."
            )
        if (
            not isinstance(self.contents, tuple)
            or not self.contents
            or any(not isinstance(item, str) or not item.strip() for item in self.contents)
        ):
            raise GroundWorkspaceError(
                "Semantic Ground adoption requires nonblank proposed Memories."
            )
        if not isinstance(self.expected_workspace_uid, str) or not self.expected_workspace_uid:
            raise GroundWorkspaceError("Expected Ground workspace identity is invalid.")
        if (
            isinstance(self.expected_revision, bool)
            or not isinstance(self.expected_revision, int)
            or self.expected_revision < 0
        ):
            raise GroundWorkspaceError("Expected Ground revision is invalid.")
        if any(
            not isinstance(value, str) or len(value) != 64
            for value in (
                self.expected_root_digest,
                self.expected_lane_digest,
                self.analysis_digest,
            )
        ):
            raise GroundWorkspaceError("Semantic Ground adoption digest is invalid.")
        if self.source_operation not in {"distill", "elaborate"}:
            raise GroundWorkspaceError("Semantic Ground adoption operation is invalid.")
        names = tuple(binding[0] for binding in self.source_bindings)
        if len(names) != len(set(names)) or any(
            len(binding) != 3
            or any(not isinstance(value, str) or not value for value in binding)
            for binding in self.source_bindings
        ):
            raise GroundWorkspaceError("Semantic Ground Source bindings are invalid.")


@dataclass(frozen=True)
class AdoptGroundWorkspaceMemoriesResult:
    """Receipt for one all-or-nothing semantic proposal adoption."""

    workspace_name: str
    workspace_uid: str
    revision: int
    lane: GroundWorkspaceLane
    memory_uids: tuple[str, ...]
    command_uid: str
    affected_context_names: tuple[str, ...]


class GroundWorkspaceEditingPort(Protocol):
    """Load and atomically publish one reviewed Ground-local edit."""

    def load(self, name: str) -> GroundWorkspace:
        """Load one exact physical workspace."""

    def commit_edit(
        self,
        workspace: GroundWorkspace,
        *,
        lane: GroundWorkspaceLane,
        memory_uid: str,
        action: str,
        goal_focus: FrozenGoalFocus | None = None,
    ) -> tuple[GroundWorkspace, str]:
        """Commit the changed root and lane and return its command UID."""

    def commit_adoption(
        self,
        workspace: GroundWorkspace,
        *,
        request: AdoptGroundWorkspaceMemoriesRequest,
        memory_uids: tuple[str, ...],
    ) -> tuple[GroundWorkspace, str]:
        """Commit one complete semantic proposal as one Ground command."""


def create_ground_workspace(
    request: CreateGroundWorkspaceRequest,
    *,
    port: GroundWorkspaceCreationPort,
) -> CreateGroundWorkspaceResult:
    """Build and publish one exact workspace through an injected Store port."""

    workspace = create_ground_workspace_records(
        request.name,
        goal=request.effective_goal,
    )
    created = port.create(workspace, goal_focus=request.goal_focus)
    if (
        created.uid != workspace.uid
        or tuple(context.name for context in created.all_contexts)
        != tuple(context.name for context in workspace.all_contexts)
        or tuple(context.uid for context in created.all_contexts)
        != tuple(context.uid for context in workspace.all_contexts)
    ):
        raise GroundWorkspaceError(
            "Ground workspace creation returned a different physical workspace."
        )
    goal_items = tuple(created.goals.iter_items())
    goal_memory_uid = goal_items[0].uid if goal_items else None
    return CreateGroundWorkspaceResult(
        name=created.name,
        workspace_uid=created.uid,
        context_names=tuple(context.name for context in created.all_contexts),
        context_uids=tuple(context.uid for context in created.all_contexts),
        goal_memory_uid=goal_memory_uid,
    )


def add_ground_workspace_memory(
    request: AddGroundWorkspaceMemoryRequest,
    *,
    port: GroundWorkspaceEditingPort,
) -> GroundWorkspaceEditResult:
    """Add one ordinary Memory while advancing one workspace revision."""

    workspace = port.load(request.workspace_name)
    if (
        request.expected_revision is not None
        and workspace.manifest.revision != request.expected_revision
    ):
        raise GroundWorkspaceError(
            "Ground workspace changed after the reviewed edit was prepared."
        )
    lane_context = workspace.lane(request.lane)
    memory = lane_context.add(request.content)
    assert isinstance(memory, Memory)
    revised = workspace.advance_revision()
    committed, command_uid = port.commit_edit(
        revised,
        lane=request.lane,
        memory_uid=memory.uid,
        action="add-memory",
        goal_focus=request.goal_focus,
    )
    return GroundWorkspaceEditResult(
        workspace_name=committed.name,
        workspace_uid=committed.uid,
        revision=committed.manifest.revision,
        lane=request.lane,
        memory_uid=memory.uid,
        command_uid=command_uid,
        affected_context_names=(committed.root.name, lane_context.name),
    )


def replace_ground_workspace_memory(
    request: ReplaceGroundWorkspaceMemoryRequest,
    *,
    port: GroundWorkspaceEditingPort,
) -> GroundWorkspaceEditResult:
    """Replace one lane Memory and advance the workspace revision."""

    workspace = port.load(request.workspace_name)
    if (
        request.expected_revision is not None
        and workspace.manifest.revision != request.expected_revision
    ):
        raise GroundWorkspaceError(
            "Ground workspace changed after the reviewed edit was prepared."
        )
    lane_context = workspace.lane(request.lane)
    existing = lane_context.memories.get(request.memory_uid)
    if not isinstance(existing, Memory):
        raise GroundWorkspaceError(
            "Ground workspace replacement requires a directly owned Memory."
        )
    lane_context.replace(Memory(uid=existing.uid, content=request.content))
    revised = workspace.advance_revision()
    committed, command_uid = port.commit_edit(
        revised,
        lane=request.lane,
        memory_uid=existing.uid,
        action="replace-memory",
        goal_focus=request.goal_focus,
    )
    return GroundWorkspaceEditResult(
        workspace_name=committed.name,
        workspace_uid=committed.uid,
        revision=committed.manifest.revision,
        lane=request.lane,
        memory_uid=existing.uid,
        command_uid=command_uid,
        affected_context_names=(committed.root.name, lane_context.name),
    )


def remove_ground_workspace_memory(
    request: RemoveGroundWorkspaceMemoryRequest,
    *,
    port: GroundWorkspaceEditingPort,
) -> GroundWorkspaceEditResult:
    """Remove one lane Memory and advance the workspace revision."""

    workspace = port.load(request.workspace_name)
    if (
        request.expected_revision is not None
        and workspace.manifest.revision != request.expected_revision
    ):
        raise GroundWorkspaceError(
            "Ground workspace changed after the reviewed edit was prepared."
        )
    lane_context = workspace.lane(request.lane)
    existing = lane_context.memories.get(request.memory_uid)
    if not isinstance(existing, Memory):
        raise GroundWorkspaceError(
            "Ground workspace removal requires a directly owned Memory."
        )
    lane_context.remove(existing.uid)
    revised = workspace.advance_revision()
    committed, command_uid = port.commit_edit(
        revised,
        lane=request.lane,
        memory_uid=existing.uid,
        action="remove-memory",
    )
    return GroundWorkspaceEditResult(
        workspace_name=committed.name,
        workspace_uid=committed.uid,
        revision=committed.manifest.revision,
        lane=request.lane,
        memory_uid=existing.uid,
        command_uid=command_uid,
        affected_context_names=(committed.root.name, lane_context.name),
    )


def adopt_ground_workspace_memories(
    request: AdoptGroundWorkspaceMemoriesRequest,
    *,
    port: GroundWorkspaceEditingPort,
) -> AdoptGroundWorkspaceMemoriesResult:
    """Adopt every proposed Memory or publish none of the proposal."""

    workspace = port.load(request.workspace_name)
    lane_context = workspace.lane(request.lane)
    root_digest = getattr(workspace.root, "_store_digest", None)
    lane_digest = getattr(lane_context, "_store_digest", None)
    if (
        workspace.uid != request.expected_workspace_uid
        or workspace.manifest.revision != request.expected_revision
        or root_digest != request.expected_root_digest
        or lane_digest != request.expected_lane_digest
    ):
        raise GroundWorkspaceError(
            "Ground workspace changed after the semantic proposal was reviewed."
        )
    memories = tuple(lane_context.add(content.strip()) for content in request.contents)
    if any(not isinstance(memory, Memory) for memory in memories):  # pragma: no cover
        raise GroundWorkspaceError("Ground semantic adoption produced an invalid Memory.")
    memory_uids = tuple(memory.uid for memory in memories)
    revised = workspace.advance_revision()
    committed, command_uid = port.commit_adoption(
        revised,
        request=request,
        memory_uids=memory_uids,
    )
    return AdoptGroundWorkspaceMemoriesResult(
        workspace_name=committed.name,
        workspace_uid=committed.uid,
        revision=committed.manifest.revision,
        lane=request.lane,
        memory_uids=memory_uids,
        command_uid=command_uid,
        affected_context_names=(committed.root.name, lane_context.name),
    )


__all__ = [
    "AddGroundWorkspaceMemoryRequest",
    "AdoptGroundWorkspaceMemoriesRequest",
    "AdoptGroundWorkspaceMemoriesResult",
    "CreateGroundWorkspaceRequest",
    "CreateGroundWorkspaceResult",
    "GroundWorkspaceCreationPort",
    "GroundWorkspaceEditingPort",
    "GroundWorkspaceEditResult",
    "RemoveGroundWorkspaceMemoryRequest",
    "ReplaceGroundWorkspaceMemoryRequest",
    "add_ground_workspace_memory",
    "adopt_ground_workspace_memories",
    "create_ground_workspace",
    "remove_ground_workspace_memory",
    "replace_ground_workspace_memory",
]
