"""Typed content evidence for Compare Embeds and References."""

from __future__ import annotations

import hashlib
import uuid

import pytest

from memcommit.application.operations.compare.ledger.model import ComparisonError, ComparisonFrame, ComparisonInput
from memcommit.context import (
    Context,
    GrantedContextLink,
    GrantedMemorySource,
    Memory,
    MemoryRef,
    QueryContextRef,
)


def _uid() -> str:
    return str(uuid.uuid4())


def _peer(name: str = "peer") -> Context:
    context = Context(uid=_uid(), name=name)
    context.add(Memory(uid=_uid(), content="Peer claim."))
    return context


def test_live_memory_embed_content_is_ordinary_comparison_evidence() -> None:
    owner = Context(uid=_uid(), name="owner")
    source = Memory(uid=_uid(), content="Embedded claim.")
    owner.add(source)
    containing = Context(uid=_uid(), name="containing")
    embed = MemoryRef(
        uid=_uid(),
        target_context_uid=owner.uid,
        target_context_name=owner.name,
        target_memory_uid=source.uid,
        target=source,
    )
    containing.add(embed)

    comparison = ComparisonInput.from_contexts(containing, _peer())
    evidence = comparison.frames[0].memories[0]

    assert evidence.uid == embed.uid
    assert evidence.content == source.content
    assert evidence.source is not None
    assert evidence.source.source_form == "LIVE_MEMORY_EMBED"
    assert evidence.source.owner_context_uid == owner.uid
    assert evidence.source.owner_context_name == owner.name
    assert evidence.source.source_memory_uid == source.uid
    assert evidence.source.placement_path == (embed.uid,)


def test_granted_live_memory_embed_is_not_local_semantic_evidence() -> None:
    owner = Context(uid=_uid(), name="public/owner")
    source = Memory(uid=_uid(), content="Granted live claim.")
    owner.add(source)
    containing = Context(uid=_uid(), name="containing")
    containing.add(
        MemoryRef(
            uid=_uid(),
            target_context_uid=owner.uid,
            target_context_name=owner.name,
            target_memory_uid=source.uid,
            target=source,
            granted_source=GrantedMemorySource(
                context_uid=owner.uid,
                public_name=owner.name,
                authority_context_name="authority/owner",
                authority_profile_uid=_uid(),
                grantee_profile_uid=_uid(),
                attachment_context_uid=_uid(),
                attachment_context_name="workspace",
                grant_uid=_uid(),
                grant_revision_at_creation=1,
                resource_uid=owner.uid,
                resource_name="authority/owner",
                memory_uid=source.uid,
            ),
        )
    )

    with pytest.raises(
        ComparisonError,
        match="EMBED authorizes live reading, not provider disclosure",
    ):
        ComparisonInput.from_contexts(containing, _peer())


def test_memory_snapshot_reference_uses_retained_content_without_live_source() -> None:
    retained = Memory(uid=_uid(), content="Retained claim.")
    containing = Context(uid=_uid(), name="containing")
    reference = MemoryRef(
        uid=_uid(),
        target_context_uid=_uid(),
        target_context_name="deleted/source",
        target_memory_uid=retained.uid,
        target=retained,
        snapshot_content_sha256=hashlib.sha256(
            retained.content.encode("utf-8")
        ).hexdigest(),
    )
    containing.add(reference)

    comparison = ComparisonInput.from_contexts(containing, _peer())
    evidence = comparison.frames[0].memories[0]

    assert evidence.content == retained.content
    assert evidence.source is not None
    assert evidence.source.source_form == "MEMORY_REFERENCE"
    assert evidence.source.owner_context_name == "deleted/source"
    assert evidence.source.source_memory_uid == retained.uid


def test_live_embed_source_change_invalidates_the_frozen_frame() -> None:
    owner_uid = _uid()
    memory_uid = _uid()
    embed_uid = _uid()

    def containing(content: str) -> Context:
        context = Context(uid=containing_uid, name="containing")
        context.add(
            MemoryRef(
                uid=embed_uid,
                target_context_uid=owner_uid,
                target_context_name="owner",
                target_memory_uid=memory_uid,
                target=Memory(uid=memory_uid, content=content),
            )
        )
        return context

    containing_uid = _uid()
    frozen = ComparisonFrame.from_context(containing("Before"), side="REFERENCE")

    assert frozen.matches_context(containing("Before"))
    assert not frozen.matches_context(containing("After"))


