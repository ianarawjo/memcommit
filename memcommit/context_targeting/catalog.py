"""Frozen public Grant rows for Context namespace navigation."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.profile_config import (
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.source_projection.model import context_access_facts
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceDisplayValue,
    SourceTokenRole,
    combine_source_display_tokens,
    source_display_tokens,
)
from memcommit.store import MemoryStore
from memcommit.study_operation_policy import analysis_boundary_label


@dataclass(frozen=True)
class GrantedContextNavigation:
    """Public Grant rows and the subset authorized for ordinary READ browsing."""

    names: tuple[str, ...]
    annotations: dict[str, SourceDisplayValue]
    selectable_names: frozenset[str]

    @property
    def readable_names(self) -> frozenset[str]:
        """Name the authority meaning used by read-only browser callers."""

        return self.selectable_names


def grant_navigation_annotation(
    permissions: tuple[str, ...],
) -> tuple[SourceDisplayToken, ...]:
    """Render Grant authority through the application-wide source grammar."""

    facts = context_access_facts(
        granted=True,
        permission="READ" if "READ" in permissions else "QUERY",
        permissions=permissions,
    )
    return source_display_tokens(facts, include_permissions=True)


def grant_navigation_display_annotation(
    public_name: str,
    permissions: tuple[str, ...],
    *,
    registry: ProfileRegistry | None = None,
) -> SourceDisplayValue:
    """Compose one public row from exact Grant permissions and analysis policy."""

    return combine_source_display_tokens(
        grant_navigation_annotation(permissions),
        SourceDisplayToken(
            "ANALYSIS "
            + analysis_boundary_label(
                public_name,
                granted=True,
                readable="READ" in permissions,
                registry=registry,
            ),
            SourceTokenRole.NOTE,
        ),
    )


def freeze_granted_context_navigation(
    store: MemoryStore | None = None,
) -> GrantedContextNavigation:
    """Freeze every active public Grant row without opening authority content.

    READ grants expose their frozen public descendants as ordinary navigation
    rows. Other grants expose only their reviewed public root. In particular,
    a QUERY-only route is visible but never enters ``readable_names``; callers
    must not infer ordinary Context loading from namespace membership.
    """

    registry = load_profile_registry()
    active_store = profile_store_dir(registry.active)
    if store is None:
        store = MemoryStore(root=active_store, create=False)
    elif store.store_dir.resolve() != active_store.resolve():
        # An explicitly rooted or isolated store must not inherit the host
        # Profile's virtual names merely because a registry is available.
        return GrantedContextNavigation((), {}, frozenset())

    names: dict[str, SourceDisplayValue] = {}
    readable_names: set[str] = set()
    for grant in registry.grants:
        if grant.grantee_profile_uid != registry.active.uid:
            continue
        if not store.context_exists(grant.attachment_context_name):
            continue
        attachment = store.load_direct(grant.attachment_context_name)
        if attachment.uid != grant.attachment_context_uid:
            continue
        annotation = grant_navigation_display_annotation(
            grant.public_name,
            grant.permissions,
            registry=registry,
        )
        if "READ" not in grant.permissions:
            # The public route is useful orientation, but its bindings would
            # reveal concealed authority descendants without READ permission.
            names[grant.public_name] = annotation
            readable_names.discard(grant.public_name)
            continue
        for binding in grant.contexts:
            suffix = binding.name[len(grant.resource_name) :]
            public_name = grant.public_name + suffix
            names[public_name] = annotation
            readable_names.add(public_name)

    return GrantedContextNavigation(
        tuple(sorted(names)),
        names,
        frozenset(readable_names),
    )
