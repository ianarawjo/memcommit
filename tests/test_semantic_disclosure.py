"""Shared provider-disclosure authority boundary."""

from __future__ import annotations

import uuid

import pytest

import memcommit.application.operations.summarize.runtime as summarize_runtime
from memcommit.context import Context, GrantedContextLink, Memory
from memcommit.application.authority.access import ContextAccess
from memcommit.core.context_targeting.search import load_readable_search_roots
from memcommit.application.operations.search.application import FindSearchRequest
from memcommit.application.operations.search.runtime import execute_find_search
from memcommit.application.operations.meld.model import MeldError, MeldFrame
from memcommit.application.semantic.disclosure import (
    SemanticDisclosureError,
    require_semantic_disclosure_authority,
)
from memcommit.application.operations.sever.application import SeverApplicationError
from memcommit.application.operations.sever.runtime import capture_sever_binding
from memcommit.application.operations.summarize.model import SummarizeError, collect_summary_scope


def _uid() -> str:
    return str(uuid.uuid4())


def _granted_context(name: str = "public/advisor") -> Context:
    context = Context(uid=_uid(), name=name)
    context.add(Memory(uid=_uid(), content="Granted contributor."))
    context._granted_link = GrantedContextLink(
        context_uid=context.uid,
        public_name=context.name,
        authority_context_name="authority/advisor",
        authority_profile_uid=_uid(),
        grantee_profile_uid=_uid(),
        attachment_context_uid=_uid(),
        attachment_context_name="workspace",
        grant_uid=_uid(),
        grant_revision_at_creation=1,
        resource_uid=context.uid,
        resource_name="authority/advisor",
    )
    return context


def test_direct_granted_root_is_distinct_from_nested_local_owner_route() -> None:
    granted = _granted_context()
    require_semantic_disclosure_authority((granted,), operation="Test")

    local = Context(uid=_uid(), name="workspace")
    local.add(granted)
    with pytest.raises(
        SemanticDisclosureError,
        match="granted Context Embed.*not provider disclosure",
    ):
        require_semantic_disclosure_authority((local,), operation="Test")

    with pytest.raises(
        SemanticDisclosureError,
        match="granted Context Embed.*not provider disclosure",
    ):
        require_semantic_disclosure_authority(
            (local, granted),
            operation="Test",
        )


def test_owner_aware_recursive_meld_rejects_nested_granted_context() -> None:
    local = Context(uid=_uid(), name="workspace")
    local.add(_granted_context())

    with pytest.raises(
        MeldError,
        match="granted Context Embed.*not provider disclosure",
    ):
        MeldFrame.from_context(
            local,
            role="INCOMING",
            owner_aware=True,
            include_descendants=True,
        )


def test_recursive_summarize_rejects_nested_granted_context() -> None:
    local = Context(uid=_uid(), name="workspace")
    granted = _granted_context("workspace/advisor")
    local.add(granted)

    with pytest.raises(
        SummarizeError,
        match="granted Context Embed.*not provider disclosure",
    ):
        collect_summary_scope(
            (local, granted),
            root_context_uid=local.uid,
            root_context_name=local.name,
            include_descendants=False,
            follow_embeds=True,
        )


def test_recursive_sever_rejects_nested_granted_context() -> None:
    local = Context(uid=_uid(), name="workspace")
    granted = _granted_context("workspace/advisor")
    local.add(granted)

    class StoreStub:
        def load(self, name: str) -> Context:
            return {local.name: local, granted.name: granted}[name]

        def load_direct(self, name: str) -> Context:
            return {local.name: local, granted.name: granted}[name]

        def list_context_names(self) -> list[str]:
            return [local.name, granted.name]

    access = ContextAccess(
        store=StoreStub(),  # type: ignore[arg-type]
        context_name=local.name,
        display_name=local.name,
        attachment_name=None,
        permission="READ",
    )

    with pytest.raises(
        SeverApplicationError,
        match="granted Context Embed.*not provider disclosure",
    ):
        capture_sever_binding(access, include_descendants=True)


