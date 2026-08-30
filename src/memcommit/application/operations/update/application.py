"""Application boundary for applying exact local Update plans."""

from __future__ import annotations

from memcommit.application.operations.update.materialization import (
    materialize_update_plan,
)
from memcommit.application.operations.update.model.plan import UpdatePlan
from memcommit.application.operations.update.model.result import UpdateResult
from memcommit.core.context import Context


def apply_update(plan: UpdatePlan, target: Context) -> UpdateResult:
    """Apply one exact plan to a detached working Target.

    This operation never opens a terminal review and never persists its
    result. The caller owns the enclosing semantic session and decides when a
    reviewed working Target is ready for its durable publication boundary.
    """

    return materialize_update_plan(plan, target)


__all__ = ["apply_update"]
