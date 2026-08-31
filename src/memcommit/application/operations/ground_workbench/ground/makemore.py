"""Ground adapter over the operation-independent Makemore use case."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal, Protocol

from memcommit.application.operations.semantic_updates.derive.makemore.model import (
    MakemoreError,
    MakemoreProvider,
)
from memcommit.application.operations.semantic_updates.derive.makemore.application import (
    MakemoreRequest,
    MakemoreResult,
)
from memcommit.application.operations.semantic_updates.derive.makemore.runtime import execute_makemore
from memcommit.application.operations.semantic_updates.derive.makemore.target_context import (
    FrozenMakemoreTargetContext,
    GRANTED_MAKEMORE_ADD_PERMISSIONS,
    authorized_frozen_makemore_target,
    freeze_makemore_target_context,
)
from memcommit.application.operations.ground_workbench.ground.workspace_model import GroundWorkspace
from memcommit.application.operations.ground_workbench.ground.workspace_runtime import (
    execute_ground_workspace_memories_adoption,
    load_ground_workspace,
)
from memcommit.application.operations.ground_workbench.ground.workspace_application import (
    AdoptGroundWorkspaceMemoriesRequest,
    AdoptGroundWorkspaceMemoriesResult,
)
from memcommit.application.operations.ground_workbench.ground.workspace_projection import (
    GroundWorkspaceProjectionError,
    project_ordinary_memories,
)
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    freeze_goal_focus_context,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    freeze_memorization_target,
)
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
)


GroundMakemoreDirection = Literal["GOAL_TO_RULES", "RULES_TO_CASES"]


class GroundMakemoreProviderFactory(Protocol):
    def __call__(self) -> MakemoreProvider:
        """Construct the same provider used by standalone Makemore."""


@dataclass(frozen=True)
class FrozenGroundMakemore:
    """One exact Ground revision projected into a Makemore request."""

    ground_name: str
    ground_uid: str
    ground_revision: int
    ground_digest: str
    direction: GroundMakemoreDirection
    request: MakemoreRequest
    target_context: FrozenMakemoreTargetContext | None = None
    root_digest: str | None = None
    source_bindings: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class GroundMakemoreResult:
    """Process-local suggestions tied to one unchanged Ground revision."""

    frozen: FrozenGroundMakemore
    makemore: MakemoreResult


def freeze_ground_makemore(
    store: MemoryStore,
    *,
    ground_name: str,
    direction: GroundMakemoreDirection,
    number: int | None = None,
    strict: bool = False,
) -> FrozenGroundMakemore:
    """Freeze the exact Ground input before semantic infrastructure opens."""

    try:
        workspace = load_ground_workspace(store, ground_name)
    except FileNotFoundError as error:
        raise MakemoreError(f"Ground {ground_name!r} was not found.") from error
    request, digest = _request_from_ground_workspace(
        workspace,
        direction=direction,
        number=number,
        strict=strict,
    )
    target_lane = (
        workspace.rules if direction == "GOAL_TO_RULES" else workspace.examples
    )
    target_context = freeze_makemore_target_context(
        store,
        target=freeze_memorization_target(store, target_lane.name),
    )
    source_lane = workspace.goals if direction == "GOAL_TO_RULES" else workspace.rules
    source_bindings = [
        (
            source_lane.name,
            source_lane.uid,
            context_record_digest(source_lane),
        ),
        *(
            (item.context_name, item.context_uid, item.context_digest)
            for item in target_context.local_contexts
        ),
    ]
    if request.goal_focus is not None:
        focus = request.goal_focus
        assert focus.context_name is not None
        assert focus.context_uid is not None
        assert focus.context_digest is not None
        source_bindings.append(
            (focus.context_name, focus.context_uid, focus.context_digest)
        )
    return FrozenGroundMakemore(
        ground_name=workspace.name,
        ground_uid=workspace.uid,
        ground_revision=workspace.manifest.revision,
        ground_digest=digest,
        direction=direction,
        request=request,
        target_context=target_context,
        root_digest=context_record_digest(workspace.root),
        source_bindings=tuple(dict.fromkeys(source_bindings)),
    )


def _request_from_ground_workspace(
    workspace: GroundWorkspace,
    *,
    direction: GroundMakemoreDirection,
    number: int | None = None,
    strict: bool = False,
) -> tuple[MakemoreRequest, str]:
    try:
        goal_memories = project_ordinary_memories(
            workspace.goals,
            operation="Ground workspace Makemore",
        )
    except GroundWorkspaceProjectionError as error:
        raise MakemoreError(str(error)) from error
    if len(goal_memories) > 1:
        raise MakemoreError(
            "Ground workspace Makemore requires zero or one Goal Memory."
        )
    goal_focus = (
        freeze_goal_focus_context(
            workspace.goals,
            kind="GROUND",
            require_single=True,
        )
        if goal_memories
        else None
    )
    if direction == "GOAL_TO_RULES":
        if goal_focus is None:
            raise MakemoreError(
                "Ground workspace Makemore requires exactly one Goal Memory."
            )
        memories = goal_memories
        request = MakemoreRequest(
            goal=goal_focus.text,
            goal_focus=goal_focus,
            number=number,
            strict=strict,
        )
    elif direction == "RULES_TO_CASES":
        try:
            memories = project_ordinary_memories(
                workspace.rules,
                operation="Ground workspace Makemore",
            )
        except GroundWorkspaceProjectionError as error:
            raise MakemoreError(str(error)) from error
        if not memories:
            raise MakemoreError(
                "The Ground workspace contains no Rule Memories to expand."
            )
        request = MakemoreRequest(
            rules=tuple(item.content for item in memories),
            goal_focus=goal_focus,
            number=number,
            strict=strict,
        )
    else:
        raise MakemoreError("Ground Makemore direction is invalid.")
    digest = hashlib.sha256(
        json.dumps(
            {
                "workspace_uid": workspace.uid,
                "direction": direction,
                "goal_focus": (
                    None if goal_focus is None else goal_focus.receipt_record()
                ),
                "memories": [
                    {"uid": item.uid, "content": item.content} for item in memories
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return request, digest


def execute_ground_makemore(
    frozen: FrozenGroundMakemore,
    *,
    store: MemoryStore,
    provider_factory: GroundMakemoreProviderFactory,
) -> GroundMakemoreResult:
    """Use the standalone application and reject a concurrent Ground revision."""

    if not isinstance(frozen, FrozenGroundMakemore):
        raise TypeError("Ground Makemore requires a frozen request.")
    before_workspace = load_ground_workspace(store, frozen.ground_name)
    before_request, before_digest = _request_from_ground_workspace(
        before_workspace,
        direction=frozen.direction,
        number=frozen.request.number,
        strict=frozen.request.strict,
    )
    if (
        before_workspace.uid != frozen.ground_uid
        or before_digest != frozen.ground_digest
        or before_request != frozen.request
    ):
        raise MakemoreError(
            "The consumed Ground workspace Memories changed before Makemore began."
        )
    target_context = frozen.target_context
    if not isinstance(target_context, FrozenMakemoreTargetContext):
        raise MakemoreError("Ground workspace Makemore Target is invalid.")
    with authorized_frozen_makemore_target(store, target_context):
        result = execute_makemore(
            frozen.request,
            provider_factory=provider_factory,
            target_context=(
                target_context.semantic if target_context.semantic.items else None
            ),
        )
    after_workspace = load_ground_workspace(store, frozen.ground_name)
    after_request, after_digest = _request_from_ground_workspace(
        after_workspace,
        direction=frozen.direction,
        number=frozen.request.number,
        strict=frozen.request.strict,
    )
    if (
        after_workspace.uid != frozen.ground_uid
        or after_digest != frozen.ground_digest
        or after_request != frozen.request
    ):
        raise MakemoreError(
            "The consumed Ground workspace Memories changed while "
            "Makemore was running; no proposal was published."
        )
    return GroundMakemoreResult(frozen=frozen, makemore=result)


def apply_ground_makemore_result(
    result: GroundMakemoreResult,
    *,
    store: MemoryStore,
) -> AdoptGroundWorkspaceMemoriesResult:
    """Explicitly adopt one unchanged physical-Ground Makemore proposal."""

    if not isinstance(result, GroundMakemoreResult):
        raise TypeError("Ground Makemore adoption requires a result.")
    frozen = result.frozen
    target_context = frozen.target_context
    if not isinstance(target_context, FrozenMakemoreTargetContext):
        raise MakemoreError(
            "Makemore adoption requires a physical Ground workspace result."
        )
    current = freeze_ground_makemore(
        store,
        ground_name=frozen.ground_name,
        direction=frozen.direction,
        number=frozen.request.number,
        strict=frozen.request.strict,
    )
    if current != frozen:
        raise MakemoreError(
            "The Ground workspace changed after the Makemore proposal was reviewed."
        )
    analysis = result.makemore.analysis
    contents = (
        tuple(item.content for item in analysis.rules)
        if frozen.direction == "GOAL_TO_RULES"
        else tuple(item.proposition for item in analysis.cases)
    )
    lane: Literal["rules", "examples"] = (
        "rules" if frozen.direction == "GOAL_TO_RULES" else "examples"
    )
    assert frozen.root_digest is not None
    with authorized_frozen_makemore_target(
        store,
        target_context,
        revalidate_after=False,
        required_granted_permissions=GRANTED_MAKEMORE_ADD_PERMISSIONS,
    ):
        return execute_ground_workspace_memories_adoption(
            AdoptGroundWorkspaceMemoriesRequest(
                workspace_name=frozen.ground_name,
                lane=lane,
                contents=contents,
                expected_workspace_uid=frozen.ground_uid,
                expected_revision=frozen.ground_revision,
                expected_root_digest=frozen.root_digest,
                expected_lane_digest=target_context.target.context_digest,
                source_operation="makemore",
                analysis_digest=analysis.digest,
                source_bindings=frozen.source_bindings,
            ),
            store=store,
        )


__all__ = [
    "FrozenGroundMakemore",
    "GroundMakemoreDirection",
    "GroundMakemoreResult",
    "apply_ground_makemore_result",
    "execute_ground_makemore",
    "freeze_ground_makemore",
]
