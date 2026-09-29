"""Process-local Resolve input; the composing operation owns durable publication."""

from __future__ import annotations

from memcommit.application.operations.audit.model import QualityAuditSource
from .model import FrozenResolveFrame, ResolveError, ResolveRequest


class DetachedResolvePort:
    def __init__(self, source: QualityAuditSource, *, revision: str):
        self.source = source
        self.revision = revision

    def freeze(self, request: ResolveRequest) -> FrozenResolveFrame:
        if request.context_name != self.source.context_name or request.memory_selectors:
            raise ResolveError("Detached Resolve requires its complete candidate.")
        return FrozenResolveFrame(
            request=request,
            display_name=self.source.context_name,
            source=self.source,
            revision=self.revision,
            actionable_uids=tuple(item.uid for item in self.source.items),
            allowed_effects=request.requested_effects,
        )

    def revalidate(self, frame: FrozenResolveFrame) -> None:
        if frame.source != self.source or frame.revision != self.revision:
            raise ResolveError("Detached Resolve candidate changed.")

    def load_target(self, frame: FrozenResolveFrame):
        self.revalidate(frame)
        return self.source.context()

    def apply_update_plan(self, *args, **kwargs):
        raise ResolveError("The composing operation owns candidate publication.")
