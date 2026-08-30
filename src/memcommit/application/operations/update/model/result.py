"""Detached results from applying one exact Update plan."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.core.context import Context


@dataclass(frozen=True, slots=True)
class AppliedOwner:
    """One affected direct owner and its detached post-update record."""

    owner_context_uid: str
    owner_context_name: str
    post_image: Context


@dataclass(frozen=True, slots=True)
class UpdateResult:
    """Detached post-images produced without persistence or presentation."""

    plan_uid: str
    target_uid: str
    target_name: str
    affected_owners: tuple[AppliedOwner, ...]

    @property
    def session_uid(self) -> str:
        """Compatibility name for callers consuming an UpdateSession plan."""

        return self.plan_uid

    @property
    def post_images(self) -> tuple[Context, ...]:
        """Return detached Context records in canonical save order."""

        return tuple(owner.post_image for owner in self.affected_owners)

    def post_image_for(self, context_uid: str) -> Context | None:
        """Return one affected owner post-image without assuming root order."""

        for owner in self.affected_owners:
            if owner.owner_context_uid == context_uid:
                return owner.post_image
        return None


__all__ = ["AppliedOwner", "UpdateResult"]
