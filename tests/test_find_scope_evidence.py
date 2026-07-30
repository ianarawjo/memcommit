"""Three-scope local evidence collection contracts."""
from __future__ import annotations

import memcommit.ops as ops
from memcommit.context import QueryContextRef
from memcommit.find_scope_evidence import (
    candidate_logical_identity,
    collect_outside_context_evidence,
    context_remainder_evidence,
    frame_context_uids,
)
from memcommit.search import collect_candidates
from memcommit.store import MemoryStore


def test_visible_reference_excludes_its_direct_target_from_remainder():
    source = ops.init("source")
    memory = ops.add(source, "The shared fact.")
    root = ops.init("root")
    ref = ops.reference_memory(memory, source, root)
    root.add(source)
    candidates = collect_candidates(root)

    assert candidates[0].item is ref
    assert candidates[0].context_names == ("root", "source")
    assert context_remainder_evidence(candidates, [candidates[0]]) == ()


def test_branch_copies_with_distinct_context_identity_remain_distinct():
    first = ops.init("branch-a")
    second = ops.init("branch-b")
    first_memory = ops.add(first, "First version.")
    second.add(type(first_memory)(first_memory.uid, "Second version."))
    root = ops.init("root")
    root.add(first)
    root.add(second)

    candidates = collect_candidates(root)

    assert len(candidates) == 2
    assert (
        candidate_logical_identity(candidates[0])
        != candidate_logical_identity(candidates[1])
    )


def test_recursive_child_is_inside_frame_but_direct_child_is_outside(
    isolated_store,
):
    store = MemoryStore()
    child = ops.init("child")
    child_memory = ops.add(child, "Child evidence.")
    store.save(child)
    root = ops.init("root")
    root_memory = ops.add(root, "Root evidence.")
    root.add(child)
    store.save(root)
    loaded = store.load("root")

    recursive_candidates = collect_candidates(loaded, recursive=True)
    recursive_outside = collect_outside_context_evidence(
        store,
        excluded_context_uids=frame_context_uids(
            loaded,
            recursive=True,
        ),
        excluded_candidates=recursive_candidates,
    )
    direct_candidates = collect_candidates(loaded, recursive=False)
    direct_outside = collect_outside_context_evidence(
        store,
        excluded_context_uids=frame_context_uids(
            loaded,
            recursive=False,
        ),
        excluded_candidates=direct_candidates,
    )

    assert {item.uid for item in recursive_outside.evidence} == set()
    assert {item.uid for item in direct_outside.evidence} == {
        child_memory.uid,
    }
    assert {candidate.item.uid for candidate in direct_candidates} == {
        root_memory.uid,
    }


def test_outside_collection_resolves_refs_and_excludes_frame_logical_items(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("root")
    hidden = ops.add(root, "Already in the frame corpus.")
    store.save(root)
    other = ops.init("other")
    ops.reference_memory(hidden, root, other)
    independent = ops.add(other, "Independent outside evidence.")
    store.save(other)
    loaded_root = store.load("root")
    frame_candidates = collect_candidates(loaded_root)

    collected = collect_outside_context_evidence(
        store,
        excluded_context_uids=frame_context_uids(
            loaded_root,
            recursive=True,
        ),
        excluded_candidates=frame_candidates,
    )

    assert collected.status == "SEARCHED"
    assert [item.uid for item in collected.evidence] == [independent.uid]
    assert collected.evidence[0].alias == "x1"


def test_query_only_collection_uses_public_projection_without_source_load(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("root")
    ops.add(root, "Visible.")
    store.save(root)
    other = ops.init("other")
    pointer = QueryContextRef(
        uid="query-pointer",
        name="public-policy",
        target_source_uid="concealed-source",
        provider="codex_chatgpt",
    )
    other.add(pointer)
    store.save(other)
    monkeypatch.setattr(
        store,
        "load_query_source",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("query-only source must remain concealed")
        ),
    )

    loaded_root = store.load("root")
    frame_candidates = collect_candidates(loaded_root)
    collected = collect_outside_context_evidence(
        store,
        excluded_context_uids=frame_context_uids(
            loaded_root,
            recursive=True,
        ),
        excluded_candidates=frame_candidates,
    )

    query = next(item for item in collected.evidence if item.kind == "query")
    assert query.uid == pointer.uid
    assert query.content == "public-policy (query-only)"
    assert "concealed-source" not in query.content


def test_disappearing_context_marks_outside_scan_partial(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("root")
    store.save(root)
    monkeypatch.setattr(
        store,
        "list_context_names",
        lambda: ["root", "disappeared"],
    )

    collected = collect_outside_context_evidence(
        store,
        excluded_context_uids=frozenset({root.uid}),
        excluded_candidates=(),
    )

    assert collected.status == "PARTIAL"
