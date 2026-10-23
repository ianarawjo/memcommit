"""Detached results from applying one exact Update plan."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.models.context import Context


@dataclass(frozen=True, slots=True)
class UpdatedContext:
    """One Context with applied changes and its detached post-update record."""

    context_uid: str
    context_name: str
    post_image: Context


@dataclass(frozen=True, slots=True)
class UpdateResult:
    """Detached post-images produced without persistence or presentation."""

    plan_uid: str
    target_uid: str
    target_name: str
    updated_contexts: tuple[UpdatedContext, ...]

    @property
    def post_images(self) -> tuple[Context, ...]:
        """Return detached Context records in canonical save order."""

        return tuple(
            updated_context.post_image for updated_context in self.updated_contexts
        )

    def post_image_for(self, context_uid: str) -> Context | None:
        """Return one updated Context's post-image without assuming root order."""

        for updated_context in self.updated_contexts:
            if updated_context.context_uid == context_uid:
                return updated_context.post_image
        return None


__all__ = ["UpdatedContext", "UpdateResult"]