def test_live_embed_retarget_with_same_content_invalidates_the_frozen_frame() -> None:
    containing_uid = _uid()
    embed_uid = _uid()

    def containing(owner_uid: str, memory_uid: str) -> Context:
        context = Context(uid=containing_uid, name="containing")
        context.add(
            MemoryRef(
                uid=embed_uid,
                target_context_uid=owner_uid,
                target_context_name="owner",
                target_memory_uid=memory_uid,
                target=Memory(uid=memory_uid, content="Same claim."),
            )
        )
        return context

    frozen = ComparisonFrame.from_context(
        containing(_uid(), _uid()),
        side="REFERENCE",
    )

    assert not frozen.matches_context(containing(_uid(), _uid()))


def test_dangling_live_embed_names_the_unavailable_source_without_a_version_label() -> None:
    containing = Context(uid=_uid(), name="containing")
    containing.add(
        MemoryRef(
            uid=_uid(),
            target_context_uid=_uid(),
            target_context_name="missing/source",
            target_memory_uid=_uid(),
            target=None,
        )
    )

    with pytest.raises(ComparisonError) as captured:
        ComparisonInput.from_contexts(containing, _peer())

    message = str(captured.value)
    assert "Memory Embed" in message
    assert "missing/source" in message
    assert "version" not in message.lower()


def test_context_embed_content_is_not_rewritten_with_a_name_prefix() -> None:
    child = Context(uid=_uid(), name="child")
    memory = Memory(uid=_uid(), content="Child claim.")
    child.add(memory)
    containing = Context(uid=_uid(), name="containing")
    containing.add(child)

    comparison = ComparisonInput.from_contexts(containing, _peer())
    evidence = comparison.frames[0].memories[0]

    assert evidence.uid == memory.uid
    assert evidence.content == "Child claim."
    assert evidence.source is not None
    assert evidence.source.source_form == "CONTEXT_GRAPH"
    assert evidence.source.owner_context_name == "child"


def test_granted_live_context_embed_is_not_local_semantic_evidence() -> None:
    granted = Context(uid=_uid(), name="public/shared")
    granted.add(Memory(uid=_uid(), content="Granted live claim."))
    granted._granted_link = GrantedContextLink(
        context_uid=granted.uid,
        public_name=granted.name,
        authority_context_name="authority/shared",
        authority_profile_uid=_uid(),
        grantee_profile_uid=_uid(),
        attachment_context_uid=_uid(),
        attachment_context_name="workspace",
        grant_uid=_uid(),
        grant_revision_at_creation=1,
        resource_uid=granted.uid,
        resource_name="authority/shared",
    )
    containing = Context(uid=_uid(), name="containing")
    containing.add(granted)

    with pytest.raises(
        ComparisonError,
        match="granted Context Embed.*EMBED authorizes live reading",
    ):
        ComparisonInput.from_contexts(containing, _peer())


def test_granted_root_keeps_grant_provenance_outside_the_claim_text() -> None:
    granted = Context(uid=_uid(), name="public/shared")
    granted.add(Memory(uid=_uid(), content="Granted claim."))
    granted._granted_link = GrantedContextLink(
        context_uid=granted.uid,
        public_name=granted.name,
        authority_context_name="authority/shared",
        authority_profile_uid=_uid(),
        grantee_profile_uid=_uid(),
        attachment_context_uid=_uid(),
        attachment_context_name="attachment",
        grant_uid=_uid(),
        grant_revision_at_creation=1,
        resource_uid=_uid(),
        resource_name="resource",
    )

    evidence = ComparisonInput.from_contexts(granted, _peer()).frames[0].memories[0]

    assert evidence.content == "Granted claim."
    assert evidence.source is not None
    assert evidence.source.source_form == "GRANTED_CONTEXT"
    assert evidence.source.owner_context_name == granted.name


def test_query_only_context_is_never_silently_omitted() -> None:
    containing = Context(uid=_uid(), name="containing")
    containing.add(Memory(uid=_uid(), content="Readable claim."))
    containing.add(
        QueryContextRef(
            uid=_uid(),
            name="query/source",
            target_source_uid=_uid(),
            provider="test",
        )
    )

    with pytest.raises(ComparisonError, match="query-only Context 'query/source'"):
        ComparisonInput.from_contexts(containing, _peer())


def test_grant_navigation_query_route_is_not_comparison_content() -> None:
    containing = Context(uid=_uid(), name="public/readable")
    readable = Memory(uid=_uid(), content="Readable claim.")
    containing.add(readable)
    containing.add(
        QueryContextRef(
            uid=_uid(),
            name="public/query-only-child",
            target_source_uid=_uid(),
            provider="authority-grant",
        )
    )

    frame = ComparisonInput.from_contexts(containing, _peer()).frames[0]

    assert [memory.uid for memory in frame.memories] == [readable.uid]
