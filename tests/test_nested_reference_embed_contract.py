"""Nested Reference and Embed composition contracts.

Memory-level pointer wrapping is intentionally closed: a ``MemoryRef`` is a
relationship, not a second directly owned Memory.  Context-level composition
remains open because the containing Context preserves each typed relationship
instead of flattening it into another Memory pointer.
"""

from __future__ import annotations

import pytest

import memcommit.application.ops as ops
from memcommit.context import Context, GrantedMemorySource, Memory, MemoryRef
from memcommit.application.retained_history.context_snapshot import ContextSnapshotRef
from memcommit.application.operations.embed.application import EmbedRequest, MemoryEmbedRequest
from memcommit.application.operations.embed.runtime import MemoryStoreEmbedPort, execute_embed
from memcommit.application.operations.reference.application import ContextReferenceRequest, ReferenceRequest
from memcommit.application.operations.reference.runtime import (
    MemoryStoreReferencePort,
    execute_context_reference,
    execute_reference,
)
from memcommit.persistence.store import MemoryStore


def _visible_contents(context: Context) -> set[str]:
    """Collect readable values from a possibly cyclic hydrated Context graph."""

    found: set[str] = set()
    visited: set[str] = set()

    def visit(current: Context) -> None:
        if current.uid in visited:
            return
        visited.add(current.uid)
        for item in current.iter_items():
            if isinstance(item, Memory):
                found.add(item.content)
            elif isinstance(item, MemoryRef) and item.target is not None:
                found.add(item.target.content)
            elif isinstance(item, Context):
                visit(item)

    visit(context)
    return found


@pytest.mark.parametrize("pointer_kind", ["snapshot", "live"])
def test_memory_pointer_rejects_malformed_grant_provenance(pointer_kind):
    origin = ops.init("origin")
    memory = ops.add(origin, "owned once")
    target = ops.init("target")
    pointer = (
        ops.reference_memory(memory, origin, target)
        if pointer_kind == "snapshot"
        else ops.embed_memory(memory, origin, target)
    )
    record = pointer.to_dict()
    record["grant_source"] = "not-an-authority-binding"

    with pytest.raises(ValueError, match="Grant Source is invalid"):
        MemoryRef.from_dict(record)


def test_malformed_granted_memory_binding_fails_before_live_source_load():
    source = GrantedMemorySource(
        context_uid="authority-context",
        public_name="shared/source",
        authority_context_name="private/source",
        authority_profile_uid="authority-profile",
        grantee_profile_uid="grantee-profile",
        attachment_context_uid="attachment-context",
        attachment_context_name="workspace",
        grant_uid="grant",
        grant_revision_at_creation=1,
        resource_uid="resource",
        resource_name="private/source",
        memory_uid="authority-memory",
    )
    record = {
        "type": "granted_memory_ref",
        "uid": "relationship",
        "target_context": {
            "uid": source.context_uid,
            "name": source.public_name,
        },
        "target_memory_uid": "tampered-memory",
        "grant_source": source.to_dict(),
    }
    loads: list[GrantedMemorySource] = []

    with pytest.raises(ValueError, match="does not match its relationship target"):
        Context.from_dict(
            {
                "uid": "target-context",
                "name": "target",
                "memories": {record["uid"]: record},
            },
            granted_memory_loader=lambda binding: loads.append(binding),
        )

    assert loads == []


@pytest.mark.parametrize("pointer_kind", ["snapshot", "live"])
def test_memory_pointer_cannot_be_referenced_or_embedded_again(
    isolated_store,
    pointer_kind,
):
    store = MemoryStore()
    origin = ops.init("origin")
    memory = ops.add(origin, "owned once")
    middle = ops.init("middle")
    pointer = (
        ops.reference_memory(memory, origin, middle)
        if pointer_kind == "snapshot"
        else ops.embed_memory(memory, origin, middle)
    )
    target = ops.init("target")
    for context in (origin, middle, target):
        store.save(context)

    before = store.load_direct(target.name).to_dict()
    reference_port = MemoryStoreReferencePort.capture(store)
    embed_port = MemoryStoreEmbedPort.capture(store)

    with pytest.raises(TypeError, match="not a directly owned Memory"):
        reference_port.freeze(
            ReferenceRequest(pointer.uid, middle.name, target.name)
        )
    with pytest.raises(TypeError, match="not a directly owned Memory"):
        embed_port.freeze_memory(
            MemoryEmbedRequest(pointer.uid, middle.name, target.name)
        )

    assert store.load_direct(target.name).to_dict() == before
    assert store.list_checkpoints(target.name) == []


