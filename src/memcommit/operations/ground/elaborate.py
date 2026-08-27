"""Ground adapter over the operation-independent Elaborate use case."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal, Protocol

from memcommit.operations.elaborate.model import (
    ElaborateError,
    ElaborateProvider,
    ElaborateTargetContext,
    ElaborateTargetContextItem,
)
from memcommit.operations.elaborate.application import ElaborateRequest, ElaborateResult
from memcommit.operations.elaborate.runtime import execute_elaborate
from memcommit.operations.elaborate.target_context import (
    FrozenElaborateTargetContext,
    GRANTED_ELABORATE_ADD_PERMISSIONS,
    authorized_frozen_elaborate_target,
    freeze_elaborate_target_context,
)
from memcommit.operations.ground.model import GroundSession, is_bound_ground_schema
from memcommit.operations.ground.workspace_model import GroundWorkspace
from memcommit.operations.ground.workspace_runtime import (
    execute_ground_workspace_memories_adoption,
    ground_workspace_exists,
    load_ground_workspace,
)
from memcommit.operations.ground.workspace_application import (
    AdoptGroundWorkspaceMemoriesRequest,
    AdoptGroundWorkspaceMemoriesResult,
)
from memcommit.operations.ground.workspace_projection import (
    GroundWorkspaceProjectionError,
    project_ordinary_memories,
)
from memcommit.semantic.goal_focus_runtime import freeze_goal_focus_context
from memcommit.operations.add.semantic_runtime import freeze_semantic_add_target
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
    ground_session_record_digest,
)


GroundElaborateDirection = Literal["GOAL_TO_RULES", "RULES_TO_CASES"]


class GroundElaborateProviderFactory(Protocol):
    def __call__(self) -> ElaborateProvider:
        """Construct the same provider used by standalone Elaborate."""


@dataclass(frozen=True)
class FrozenGroundElaborate:
    """One exact Ground revision projected into an Elaborate request."""

    ground_name: str
    ground_uid: str
    ground_revision: int
    ground_digest: str
    direction: GroundElaborateDirection
    request: ElaborateRequest
    target_context: FrozenElaborateTargetContext | ElaborateTargetContext | None = None
    root_digest: str | None = None
    source_bindings: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class GroundElaborateResult:
    """Process-local suggestions tied to one unchanged Ground revision."""

    frozen: FrozenGroundElaborate
    elaborate: ElaborateResult


def _request_from_ground(
    session: GroundSession,
    *,
    direction: GroundElaborateDirection,
    number: int | None = None,
    strict: bool = False,
) -> ElaborateRequest:
    if not is_bound_ground_schema(session.schema_version):
        raise ElaborateError("Ground Elaborate requires a bound Ground.")
    if session.status != "OPEN":
        raise ElaborateError("Ground Elaborate requires an open Ground.")
    if direction == "GOAL_TO_RULES":
        return ElaborateRequest(goal=session.goal, number=number, strict=strict)
    if direction != "RULES_TO_CASES":
        raise ElaborateError("Ground Elaborate direction is invalid.")
    active_rules = tuple(
        item.content
        for item in session.items
        if item.kind == "RULE" and item.status in {"PROPOSED", "ACCEPTED"}
    )
    if not active_rules:
        raise ElaborateError("The Ground contains no active Rules to elaborate.")
    return ElaborateRequest(rules=active_rules, number=number, strict=strict)


def _legacy_target_context(
    session: GroundSession,
    *,
    direction: GroundElaborateDirection,
) -> ElaborateTargetContext | None:
    """Project only the legacy destination lane, never the whole Ground."""

    kind = "RULE" if direction == "GOAL_TO_RULES" else "CASE"
    lane = "rules" if kind == "RULE" else "examples"
    target_name = f"ground:{session.contract_name}/{lane}"
    items = tuple(
        item
        for item in session.items
        if item.kind == kind and item.status in {"PROPOSED", "ACCEPTED"}
    )
    if not items:
        return None
    return ElaborateTargetContext(
        context_name=target_name,
        items=tuple(
            ElaborateTargetContextItem(
                alias=f"t{index}",
                kind="MEMORY",
                context_name=target_name,
                memory_uid=item.uid,
                content=item.content,
            )
            for index, item in enumerate(items, 1)
        ),
    )


def freeze_ground_elaborate(
    store: MemoryStore,
    *,
    ground_name: str,
    direction: GroundElaborateDirection,
    number: int | None = None,
    strict: bool = False,
) -> FrozenGroundElaborate:
    """Freeze the exact Ground input before semantic infrastructure opens."""

    if ground_workspace_exists(store, ground_name):
        workspace = load_ground_workspace(store, ground_name)
        request, digest = _request_from_ground_workspace(
            workspace,
            direction=direction,
            number=number,
            strict=strict,
        )
        target_lane = (
            workspace.rules if direction == "GOAL_TO_RULES" else workspace.examples
        )
        target_context = freeze_elaborate_target_context(
            store,
            target=freeze_semantic_add_target(store, target_lane.name),
        )
        source_lane = (
            workspace.goals if direction == "GOAL_TO_RULES" else workspace.rules
        )
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
        return FrozenGroundElaborate(
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

    session = store.load_ground_session(ground_name)
    if session is None:
        raise ElaborateError(f"Ground '{ground_name}' was not found.")
    request = _request_from_ground(
        session,
        direction=direction,
        number=number,
        strict=strict,
    )
    return FrozenGroundElaborate(
        ground_name=session.contract_name,
        ground_uid=session.uid,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        direction=direction,
        request=request,
        target_context=_legacy_target_context(session, direction=direction),
    )


def _request_from_ground_workspace(
    workspace: GroundWorkspace,
    *,
    direction: GroundElaborateDirection,
    number: int | None = None,
    strict: bool = False,
) -> tuple[ElaborateRequest, str]:
    try:
        goal_memories = project_ordinary_memories(
            workspace.goals,
            operation="Ground workspace Elaborate",
        )
    except GroundWorkspaceProjectionError as error:
        raise ElaborateError(str(error)) from error
    if len(goal_memories) > 1:
        raise ElaborateError(
            "Ground workspace Elaborate requires zero or one Goal Memory."
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
            raise ElaborateError(
                "Ground workspace Elaborate requires exactly one Goal Memory."
            )
        memories = goal_memories
        request = ElaborateRequest(
            goal=goal_focus.text,
            goal_focus=goal_focus,
            number=number,
            strict=strict,
        )
    elif direction == "RULES_TO_CASES":
        try:
            memories = project_ordinary_memories(
                workspace.rules,
                operation="Ground workspace Elaborate",
            )
        except GroundWorkspaceProjectionError as error:
            raise ElaborateError(str(error)) from error
        if not memories:
            raise ElaborateError(
                "The Ground workspace contains no Rule Memories to elaborate."
            )
        request = ElaborateRequest(
            rules=tuple(item.content for item in memories),
            goal_focus=goal_focus,
            number=number,
            strict=strict,
        )
    else:
        raise ElaborateError("Ground Elaborate direction is invalid.")
    digest = hashlib.sha256(
        json.dumps(
            {
                "workspace_uid": workspace.uid,
                "direction": direction,
                "goal_focus": (
                    None if goal_focus is None else goal_focus.receipt_record()
                ),
                "memories": [
                    {"uid": item.uid, "content": item.content}
                    for item in memories
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return request, digest


def execute_ground_elaborate(
    frozen: FrozenGroundElaborate,
    *,
    store: MemoryStore,
    provider_factory: GroundElaborateProviderFactory,
) -> GroundElaborateResult:
    """Use the standalone application and reject a concurrent Ground revision."""

    if not isinstance(frozen, FrozenGroundElaborate):
        raise TypeError("Ground Elaborate requires a frozen request.")
    if ground_workspace_exists(store, frozen.ground_name):
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
            raise ElaborateError(
                "The consumed Ground workspace Memories changed before "
                "Elaborate began."
            )
        target_context = frozen.target_context
        if not isinstance(target_context, FrozenElaborateTargetContext):
            raise ElaborateError("Ground workspace Elaborate Target is invalid.")
        with authorized_frozen_elaborate_target(store, target_context):
            result = execute_elaborate(
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
            raise ElaborateError(
                "The consumed Ground workspace Memories changed while "
                "Elaborate was running; no proposal was published."
            )
        return GroundElaborateResult(frozen=frozen, elaborate=result)
    before = store.load_ground_session(frozen.ground_name)
    if (
        before is None
        or before.uid != frozen.ground_uid
        or before.revision != frozen.ground_revision
        or ground_session_record_digest(before) != frozen.ground_digest
        or _request_from_ground(
            before,
            direction=frozen.direction,
            number=frozen.request.number,
            strict=frozen.request.strict,
        )
        != frozen.request
    ):
        raise ElaborateError("The Ground changed before Elaborate began.")
    result = execute_elaborate(
        frozen.request,
        provider_factory=provider_factory,
        target_context=(
            frozen.target_context
            if isinstance(frozen.target_context, ElaborateTargetContext)
            else None
        ),
    )
    after = store.load_ground_session(frozen.ground_name)
    if (
        after is None
        or after.uid != frozen.ground_uid
        or after.revision != frozen.ground_revision
        or ground_session_record_digest(after) != frozen.ground_digest
    ):
        raise ElaborateError(
            "The Ground changed while Elaborate was running; no proposal was published."
        )
    return GroundElaborateResult(frozen=frozen, elaborate=result)


def apply_ground_elaborate_result(
    result: GroundElaborateResult,
    *,
    store: MemoryStore,
) -> AdoptGroundWorkspaceMemoriesResult:
    """Explicitly adopt one unchanged physical-Ground Elaborate proposal."""

    if not isinstance(result, GroundElaborateResult):
        raise TypeError("Ground Elaborate adoption requires a result.")
    frozen = result.frozen
    target_context = frozen.target_context
    if not isinstance(target_context, FrozenElaborateTargetContext):
        raise ElaborateError(
            "Elaborate adoption requires a physical Ground workspace result."
        )
    current = freeze_ground_elaborate(
        store,
        ground_name=frozen.ground_name,
        direction=frozen.direction,
        number=frozen.request.number,
        strict=frozen.request.strict,
    )
    if current != frozen:
        raise ElaborateError(
            "The Ground workspace changed after the Elaborate proposal was reviewed."
        )
    analysis = result.elaborate.analysis
    contents = (
        tuple(item.content for item in analysis.rules)
        if frozen.direction == "GOAL_TO_RULES"
        else tuple(item.proposition for item in analysis.cases)
    )
    lane: Literal["rules", "examples"] = (
        "rules" if frozen.direction == "GOAL_TO_RULES" else "examples"
    )
    assert frozen.root_digest is not None
    with authorized_frozen_elaborate_target(
        store,
        target_context,
        revalidate_after=False,
        required_granted_permissions=GRANTED_ELABORATE_ADD_PERMISSIONS,
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
                source_operation="elaborate",
                analysis_digest=analysis.digest,
                source_bindings=frozen.source_bindings,
            ),
            store=store,
        )


__all__ = [
    "FrozenGroundElaborate",
    "GroundElaborateDirection",
    "GroundElaborateResult",
    "apply_ground_elaborate_result",
    "execute_ground_elaborate",
    "freeze_ground_elaborate",
]
