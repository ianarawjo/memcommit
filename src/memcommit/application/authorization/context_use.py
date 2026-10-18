"""Authorize one resolved Context for an exact ordinary use."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from memcommit.application.context_access.access import ContextAccess
from memcommit.application.operations.profile.model import ProfileError


class ContextPermission(str, Enum):
    """Permissions requested or allowed when using a resolved Context."""

    QUERY = "QUERY"
    CREATE = "CREATE"
    READ = "READ"
    EDIT = "EDIT"
    DELETE = "DELETE"


@dataclass(frozen=True)
class ContextUseAuthorization:
    """One resolved Context and all ordinary uses currently authorized for it."""

    access: ContextAccess
    allowed: frozenset[ContextPermission]

    def permits(self, use: ContextPermission) -> bool:
        """Return whether this exact authorization admits one use."""

        if not isinstance(use, ContextPermission):
            raise TypeError("Expected a ContextPermission value.")
        return use in self.allowed


def _normalize_context_uses(
    uses: ContextPermission | Iterable[ContextPermission],
) -> frozenset[ContextPermission]:
    if isinstance(uses, ContextPermission):
        return frozenset((uses,))
    values = frozenset(uses)
    if not values or any(not isinstance(use, ContextPermission) for use in values):
        raise TypeError(
            "Context authorization requires one or more ContextPermission values."
        )
    return values


def check_context_permissions(
    access: ContextAccess,
    uses: ContextPermission | Iterable[ContextPermission],
) -> ContextUseAuthorization:
    """Check that one resolved Context allows every requested permission.

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
            for use in ContextPermission
            if use.value in granted
            or use is ContextPermission.QUERY
            and ContextPermission.READ.value in granted
        )
    else:
        # A local Context belongs to the active Profile. Returning the same
        # complete vocabulary keeps operation planning independent from where
        # the Context was resolved while preserving the no-Grant fast path.
        allowed = frozenset(ContextPermission)
    missing = {
        use.value
        for use in required
        if use not in allowed
    }
    if missing:
        assert access.view is not None
        ordered = [use.value for use in ContextPermission if use.value in missing]
        raise ProfileError(
            f"Grant {access.view.grant.uid[:8]} does not allow "
            + " + ".join(ordered).lower()
            + f" access to {access.access_name!r}."
        )
    return ContextUseAuthorization(access=access, allowed=allowed)


__all__ = ["ContextPermission", "ContextUseAuthorization", "check_context_permissions"]
