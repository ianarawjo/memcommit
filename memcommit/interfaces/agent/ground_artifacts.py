"""Bounded process-local handoff for Ground semantic agent calls."""

from __future__ import annotations

from collections import OrderedDict
from typing import TypeVar

from memcommit.api import (
    DistillProposal,
    ElaborateProposal,
    GroundFitReceiptResult,
    GroundResolutionPlanResult,
)


GroundArtifact = DistillProposal | ElaborateProposal | GroundFitReceiptResult
T = TypeVar("T")


class GroundArtifactRegistry:
    """Retain opaque typed values without serializing hidden application state."""

    def __init__(self, *, capacity: int = 128) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("Ground artifact registry capacity must be positive.")
        self._capacity = capacity
        self._artifacts: OrderedDict[str, GroundArtifact] = OrderedDict()
        self._plans: OrderedDict[str, GroundResolutionPlanResult] = OrderedDict()

    def _retain(self, values: OrderedDict[str, T], key: str, value: T) -> None:
        values[key] = value
        values.move_to_end(key)
        while len(values) > self._capacity:
            values.popitem(last=False)

    def retain_artifact(self, value: GroundArtifact) -> str:
        if isinstance(value, DistillProposal):
            if value._ground_result is None:
                raise ValueError("Only a Ground Distill proposal can be retained.")
            uid = value.analysis_uid
        elif isinstance(value, ElaborateProposal):
            if value._ground_result is None:
                raise ValueError("Only a Ground Elaborate proposal can be retained.")
            uid = value.analysis_uid
        elif isinstance(value, GroundFitReceiptResult):
            uid = value.receipt_uid
        else:
            raise TypeError("Unsupported Ground semantic artifact.")
        self._retain(self._artifacts, uid, value)
        return uid

    def artifact(self, uid: str) -> GroundArtifact | None:
        value = self._artifacts.get(uid)
        if value is not None:
            self._artifacts.move_to_end(uid)
        return value

    def retain_plan(self, value: GroundResolutionPlanResult) -> str:
        if not isinstance(value, GroundResolutionPlanResult):
            raise TypeError("Ground artifact registry requires a public Resolve plan.")
        self._retain(self._plans, value.plan_digest, value)
        return value.plan_digest

    def plan(self, digest: str) -> GroundResolutionPlanResult | None:
        value = self._plans.get(digest)
        if value is not None:
            self._plans.move_to_end(digest)
        return value


__all__ = ["GroundArtifactRegistry"]
