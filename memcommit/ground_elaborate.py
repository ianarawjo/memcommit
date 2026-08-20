"""Ground adapter over the operation-independent Elaborate use case."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal, Protocol

from memcommit.elaborate import ElaborateError, ElaborateProvider
from memcommit.elaborate_application import ElaborateRequest, ElaborateResult
from memcommit.elaborate_runtime import execute_elaborate
from memcommit.ground import GroundSession, is_bound_ground_schema
from memcommit.ground_workspace import GroundWorkspace
from memcommit.ground_workspace_runtime import (
    ground_workspace_exists,
    load_ground_workspace,
)
from memcommit.ground_workspace_projection import (
    GroundWorkspaceProjectionError,
    project_ordinary_memories,
)
from memcommit.store import MemoryStore, ground_session_record_digest


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
) -> ElaborateRequest:
    if not is_bound_ground_schema(session.schema_version):
        raise ElaborateError("Ground Elaborate requires a bound Ground.")
    if session.status != "OPEN":
        raise ElaborateError("Ground Elaborate requires an open Ground.")
    if direction == "GOAL_TO_RULES":
        return ElaborateRequest(goal=session.goal, number=number)
    if direction != "RULES_TO_CASES":
        raise ElaborateError("Ground Elaborate direction is invalid.")
    active_rules = tuple(
        item.content
        for item in session.items
        if item.kind == "RULE" and item.status in {"PROPOSED", "ACCEPTED"}
    )
    if not active_rules:
        raise ElaborateError("The Ground contains no active Rules to elaborate.")
    return ElaborateRequest(rules=active_rules, number=number)


def freeze_ground_elaborate(
    store: MemoryStore,
    *,
    ground_name: str,
    direction: GroundElaborateDirection,
    number: int | None = None,
) -> FrozenGroundElaborate:
    """Freeze the exact Ground input before semantic infrastructure opens."""

    if ground_workspace_exists(store, ground_name):
        workspace = load_ground_workspace(store, ground_name)
        request, digest = _request_from_ground_workspace(
            workspace,
            direction=direction,
            number=number,
        )
        return FrozenGroundElaborate(
            ground_name=workspace.name,
            ground_uid=workspace.uid,
            ground_revision=workspace.manifest.revision,
            ground_digest=digest,
            direction=direction,
            request=request,
        )

    session = store.load_ground_session(ground_name)
    if session is None:
        raise ElaborateError(f"Ground '{ground_name}' was not found.")
    request = _request_from_ground(
        session,
        direction=direction,
        number=number,
    )
    return FrozenGroundElaborate(
        ground_name=session.contract_name,
        ground_uid=session.uid,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        direction=direction,
        request=request,
    )


def _request_from_ground_workspace(
    workspace: GroundWorkspace,
    *,
    direction: GroundElaborateDirection,
    number: int | None = None,
) -> tuple[ElaborateRequest, str]:
    if direction == "GOAL_TO_RULES":
        try:
            memories = project_ordinary_memories(
                workspace.goals,
                operation="Ground workspace Elaborate",
            )
        except GroundWorkspaceProjectionError as error:
            raise ElaborateError(str(error)) from error
        if len(memories) != 1:
            raise ElaborateError(
                "Ground workspace Elaborate requires exactly one Goal Memory."
            )
        request = ElaborateRequest(goal=memories[0].content, number=number)
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
            number=number,
        )
    else:
        raise ElaborateError("Ground Elaborate direction is invalid.")
    digest = hashlib.sha256(
        json.dumps(
            {
                "workspace_uid": workspace.uid,
                "direction": direction,
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
        result = execute_elaborate(
            frozen.request,
            provider_factory=provider_factory,
        )
        after_workspace = load_ground_workspace(store, frozen.ground_name)
        after_request, after_digest = _request_from_ground_workspace(
            after_workspace,
            direction=frozen.direction,
            number=frozen.request.number,
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
        )
        != frozen.request
    ):
        raise ElaborateError("The Ground changed before Elaborate began.")
    result = execute_elaborate(
        frozen.request,
        provider_factory=provider_factory,
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


__all__ = [
    "FrozenGroundElaborate",
    "GroundElaborateDirection",
    "GroundElaborateResult",
    "execute_ground_elaborate",
    "freeze_ground_elaborate",
]
