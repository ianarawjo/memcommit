"""Shared direct-Memory locator grammar and local owner resolution."""

import pytest

import memcommit.ops as ops
from memcommit.context import MemoryRef
from memcommit.context_targeting.loading import (
    resolve_local_direct_memory_locator,
)
from memcommit.context_targeting.resolution import (
    is_direct_memory_locator_operand,
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