def test_context_reference_preserves_nested_reference_values(isolated_store):
    store = MemoryStore()
    origin = ops.init("origin")
    memory = ops.add(origin, "retained version")
    first = ops.init("first")
    second = ops.init("second")
    final = ops.init("final")
    for context in (origin, first, second, final):
        store.save(context)

    memory_result = execute_reference(
        ReferenceRequest(memory.uid, origin.name, first.name),
        store=store,
    )
    memory_record = store.load_direct(first.name).memories[
        memory_result.reference_uid
    ].to_dict()
    first_result = execute_context_reference(
        ContextReferenceRequest(first.name, second.name),
        store=store,
    )
    first_record = store.load_direct(second.name).memories[
        first_result.reference_uid
    ].to_dict()
    second_result = execute_context_reference(
        ContextReferenceRequest(second.name, final.name),
        store=store,
    )

    for source_name in (origin.name, first.name, second.name):
        store.delete(source_name)

    outer = store.load(final.name).memories[second_result.reference_uid]
    assert isinstance(outer, ContextSnapshotRef)
    inner_context = outer.memories[first_result.reference_uid]
    assert isinstance(inner_context, ContextSnapshotRef)
    assert inner_context.to_dict() == first_record
    inner_memory = inner_context.memories[memory_result.reference_uid]
    assert isinstance(inner_memory, MemoryRef)
    assert inner_memory.is_snapshot
    assert inner_memory.to_dict() == memory_record
    assert _visible_contents(outer) == {"retained version"}


def test_two_hop_context_embed_keeps_inner_snapshot_fixed_and_contexts_live(
    isolated_store,
):
    store = MemoryStore()
    origin = ops.init("origin")
    memory = ops.add(origin, "snapshot version")
    leaf = ops.init("leaf")
    middle = ops.init("middle")
    outer = ops.init("outer")
    for context in (origin, leaf, middle, outer):
        store.save(context)

    execute_reference(
        ReferenceRequest(memory.uid, origin.name, leaf.name),
        store=store,
    )
    execute_embed(EmbedRequest(leaf.name, middle.name), store=store)
    execute_embed(EmbedRequest(middle.name, outer.name), store=store)

    changed_origin = store.load_for_update(origin.name)
    changed_origin.replace(Memory(uid=memory.uid, content="changed origin"))
    store.save(changed_origin)
    changed_leaf = store.load_for_update(leaf.name)
    ops.add(changed_leaf, "added after both embeds")
    store.save(changed_leaf)

    reloaded = store.load(outer.name)
    assert _visible_contents(reloaded) == {
        "snapshot version",
        "added after both embeds",
    }
    assert "changed origin" not in _visible_contents(reloaded)
    outer_child = next(iter(store.load_direct(outer.name).iter_items()))
    middle_child = next(iter(store.load_direct(middle.name).iter_items()))
    assert isinstance(outer_child, Context) and outer_child.name == middle.name
    assert isinstance(middle_child, Context) and middle_child.name == leaf.name


def test_recursive_reference_freezes_each_context_in_two_hop_embed_once(
    isolated_store,
):
    store = MemoryStore()
    leaf = ops.init("leaf")
    ops.add(leaf, "leaf fact")
    middle = ops.init("middle")
    ops.add(middle, "middle fact")
    outer = ops.init("outer")
    ops.add(outer, "outer fact")
    target = ops.init("target")
    for context in (leaf, middle, outer, target):
        store.save(context)
    execute_embed(EmbedRequest(leaf.name, middle.name), store=store)
    execute_embed(EmbedRequest(middle.name, outer.name), store=store)

    result = execute_context_reference(
        ContextReferenceRequest(
            outer.name,
            target.name,
            include_descendants=True,
            follow_embeds=True,
        ),
        store=store,
    )
    for source_name in (leaf.name, middle.name, outer.name):
        store.delete(source_name)

    snapshot = store.load(target.name).memories[result.reference_uid]
    assert isinstance(snapshot, ContextSnapshotRef)
    retained_names = [
        record["name"] for record in snapshot.snapshot_package["contexts"]
    ]
    assert retained_names == [outer.name, middle.name, leaf.name]
    assert result.context_count == 3
    assert _visible_contents(snapshot) == {
        "leaf fact",
        "middle fact",
        "outer fact",
    }


def test_recursive_reference_freezes_an_embed_cycle_once(isolated_store):
    store = MemoryStore()
    first = ops.init("cycle/first")
    ops.add(first, "first fact")
    second = ops.init("cycle/second")
    ops.add(second, "second fact")
    target = ops.init("target")
    for context in (first, second, target):
        store.save(context)
    execute_embed(EmbedRequest(second.name, first.name), store=store)
    execute_embed(EmbedRequest(first.name, second.name), store=store)

    result = execute_context_reference(
        ContextReferenceRequest(
            first.name,
            target.name,
            include_descendants=True,
            follow_embeds=True,
        ),
        store=store,
    )
    for source_name in (first.name, second.name):
        store.delete(source_name)

    snapshot = store.load(target.name).memories[result.reference_uid]
    assert isinstance(snapshot, ContextSnapshotRef)
    retained_names = [
        record["name"] for record in snapshot.snapshot_package["contexts"]
    ]
    assert retained_names == [first.name, second.name]
    assert result.context_count == 2
    assert _visible_contents(snapshot) == {"first fact", "second fact"}
