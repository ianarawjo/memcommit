"""Context-rooted common Ground workspace domain values.

A Ground workspace is not a parallel session document.  It is one ordinary
Context root plus a fixed lexical subtree whose contents remain ordinary
Memories and Context relationships.  This module owns only that shape; Store
I/O, terminal presentation, semantic inference, and command history live at
their respective boundaries.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, replace
from typing import Literal

from memcommit.core.context import Context, Memory


GROUND_WORKSPACE_SCHEMA_VERSION = 1
GROUND_WORKSPACE_MANIFEST_KIND = "memcommit.application.operations.ground.model-workspace"
GroundWorkspaceStatus = Literal["OPEN", "GROUNDED", "DEFERRED"]
GroundWorkspaceLane = Literal[
    "goals",
    "rules",
    "examples",
    "contexts",
    "relations",
]
GROUND_WORKSPACE_LANES: tuple[GroundWorkspaceLane, ...] = (
    "goals",
    "rules",
    "examples",
    "contexts",
    "relations",
)
_GROUND_WORKSPACE_STATUSES = {"OPEN", "GROUNDED", "DEFERRED"}


class GroundWorkspaceError(ValueError):
    """A physical Ground workspace is missing or internally inconsistent."""


@dataclass(frozen=True)
class GroundWorkspaceManifest:
    """Minimal first-class Memory payload identifying one workspace root."""

    workspace_uid: str
    schema_version: int = GROUND_WORKSPACE_SCHEMA_VERSION
    revision: int = 0
    status: GroundWorkspaceStatus = "OPEN"

    def __post_init__(self) -> None:
        try:
            canonical_uid = str(uuid.UUID(self.workspace_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise GroundWorkspaceError(
                "Ground workspace identity must be a canonical UUID."
            ) from error
        if canonical_uid != self.workspace_uid:
            raise GroundWorkspaceError(
                "Ground workspace identity must be a canonical UUID."
            )
        if self.schema_version != GROUND_WORKSPACE_SCHEMA_VERSION:
            raise GroundWorkspaceError(
                "Unsupported Ground workspace schema version."
            )
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 0
        ):
            raise GroundWorkspaceError("Ground workspace revision is invalid.")
        if self.status not in _GROUND_WORKSPACE_STATUSES:
            raise GroundWorkspaceError("Ground workspace status is invalid.")

    def to_memory_content(self) -> str:
        """Return the canonical structured content of the manifest Memory."""

        return json.dumps(
            {
                "kind": GROUND_WORKSPACE_MANIFEST_KIND,
                "revision": self.revision,
                "schema_version": self.schema_version,
                "status": self.status,
                "workspace_uid": self.workspace_uid,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_memory(cls, memory: Memory) -> "GroundWorkspaceManifest":
        """Decode one exact manifest Memory without accepting extra fields."""

        try:
            value = json.loads(memory.content)
        except (json.JSONDecodeError, TypeError) as error:
            raise GroundWorkspaceError(
                "Ground workspace manifest Memory is invalid."
            ) from error
        expected = {
            "kind",
            "revision",
            "schema_version",
            "status",
            "workspace_uid",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise GroundWorkspaceError(
                "Ground workspace manifest Memory is invalid."
            )
        if value.get("kind") != GROUND_WORKSPACE_MANIFEST_KIND:
            raise GroundWorkspaceError(
                "Ground workspace manifest kind is invalid."
            )
        return cls(
            workspace_uid=value["workspace_uid"],
            schema_version=value["schema_version"],
            revision=value["revision"],
            status=value["status"],
        )


@dataclass(frozen=True)
class GroundWorkspace:
    """One validated ordinary-Context aggregate rooted at ``root``."""

    root: Context
    manifest_memory_uid: str
    manifest: GroundWorkspaceManifest
    goals: Context
    rules: Context
    examples: Context
    contexts: Context
    relations: Context

    def __post_init__(self) -> None:
        lane_contexts = self.lane_contexts
        expected_names = ground_workspace_context_names(self.root.name)
        actual_names = (self.root.name, *(context.name for context in lane_contexts))
        if actual_names != expected_names:
            raise GroundWorkspaceError(
                "Ground workspace Context names do not match its root."
            )
        identities = (self.root.uid, *(context.uid for context in lane_contexts))
        if len(set(identities)) != len(identities):
            raise GroundWorkspaceError(
                "Ground workspace Contexts require distinct identities."
            )
        if self.manifest.workspace_uid != self.root.uid:
            raise GroundWorkspaceError(
                "Ground workspace manifest does not identify its root Context."
            )
        item = self.root.memories.get(self.manifest_memory_uid)
        if not isinstance(item, Memory):
            raise GroundWorkspaceError(
                "Ground workspace root is missing its manifest Memory."
            )
        if GroundWorkspaceManifest.from_memory(item) != self.manifest:
            raise GroundWorkspaceError(
                "Ground workspace manifest projection is inconsistent."
            )
        manifest_count = sum(
            is_ground_workspace_manifest_memory(candidate)
            for candidate in self.root.iter_items()
        )
        if manifest_count != 1:
            raise GroundWorkspaceError(
                "Ground workspace root must contain exactly one manifest Memory."
            )

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def uid(self) -> str:
        return self.root.uid

    @property
    def lane_contexts(self) -> tuple[Context, ...]:
        return (
            self.goals,
            self.rules,
            self.examples,
            self.contexts,
            self.relations,
        )

    @property
    def all_contexts(self) -> tuple[Context, ...]:
        return (self.root, *self.lane_contexts)

    def lane(self, name: GroundWorkspaceLane) -> Context:
        if name not in GROUND_WORKSPACE_LANES:
            raise GroundWorkspaceError(f"Unknown Ground workspace lane '{name}'.")
        return getattr(self, name)

    def advance_revision(
        self,
        *,
        status: GroundWorkspaceStatus | None = None,
    ) -> "GroundWorkspace":
        """Advance the manifest Memory after one reviewed local command.

        The revision is causal workspace state, so an Undo also advances it
        instead of restoring an older revision number.  The command receipt
        retains the exact lane pre-image separately.
        """

        manifest = replace(
            self.manifest,
            revision=self.manifest.revision + 1,
            status=self.manifest.status if status is None else status,
        )
        self.root.replace(
            Memory(
                uid=self.manifest_memory_uid,
                content=manifest.to_memory_content(),
            )
        )
        return GroundWorkspace(
            root=self.root,
            manifest_memory_uid=self.manifest_memory_uid,
            manifest=manifest,
            goals=self.goals,
            rules=self.rules,
            examples=self.examples,
            contexts=self.contexts,
            relations=self.relations,
        )


def ground_workspace_context_names(root_name: str) -> tuple[str, ...]:
    """Return the exact root-first physical Context names for one workspace."""

    if not isinstance(root_name, str) or not root_name.strip():
        raise GroundWorkspaceError("Ground workspace name is required.")
    return (
        root_name,
        *(f"{root_name}/{lane}" for lane in GROUND_WORKSPACE_LANES),
    )


def is_ground_workspace_manifest_memory(value: object) -> bool:
    """Return whether one ordinary Memory is an exact workspace manifest."""

    if not isinstance(value, Memory):
        return False
    try:
        GroundWorkspaceManifest.from_memory(value)
    except GroundWorkspaceError:
        return False
    return True


def create_ground_workspace_records(
    root_name: str,
    *,
    goal: str = "",
) -> GroundWorkspace:
    """Build one unsaved physical workspace without Store or UI effects."""

    if not isinstance(goal, str):
        raise GroundWorkspaceError("Ground Goal must be text.")
    root = Context(uid=str(uuid.uuid4()), name=root_name)
    manifest = GroundWorkspaceManifest(workspace_uid=root.uid)
    manifest_memory = Memory(
        uid=str(uuid.uuid4()),
        content=manifest.to_memory_content(),
    )
    root.add(manifest_memory)
    lane_by_name = {
        lane: Context(uid=str(uuid.uuid4()), name=f"{root_name}/{lane}")
        for lane in GROUND_WORKSPACE_LANES
    }
    if goal:
        lane_by_name["goals"].add(goal)
    return GroundWorkspace(
        root=root,
        manifest_memory_uid=manifest_memory.uid,
        manifest=manifest,
        goals=lane_by_name["goals"],
        rules=lane_by_name["rules"],
        examples=lane_by_name["examples"],
        contexts=lane_by_name["contexts"],
        relations=lane_by_name["relations"],
    )


def load_ground_workspace_records(
    root: Context,
    *,
    goals: Context,
    rules: Context,
    examples: Context,
    contexts: Context,
    relations: Context,
) -> GroundWorkspace:
    """Validate already loaded ordinary Context records as one workspace."""

    manifests = tuple(
        item
        for item in root.iter_items()
        if is_ground_workspace_manifest_memory(item)
    )
    if len(manifests) != 1:
        raise GroundWorkspaceError(
            "Ground workspace root must contain exactly one manifest Memory."
        )
    manifest_memory = manifests[0]
    assert isinstance(manifest_memory, Memory)
    return GroundWorkspace(
        root=root,
        manifest_memory_uid=manifest_memory.uid,
        manifest=GroundWorkspaceManifest.from_memory(manifest_memory),
        goals=goals,
        rules=rules,
        examples=examples,
        contexts=contexts,
        relations=relations,
    )


__all__ = [
    "GROUND_WORKSPACE_LANES",
    "GROUND_WORKSPACE_MANIFEST_KIND",
    "GROUND_WORKSPACE_SCHEMA_VERSION",
    "GroundWorkspace",
    "GroundWorkspaceError",
    "GroundWorkspaceLane",
    "GroundWorkspaceManifest",
    "GroundWorkspaceStatus",
    "create_ground_workspace_records",
    "ground_workspace_context_names",
    "is_ground_workspace_manifest_memory",
    "load_ground_workspace_records",
]
