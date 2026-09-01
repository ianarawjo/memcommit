"""Authorize resolved Context participants through one operation boundary."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from memcommit.application.context_access.access import (
    ContextAccess,
    revalidate_context_access,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.application.operations.profile.config import ProfileRegistry


def _require_granted_permissions(
    access: ContextAccess,
    required_permissions: tuple[str, ...],
) -> None:
    if access.view is None:
        return
    missing = sorted(set(required_permissions) - set(access.view.grant.permissions))
    if missing:
        raise ProfileError(
            f"Grant {access.view.grant.uid[:8]} does not allow "
            + " + ".join(missing)
            + f" access to {access.access_name!r}."
        )


@contextmanager
def authorized_context_operation(
    checks: tuple[tuple[ContextAccess, tuple[str, ...]], ...],
) -> Iterator[ProfileRegistry | None]:
    """Freeze all granted participants in one operation through its writes."""

    granted = tuple(check for check in checks if check[0].is_granted)
    if not granted:
        yield None
        return
    for access, permissions in granted:
        _require_granted_permissions(access, permissions)
    # Grant changes and Profile switching use this same registry lock. Holding
    # it across the authority-store save closes the revoke-after-check race.
    with authority_grant_snapshot_lock() as registry:
        for access, permissions in granted:
            revalidate_context_access(access, registry=registry)
            _require_granted_permissions(access, permissions)
        # Some retained graph operations also bind nested override membership.
        # Exposing the already-held immutable registry snapshot lets them check
        # that evidence without taking a second, potentially deadlocking lock.
        yield registry


@contextmanager
def authorized_context_mutation(
    access: ContextAccess,
    *,
    required_permissions: tuple[str, ...] = (),
) -> Iterator[None]:
    """Keep every required grant permission valid through authority save."""

    with authorized_context_operation(((access, required_permissions),)):
        yield


__all__ = ["authorized_context_mutation", "authorized_context_operation"]
