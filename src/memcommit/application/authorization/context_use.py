"""Authorize one resolved Context for an exact ordinary use."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from memcommit.application.capabilities.authority.context_access import ContextAccess
from memcommit.application.operations.profiles.profile.model import ProfileError


class ContextUse(str, Enum):
    """The complete ordinary-use vocabulary for a granted Context."""

    QUERY = "QUERY"
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True)
class ContextUseAuthorization:
    """One resolved Context and all ordinary uses currently authorized for it."""

    access: ContextAccess
    allowed: frozenset[ContextUse]

    def permits(self, use: ContextUse) -> bool:
        """Return whether this exact authorization admits one use."""

        if not isinstance(use, ContextUse):
            raise TypeError("Expected a ContextUse value.")
        return use in self.allowed


def _normalize_context_uses(
    uses: ContextUse | Iterable[ContextUse],
) -> frozenset[ContextUse]:
    if isinstance(uses, ContextUse):
        return frozenset((uses,))
    values = frozenset(uses)
    if not values or any(not isinstance(use, ContextUse) for use in values):
        raise TypeError("Context authorization requires one or more ContextUse values.")
    return values


def authorize_context_use(
    access: ContextAccess,
    uses: ContextUse | Iterable[ContextUse],
) -> ContextUseAuthorization:
    """Require one resolved Context to permit every requested ordinary use.

    Local Contexts are owned by the active Profile and therefore need no Grant
    decision. A READ grant can answer a query because it already discloses the
    underlying content; QUERY remains useful as the weaker mediated-only use.
    """

    if not isinstance(access, ContextAccess):
        raise TypeError("Context authorization requires a ContextAccess value.")
    required = _normalize_context_uses(uses)
    if access.is_granted:
        assert access.view is not None
        granted = set(access.view.grant.permissions)
        allowed = frozenset(
            use
            for use in ContextUse
            if use.value in granted
            or use is ContextUse.QUERY
            and ContextUse.READ.value in granted
        )
    else:
        # A local Context belongs to the active Profile. Returning the same
        # complete vocabulary keeps operation planning independent from where
        # the Context was resolved while preserving the no-Grant fast path.
        allowed = frozenset(ContextUse)
    missing = {
        use.value
        for use in required
        if use not in allowed
    }
    if missing:
        assert access.view is not None
        ordered = [use.value for use in ContextUse if use.value in missing]
        raise ProfileError(
            f"Grant {access.view.grant.uid[:8]} does not allow "
            + " + ".join(ordered).lower()
            + f" access to {access.display_name!r}."
        )
    return ContextUseAuthorization(access=access, allowed=allowed)


__all__ = ["ContextUse", "ContextUseAuthorization", "authorize_context_use"]
