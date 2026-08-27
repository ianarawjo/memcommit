"""Shared direct-Memory locator grammar and local owner resolution."""

import pytest

import memcommit.application.ops as ops
from memcommit.context import Memory, MemoryRef, QueryContextRef
from memcommit.core.context_targeting.loading import (
    resolve_local_direct_item_locator,
    resolve_local_context_memory_target,
    resolve_local_direct_memory_locator,
)
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectMemoryLocator,
    DirectMemoryTarget,
    ExistingContextOperand,
)
from memcommit.core.context_targeting.resolution import (
    is_direct_memory_locator_operand,
    parse_auto_typed_context_memory_operand,
    parse_direct_memory_locator,
)
from memcommit.store import MemoryStore


def test_direct_memory_locator_parser_separates_type_detection_from_owner_syntax():
    bare = parse_direct_memory_locator("abcdef12")
    qualified = parse_direct_memory_locator("../source:abcd")

    assert bare.memory_selector == "abcdef12"
    assert bare.context_locator is None
    assert qualified.memory_selector == "abcd"
    assert qualified.context_locator == "../source"
    assert is_direct_memory_locator_operand("abcdef12") is True
    assert is_direct_memory_locator_operand("source:abcd") is True
    assert is_direct_memory_locator_operand("source") is False
    assert is_direct_memory_locator_operand("abcd") is False


def test_auto_typed_operand_returns_one_typed_context_or_memory_value():
    context = parse_auto_typed_context_memory_operand("task-1")
    memory = parse_auto_typed_context_memory_operand("abcdef12")
    qualified = parse_auto_typed_context_memory_operand("../source:abcd")
    explicit = parse_auto_typed_context_memory_operand(
        "abcd",
        explicit_memory_context="../source",
    )

    assert context == ExistingContextOperand("task-1")
    assert memory == DirectMemoryLocator("abcdef12")
    assert qualified == DirectMemoryLocator("abcd", "../source")
    assert explicit == DirectMemoryLocator("abcd", "../source")


@pytest.mark.parametrize("operand", ("source::abcd", ":abcd", "source:"))
def test_direct_memory_locator_rejects_malformed_qualified_syntax(operand):
    with pytest.raises(ValueError, match="qualified Memory locator"):
        parse_direct_memory_locator(operand)


def test_direct_memory_locator_rejects_two_owner_spellings():
    with pytest.raises(ValueError, match="either CONTEXT:UID"):
        parse_direct_memory_locator("source:abcd", explicit_context="source")


def test_qualified_locator_resolves_relative_owner_and_short_prefix(isolated_store):
    store = MemoryStore()
    source = ops.init("practice/3")
    memory = ops.add(source, "owned source value")
    current = ops.init("practice/4")
    store.save(source)
    store.save(current)
    store.set_current(current.name)

    target = resolve_local_direct_memory_locator(
        store,
        f"../3:{memory.uid[:4]}",
        current=current.name,
    )

    assert target.context_name == source.name
    assert target.memory_uid == memory.uid


def test_local_auto_target_resolves_context_or_exact_memory(isolated_store):
    store = MemoryStore()
    source = ops.init("practice/3")
    memory = ops.add(source, "owned source value")
    current = ops.init("practice/4")
    store.save(source)
    store.save(current)
    store.set_current(current.name)

    context_target = resolve_local_context_memory_target(
        store,
        "../3",
        current=current.name,
    )
    memory_target = resolve_local_context_memory_target(
        store,
        memory.uid[:8],
        current=current.name,
    )

    assert context_target == ContextTarget(source.name)
    assert memory_target == DirectMemoryTarget(source.name, memory.uid)


def test_local_auto_target_resolves_short_uid_after_exact_context_miss(
    isolated_store,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = Memory(
        uid="084b1111-1111-4111-8111-111111111111",
        content="short-prefix target",
    )
    owner.add(memory)
    store.save(owner)

    target = resolve_local_context_memory_target(store, "084b", current=None)

    assert target == DirectMemoryTarget(owner.name, memory.uid)


def test_local_auto_target_preserves_exact_short_hex_context_name(isolated_store):
    store = MemoryStore()
    named = ops.init("084b")
    owner = ops.init("owner")
    memory = Memory(
        uid="084b1111-1111-4111-8111-111111111111",
        content="short-prefix target",
    )
    owner.add(memory)
    store.save(named)
    store.save(owner)

    target = resolve_local_context_memory_target(store, "084b", current=None)

    assert target == ContextTarget(named.name)


def test_bare_locator_ignores_memory_refs_and_embedded_context_bodies(
    isolated_store,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "owned value")
    projection = ops.init("projection")
    reference = ops.reference_memory(memory, owner, projection)
    embedded = ops.init("embedded-parent")
    ops.embed(owner, embedded)
    for context in (owner, projection, embedded):
        store.save(context)

    resolved = resolve_local_direct_memory_locator(
        store,
        memory.uid[:8],
        current=projection.name,
    )

    assert isinstance(projection.memories[reference.uid], MemoryRef)
    assert resolved.context_name == owner.name
    assert resolved.memory_uid == memory.uid


def test_direct_item_locator_includes_refs_and_query_rows_without_nested_bodies(
    isolated_store,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "owned value")
    projection = ops.init("projection")
    reference = ops.reference_memory(memory, owner, projection)
    query = ops.reference_query_context("concealed", "source", projection)
    for context in (owner, projection):
        store.save(context)

    reference_target = resolve_local_direct_item_locator(
        store,
        reference.uid[:8],
        current=owner.name,
    )
    query_target = resolve_local_direct_item_locator(
        store,
        query.uid[:8],
        current=owner.name,
    )

    assert isinstance(projection.memories[reference.uid], MemoryRef)
    assert isinstance(projection.memories[query.uid], QueryContextRef)
    assert reference_target.context_name == projection.name
    assert reference_target.item_uid == reference.uid
    assert query_target.context_name == projection.name
    assert query_target.item_uid == query.uid
