"""Authorize one resolved Context for an exact ordinary use."""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from memcommit.application.capabilities.authority.context_access import ContextAccess
from memcommit.application.operations.profile.model import ProfileError


class ContextUse(str, Enum):
    """The complete ordinary-use vocabulary for a granted Context."""

    QUERY = "QUERY"
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


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
) -> None:
    """Require one resolved Context to permit every requested ordinary use.

    Local Contexts are owned by the active Profile and therefore need no Grant
    decision. A READ grant can answer a query because it already discloses the
    underlying content; QUERY remains useful as the weaker mediated-only use.
    """

    required = _normalize_context_uses(uses)
    if not access.is_granted:
        return
    assert access.view is not None
    granted = set(access.view.grant.permissions)
    missing = {
        use.value
        for use in required
        if not (
            use.value in granted
            or use is ContextUse.QUERY
            and ContextUse.READ.value in granted
        )
    }
    if missing:
        ordered = [use.value for use in ContextUse if use.value in missing]
        raise ProfileError(
            f"Grant {access.view.grant.uid[:8]} does not allow "
            + " + ".join(ordered).lower()
            + f" access to {access.display_name!r}."
        )


__all__ = ["ContextUse", "authorize_context_use"]
