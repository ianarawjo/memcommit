"""Ground adapter over the operation-independent Elaborate use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.elaborate import ElaborateError, ElaborateProvider
from memcommit.elaborate_application import ElaborateRequest, ElaborateResult
from memcommit.elaborate_runtime import execute_elaborate
from memcommit.ground import GroundSession, is_bound_ground_schema
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
) -> ElaborateRequest:
    if not is_bound_ground_schema(session.schema_version):
        raise ElaborateError("Ground Elaborate requires a bound Ground.")
    if session.status != "OPEN":
        raise ElaborateError("Ground Elaborate requires an open Ground.")
    if direction == "GOAL_TO_RULES":
        return ElaborateRequest(goal=session.goal)
    if direction != "RULES_TO_CASES":
        raise ElaborateError("Ground Elaborate direction is invalid.")
    active_rules = tuple(
        item.content
        for item in session.items
        if item.kind == "RULE" and item.status in {"PROPOSED", "ACCEPTED"}
    )
    if not active_rules:
        raise ElaborateError("The Ground contains no active Rules to elaborate.")
    return ElaborateRequest(rules=active_rules)


def freeze_ground_elaborate(
    store: MemoryStore,
    *,
    ground_name: str,
    direction: GroundElaborateDirection,
) -> FrozenGroundElaborate:
    """Freeze the exact Ground input before semantic infrastructure opens."""

    session = store.load_ground_session(ground_name)
    if session is None:
        raise ElaborateError(f"Ground '{ground_name}' was not found.")
    request = _request_from_ground(session, direction=direction)
    return FrozenGroundElaborate(
        ground_name=session.contract_name,
        ground_uid=session.uid,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        direction=direction,
        request=request,
    )


def execute_ground_elaborate(
    frozen: FrozenGroundElaborate,
    *,
    store: MemoryStore,
    provider_factory: GroundElaborateProviderFactory,
) -> GroundElaborateResult:
    """Use the standalone application and reject a concurrent Ground revision."""

    if not isinstance(frozen, FrozenGroundElaborate):
        raise TypeError("Ground Elaborate requires a frozen request.")
    before = store.load_ground_session(frozen.ground_name)
    if (
        before is None
        or before.uid != frozen.ground_uid
        or before.revision != frozen.ground_revision
        or ground_session_record_digest(before) != frozen.ground_digest
        or _request_from_ground(before, direction=frozen.direction) != frozen.request
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
