from types import SimpleNamespace

import pytest

from memcommit.application.authorization import ContextUse, authorize_context_use
from memcommit.application.context_access.access import ContextAccess
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    canonical_grant_permissions,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


def _access(store: MemoryStore, permissions: tuple[str, ...] | None) -> ContextAccess:
    view = (
        None
        if permissions is None
        else SimpleNamespace(
            grant=SimpleNamespace(uid="01234567-rest", permissions=permissions)
        )
    )
    return ContextAccess(
        store=store,
        context_name="authority/source",
        access_name="public/source",
        permission="READ",
        view=view,
    )


def test_context_use_is_the_complete_ordinary_grant_vocabulary():
    assert tuple(use.value for use in ContextUse) == (
        "QUERY",
        "CREATE",
        "READ",
        "UPDATE",
        "DELETE",
    )


def test_read_grant_also_authorizes_query_but_query_does_not_disclose_content(
    isolated_store,
):
    store = MemoryStore()
    authorization = authorize_context_use(
        _access(store, ("READ",)),
        ContextUse.QUERY,
    )

    assert authorization.allowed == frozenset(
        {ContextUse.READ, ContextUse.QUERY}
    )
    assert authorization.permits(ContextUse.READ)
    assert not authorization.permits(ContextUse.UPDATE)

    with pytest.raises(ProfileError, match="does not allow read access"):
        authorize_context_use(_access(store, ("QUERY",)), ContextUse.READ)


def test_mutation_uses_are_checked_exactly_and_local_contexts_need_no_grant(
    isolated_store,
):
    store = MemoryStore()
    local = authorize_context_use(
        _access(store, None),
        tuple(ContextUse),
    )
    assert local.allowed == frozenset(ContextUse)

    granted = _access(store, ("READ", "CREATE", "UPDATE"))
    authorization = authorize_context_use(
        granted,
        (ContextUse.READ, ContextUse.CREATE, ContextUse.UPDATE),
    )
    assert authorization.allowed == frozenset(
        {
            ContextUse.QUERY,
            ContextUse.CREATE,
            ContextUse.READ,
            ContextUse.UPDATE,
        }
    )
    with pytest.raises(ProfileError, match="does not allow delete access"):
        authorize_context_use(granted, ContextUse.DELETE)


def test_retired_permissions_are_migration_only():
    with pytest.raises(ProfileConfigError, match="Unsupported grant permission"):
        canonical_grant_permissions(("READ", "DERIVE"))

    assert canonical_grant_permissions(
        ("READ", "EMBED", "DERIVE", "COMBINE", "SAVE_ANALYSIS"),
        allow_legacy=True,
    ) == ("READ",)
    assert canonical_grant_permissions(
        ("SESSION_LOG",),
        allow_legacy=True,
    ) == ("QUERY",)
