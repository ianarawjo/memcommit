"""Readable Store composition for deterministic Find."""

from __future__ import annotations

import memcommit.application.ops as ops
from memcommit.application.authority.access import ContextAccess
from memcommit.core.context_targeting.readable_catalog import ReadableContextCatalog
from memcommit.application.operations.find.application import FindRequest
from memcommit.application.operations.find.runtime import execute_find
from memcommit.persistence.store import MemoryStore


def _catalog(store: MemoryStore, name: str) -> ReadableContextCatalog:
    return ReadableContextCatalog(
        store,
        ContextAccess(
            store=store,
            context_name=name,
            display_name=name,
            attachment_name=None,
            permission="READ",
        ),
    )


def test_runtime_keeps_lexical_descendants_and_embeds_independent(tmp_path):
    store = MemoryStore(root=tmp_path / "store")
    root = ops.init("scope")
    ops.add(root, "ROOT needle")
    child = ops.init("scope/child")
    ops.add(child, "CHILD needle")
    embedded = ops.init("elsewhere")
    ops.add(embedded, "EMBEDDED needle")
    ops.embed(embedded, root)
    for context in (root, child, embedded):
        store.save(context)
    catalog = _catalog(store, root.name)

    descendants = execute_find(
        FindRequest(
            pattern="needle",
            target_names=(root.name,),
            include_descendants=True,
            follow_embeds=False,
        ),
        catalog=catalog,
    )
    embeds = execute_find(
        FindRequest(
            pattern="needle",
            target_names=(root.name,),
            include_descendants=False,
            follow_embeds=True,
        ),
        catalog=catalog,
    )

    assert {match.source.content for match in descendants.matches} == {
        "ROOT needle",
        "CHILD needle",
    }
    assert {match.source.content for match in embeds.matches} == {
        "ROOT needle",
        "EMBEDDED needle",
    }


def test_runtime_searches_resolved_reference_content_without_changing_source(tmp_path):
    store = MemoryStore(root=tmp_path / "store")
    source = ops.init("source")
    memory = ops.add(source, "one shared needle")
    target = ops.init("target")
    ops.embed_memory(memory, source, target)
    store.save(source)
    store.save(target)
    before = store.load_direct(source.name).to_dict()

    result = execute_find(
        FindRequest(pattern="needle", target_names=(target.name,)),
        catalog=_catalog(store, target.name),
    )

    assert result.matches[0].source.kind == "memory_ref"
    assert result.matches[0].source.source_context_name == source.name
    assert result.matches[0].source.source_memory_uid == memory.uid
    assert store.load_direct(source.name).to_dict() == before