def test_semantic_search_loading_omits_markerless_attached_read_projection() -> None:
    local = Context(uid=_uid(), name="workspace")
    attached = Context(uid=_uid(), name="public/advisor")
    attached.add(Memory(uid=_uid(), content="Markerless remote secret."))

    class CatalogStub:
        def list_context_names(self) -> list[str]:
            return [local.name]

        def context_exists(self, name: str) -> bool:
            return name == local.name

        def load_direct(self, name: str) -> Context:
            assert name == local.name
            return local

        def load_without_attached_reads(self, name: str) -> Context:
            assert name == local.name
            return local

        def load(self, name: str) -> Context:
            assert name == local.name
            projected = Context(uid=local.uid, name=local.name)
            projected.add(attached)
            return projected

    browsing = load_readable_search_roots(
        CatalogStub(),  # type: ignore[arg-type]
        (local.name,),
        include_descendants=False,
        follow_embeds=True,
    )
    semantic = load_readable_search_roots(
        CatalogStub(),  # type: ignore[arg-type]
        (local.name,),
        include_descendants=False,
        follow_embeds=True,
        include_attached_reads=False,
    )

    assert tuple(browsing[0].iter_items()) == (attached,)
    assert tuple(semantic[0].iter_items()) == ()


def test_summarize_loading_omits_markerless_attached_read_projection(
    monkeypatch,
) -> None:
    local = Context(uid=_uid(), name="workspace")

    class StoreStub:
        pass

    active_store = StoreStub()
    access = ContextAccess(
        store=active_store,  # type: ignore[arg-type]
        context_name=local.name,
        display_name=local.name,
        attachment_name=None,
        permission="READ",
    )

    class CatalogStub:
        def list_context_names(self) -> list[str]:
            return [local.name]

        def load_without_attached_reads(self, name: str) -> Context:
            assert name == local.name
            return local

        def load_direct(self, name: str) -> Context:
            assert name == local.name
            return local

        def load(self, name: str) -> Context:
            raise AssertionError("Summarize opened markerless attached READ content")

        def access_for(self, name: str) -> ContextAccess:
            assert name == local.name
            return access

    monkeypatch.setattr(
        summarize_runtime,
        "ReadableContextCatalog",
        lambda *_args, **_kwargs: CatalogStub(),
    )

    loaded = summarize_runtime._load_frame(
        active_store,  # type: ignore[arg-type]
        access,
        include_descendants=False,
        follow_embeds=True,
    )

    assert loaded.frame.sources == ()


def test_search_missing_attached_read_free_loader_fails_before_provider() -> None:
    local = Context(uid=_uid(), name="workspace")

    class StoreStub:
        pass

    active_store = StoreStub()
    access = ContextAccess(
        store=active_store,  # type: ignore[arg-type]
        context_name=local.name,
        display_name=local.name,
        attachment_name=None,
        permission="READ",
    )

    class UnsafeCatalog:
        def list_context_names(self) -> list[str]:
            return [local.name]

        def context_exists(self, name: str) -> bool:
            return name == local.name

        def load_direct(self, name: str) -> Context:
            assert name == local.name
            return local

        def load(self, name: str) -> Context:
            assert name == local.name
            return local

        def access_for(self, name: str) -> ContextAccess:
            assert name == local.name
            return access

    provider_connections = 0

    def provider_factory():
        nonlocal provider_connections
        provider_connections += 1
        raise AssertionError("Search connected a provider before safe loading")

    with pytest.raises(
        RuntimeError,
        match="requires an attached-READ-free loader",
    ):
        execute_find_search(
            FindSearchRequest(
                query="secret",
                target_names=(local.name,),
                include_descendants=False,
                follow_embeds=True,
            ),
            store=active_store,  # type: ignore[arg-type]
            catalog=UnsafeCatalog(),  # type: ignore[arg-type]
            provider_factory=provider_factory,
        )

    assert provider_connections == 0
