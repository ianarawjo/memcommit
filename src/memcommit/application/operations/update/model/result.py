"""Detached results from applying one exact Update plan."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.models.context import Context


@dataclass(frozen=True, slots=True)
class UpdateResult:
    """Changed Context copies produced without persistence or presentation."""

    plan_uid: str
    target_uid: str
    target_name: str
    updated_contexts: tuple[Context, ...]

    def get_updated_context(self, context_uid: str) -> Context | None:
        """Find a changed Context by UID; unchanged Contexts have no result."""

        for updated_context in self.updated_contexts:
            if updated_context.uid == context_uid:
                return updated_context
        return None


__all__ = ["UpdateResult"]
