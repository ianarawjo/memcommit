"""Profile-wide Context browser catalog contracts."""

from __future__ import annotations

from types import SimpleNamespace

from memcommit.application.context_access.readable_contexts import (
    freeze_profile_context_navigation,
)
from memcommit.application.context_access.granted_context_navigation import (
    GrantedContextNavigation,
)


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
        "memcommit.application.context_access.readable_contexts."
        "freeze_profile_readable_context_catalog",
        lambda *_args, **_kwargs: catalog,
    )

    navigation = freeze_profile_context_navigation(
        SimpleNamespace(),
        SimpleNamespace(access_name="shared"),
        granted_navigation=grants,
    )

    assert navigation.local_names == ("local",)
    assert navigation.virtual_names == ("query-only", "shared", "shared/child")
    assert navigation.selectable_virtual_names == frozenset(
        {"shared", "shared/child"}
    )
    assert navigation.virtual_annotations["query-only"] == "QUERY GRANT"
