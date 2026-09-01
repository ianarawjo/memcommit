"""Freeze authorized Grant placements for Context namespace navigation."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    default_store_dir,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.application.context_access.granted_view import (
    active_grant_placements,
)
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceDisplayValue,
    SourceTokenRole,
    combine_source_display_tokens,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class GrantedContextNavigation:
    """Grant access names and the subset authorized for ordinary READ browsing."""

    names: tuple[str, ...]
    annotations: dict[str, SourceDisplayValue]
    selectable_names: frozenset[str]

    @property
    def readable_names(self) -> frozenset[str]:
        """Name the authority meaning used by read-only browser callers."""

        return self.selectable_names


_GRANT_NAVIGATION_CAPABILITY_ORDER = (
    "READ",
    "QUERY",
    "EDIT",
    "DELETE",
    "SHARE",
)


def grant_navigation_capability_labels(
    permissions: tuple[str, ...],
) -> tuple[str, ...]:
    """Project exact Grant atoms into the compact Context-navigation lens.

    Context navigation distinguishes the operations a person can recognize at
    a glance. The exact tuple remains on the Grant and remains authoritative;
    SHARE remains visible as a separate delivery capability rather than an
    ordinary Context use.
    """

    permission_set = frozenset(permissions)
    enabled = {
        "READ": "READ" in permission_set,
        "QUERY": "QUERY" in permission_set,
        # CREATE and UPDATE are the two ordinary content-editing capabilities.
        # DELETE remains separate because it has a materially different risk.
        "EDIT": bool(permission_set & {"CREATE", "UPDATE"}),
        "DELETE": "DELETE" in permission_set,
        "SHARE": "SHARE" in permission_set,
    }
    labels = tuple(
        label for label in _GRANT_NAVIGATION_CAPABILITY_ORDER if enabled[label]
    )
    if not labels:
        raise ValueError("Grant navigation requires a visible capability.")
    return labels


def grant_navigation_capability_text(permissions: tuple[str, ...]) -> str:
    """Return the compact, ordered capability cluster for one Grant row."""

    return " + ".join(grant_navigation_capability_labels(permissions))


def grant_navigation_annotation(
    permissions: tuple[str, ...],
) -> tuple[SourceDisplayToken, ...]:
    """Render ownership and compact capability facts for Context navigation."""

    # Keep ownership separate so every Context-tree renderer can place GRANT
    # before the access name instead of hiding it in trailing metadata.
    return (
        SourceDisplayToken("GRANT", SourceTokenRole.OWNERSHIP),
        SourceDisplayToken(
            grant_navigation_capability_text(permissions),
            SourceTokenRole.CAPABILITY,
        ),
    )


def grant_navigation_display_annotation(
    permissions: tuple[str, ...],
) -> SourceDisplayValue:
    """Compose one compact public row without weakening exact authorization."""

    return combine_source_display_tokens(grant_navigation_annotation(permissions))


def freeze_granted_context_navigation(
    store: MemoryStore | None = None,
) -> GrantedContextNavigation:
    """Freeze every active Grant placement without opening authority content.

    READ grants expose their frozen public descendants as ordinary navigation
    rows. Other grants expose only their reviewed public root. In particular,
    a QUERY-only route is visible but never enters ``readable_names``; callers
    must not infer ordinary Context loading from namespace membership.
    """

    try:
        registry = load_profile_registry()
    except ProfileConfigError:
        if (
            store is not None
            and store.store_dir.resolve() != default_store_dir().resolve()
        ):
            return GrantedContextNavigation((), {}, frozenset())
        raise
    active_store = profile_store_dir(registry.active)
    if store is None:
        store = MemoryStore(root=active_store, create=False)
    elif store.store_dir.resolve() != active_store.resolve():
        # An explicitly rooted or isolated store must not inherit the host
        # Profile's virtual names merely because a registry is available.
        return GrantedContextNavigation((), {}, frozenset())

    names: dict[str, SourceDisplayValue] = {}
    readable_names: set[str] = set()
    for placement, grant in active_grant_placements(registry=registry):
        annotation = grant_navigation_display_annotation(
            grant.permissions,
        )
        if "READ" not in grant.permissions:
            # The access route is useful orientation, but its bindings would
            # reveal concealed authority descendants without READ permission.
            names[placement.access_name] = annotation
            readable_names.discard(placement.access_name)
            continue
        for binding in grant.contexts:
            suffix = binding.name[len(grant.resource_name) :]
            access_name = placement.access_name + suffix
            names[access_name] = annotation
            readable_names.add(access_name)

    return GrantedContextNavigation(
        tuple(sorted(names)),
        names,
        frozenset(readable_names),
    )
