"""Profile-wide Context browser catalog contracts."""

from __future__ import annotations

from types import SimpleNamespace

from memcommit.commands.contexts import _browse_contexts
from memcommit.commands.readable_context_catalog import (
    ProfileContextNavigation,
    freeze_profile_context_navigation,
)
from memcommit.context import Context
from memcommit.context_targeting.catalog import GrantedContextNavigation
from memcommit.store import MemoryStore


class _FakeCatalog:
    def __init__(self) -> None:
        self._granted = {"shared", "shared/child"}

    def list_context_names(self) -> list[str]:
        return ["local", "shared", "shared/child"]

    def access_for(self, name: str):
        return SimpleNamespace(is_granted=name in self._granted)


def test_profile_navigation_merges_readable_and_opaque_switch_rows(monkeypatch):
    catalog = _FakeCatalog()
    grants = GrantedContextNavigation(
        names=("query-only", "shared", "shared/child"),
        annotations={
            "query-only": "QUERY GRANT",
            "shared": "READ GRANT",
            "shared/child": "READ GRANT",
        },
        selectable_names=frozenset({"shared", "shared/child"}),
    )
    monkeypatch.setattr(
        "memcommit.commands.readable_context_catalog."
        "freeze_profile_readable_context_catalog",
        lambda *_args, **_kwargs: catalog,
    )

    navigation = freeze_profile_context_navigation(
        SimpleNamespace(),
        SimpleNamespace(display_name="shared"),
        granted_navigation=grants,
    )

    assert navigation.local_names == ("local",)
    assert navigation.virtual_names == ("query-only", "shared", "shared/child")
    assert navigation.selectable_virtual_names == frozenset(
        {"shared", "shared/child"}
    )
    assert navigation.virtual_annotations["query-only"] == "QUERY GRANT"


def test_contexts_uses_read_granted_current_as_initial_row(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    local = Context("local-uid", "local")
    store.create_context(local)
    granted = GrantedContextNavigation(
        names=("query-only", "shared"),
        annotations={"query-only": "QUERY GRANT", "shared": "READ GRANT"},
        selectable_names=frozenset({"shared"}),
    )
    selected_access = SimpleNamespace(display_name="shared")
    fake_catalog = SimpleNamespace(load=lambda _name: local)
    navigation = ProfileContextNavigation(
        catalog=fake_catalog,
        local_names=("local",),
        virtual_names=("query-only", "shared"),
        selectable_virtual_names=frozenset({"shared"}),
        virtual_annotations=granted.annotations,
    )
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        "memcommit.commands.contexts.freeze_granted_context_navigation",
        lambda _store: granted,
    )
    monkeypatch.setattr(
        "memcommit.commands.contexts.resolve_context_access",
        lambda *_args, **_kwargs: selected_access,
    )
    monkeypatch.setattr(
        "memcommit.commands.contexts.freeze_profile_context_navigation",
        lambda *_args, **_kwargs: navigation,
    )
    monkeypatch.setattr(
        "memcommit.commands.contexts.choose_context",
        lambda names, **kwargs: observed.update(names=names, **kwargs),
    )

    _browse_contexts(store, current="shared", names=["local"])

    assert observed["current"] == "shared"
    assert observed["names"] == ("local",)
    assert observed["virtual_names"] == ("query-only", "shared")
    assert observed["selectable_virtual_names"] == frozenset({"shared"})
