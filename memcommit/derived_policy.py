"""Two-sided authority policy for derived and combined grant outputs."""

from __future__ import annotations

from collections.abc import Iterable

from memcommit.commands.granted_context import ContextAccess
from memcommit.profiles import ProfileError


def _require(access: ContextAccess, permissions: Iterable[str]) -> None:
    if not access.is_granted:
        return
    assert access.view is not None
    missing = sorted(set(permissions) - set(access.view.grant.permissions))
    if missing:
        raise ProfileError(
            f"Grant {access.view.grant.uid[:8]} does not authorize "
            + " + ".join(missing)
            + f" for derived use of {access.display_name!r}."
        )


def same_granted_domain(left: ContextAccess, right: ContextAccess) -> bool:
    """Return whether both endpoints are governed by one exact grant resource."""

    if not left.is_granted or not right.is_granted:
        return False
    assert left.view is not None and right.view is not None
    return (
        left.view.grant.uid == right.view.grant.uid
        and left.view.grant.revision == right.view.grant.revision
        and left.view.authority.uid == right.view.authority.uid
        and left.view.grant.resource_uid == right.view.grant.resource_uid
    )


def authorize_derived_transfer(
    source: ContextAccess,
    target: ContextAccess,
) -> None:
    """Require source export and target acceptance across ownership domains."""

    if source.is_granted:
        required = {"DERIVE"}
        if not same_granted_domain(source, target):
            required.add("EXPORT")
        _require(source, required)
    if target.is_granted and not same_granted_domain(source, target):
        _require(target, {"ACCEPT_DERIVED"})


def authorize_combination(accesses: Iterable[ContextAccess]) -> None:
    """Require every granted contributor to allow cross-domain combination."""

    values = tuple(accesses)
    domains = {
        (
            "grant",
            access.view.grant.uid,
            access.view.grant.resource_uid,
        )
        if access.is_granted and access.view is not None
        else ("local", str(access.store.store_dir), access.context_name)
        for access in values
    }
    for access in values:
        if not access.is_granted:
            continue
        required = {"DERIVE"}
        if len(domains) > 1:
            required.add("COMBINE")
        _require(access, required)


def authorize_analysis_save(accesses: Iterable[ContextAccess]) -> None:
    """Require each authority source to permit a grantee-owned analysis."""

    for access in accesses:
        _require(access, {"DERIVE", "SAVE_ANALYSIS"})
