"""Freeze readable Contexts as exact Memory Issue detection Sources."""

from __future__ import annotations

from memcommit.application.capabilities.authority.context_access import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.application.capabilities.authority.source_use_policy import (
    authorize_combination,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.workbench import (
    QualityFindSourceFrame,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.core.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.persistence.store import MemoryStore


def freeze_quality_find_source(
    store: MemoryStore,
    context_name: str | None,
    *,
    current_name: str | None,
    all_readable: bool = False,
    registry: ProfileRegistry | None = None,
) -> QualityFindSourceFrame:
    """Resolve authority and freeze one exact or Profile-wide Source frame."""

    if all_readable and context_name is not None:
        raise ValueError(
            "All-readable Memory Issue detection cannot use an explicit Context."
        )
    access = resolve_context_access(
        store,
        None if all_readable else context_name,
        current_name=current_name,
        required_permission="READ",
        registry=registry,
    )
    if all_readable:
        catalog = freeze_profile_readable_context_catalog(
            store,
            access,
            registry=registry,
            include_query_routes=False,
        )
        names = tuple(catalog.list_context_names())
        accesses = tuple(catalog.access_for(name) for name in names)
        # Provider inference derives from every frozen contributor. Grant
        # authority must therefore be checked before any Source is disclosed.
        authorize_combination(accesses)
        return QualityFindSourceFrame.create(
            tuple(catalog.load_direct(name) for name in names),
            context_names=names,
            target_names=(),
            selection_mode="MULTIPLE",
            include_descendants=False,
            profile_selected=True,
        )

    authorize_combination((access,))
    context = (
        GrantedReadStore(access, registry=registry).load_direct(access.display_name)
        if access.is_granted
        else access.store.load_direct(access.context_name)
    )
    return QualityFindSourceFrame.create(
        (context,),
        context_names=(access.display_name,),
        target_names=(access.display_name,),
        selection_mode="SINGLE",
    )


__all__ = ["freeze_quality_find_source"]
