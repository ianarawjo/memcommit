"""Stable Python contracts for process-local Forget review and Apply."""

from __future__ import annotations

import json
import uuid

import pytest

from memcommit.api import (
    ForgetApplyResult,
    ForgetConflictError,
    ForgetInputError,
    ForgetReviewResult,
    MemCommitClient,
)
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.store import MemoryStore


class _ForgetProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        assert operation == "forget"
        assert output_schema is not None
        messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
        payload = json.loads(
            messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
        )
        keep_all = self.calls > 1
        candidates = []
        for index, source in enumerate(payload["source"]["memories"]):
            remove = index == 0 and not keep_all
            candidates.append(
                {
                    "source_memory_id": source["item_id"],
                    "decision": "DELETE" if remove else "KEEP",
                    "proposed_content": "" if remove else source["content"],
                    "rationale": "Reviewed against the complete instruction.",
                    "criterion_item_ids": ["k1"],
                }
            )
        return json.dumps(
            {
                "overview": "Reviewed every direct Source Memory.",
                "candidates": candidates,
            }
        )


def _source(root, name: str = "forget/public") -> tuple[MemoryStore, Context]:
    store = MemoryStore(root=root)
    context = Context(uid=str(uuid.uuid4()), name=name)
    context.add(
        Memory(
            uid=str(uuid.uuid4()),
            content="The old desk was beside the west entrance.",
        )
    )
    context.add(
        Memory(
            uid=str(uuid.uuid4()),
            content="The accessible entrance remains on the north side.",
        )
    )
    store.create_context(context)
    store.set_current(context.name)
    return store, context


def test_public_forget_analyze_select_noop_and_apply(tmp_path) -> None:
    root = tmp_path / "store"
    store, source = _source(root)
    provider = _ForgetProvider()
    client = MemCommitClient(
        root=root,
        semantic_provider_factory=lambda: provider,
    )

    analyzed = client.analyze_forget("Forget the old desk.")
    selected = client.select_forget(
        analyzed,
        analyzed.candidates[0].uid,
        "KEEP",
    )
    applied = client.apply_forget(selected)

    assert isinstance(analyzed, ForgetReviewResult)
    assert analyzed.source_context == source.name
    assert analyzed.retention == "PROCESS_LOCAL"
    assert analyzed.provider_used is True
    assert analyzed.candidates[0].recommendation == "DELETE"
    assert selected.review_uid == analyzed.review_uid
    assert selected.version != analyzed.version
    assert selected.provider_used is False
    assert isinstance(applied, ForgetApplyResult)
    assert applied.applied is False
    assert applied.changed_count == 0
    assert applied.checkpoint_uid is None
    assert tuple(store.load_direct(source.name).memories) == tuple(source.memories)
    assert store.list_checkpoints(source.name) == []


def test_public_forget_revision_and_exact_apply(tmp_path) -> None:
    root = tmp_path / "store"
    store, source = _source(root)
    provider = _ForgetProvider()
    client = MemCommitClient(
        root=root,
        semantic_provider_factory=lambda: provider,
    )
    analyzed = client.analyze_forget(
        "Forget the old desk.",
        context_name=source.name,
    )

    revised = client.revise_forget(analyzed, "Keep every Memory instead.")
    removal_provider = _ForgetProvider()
    removal_client = MemCommitClient(
        root=root,
        semantic_provider_factory=lambda: removal_provider,
    )
    removal = removal_client.analyze_forget(
        "Forget the old desk.",
        context_name=source.name,
    )
    applied = removal_client.apply_forget(removal)

    assert revised.review_uid == analyzed.review_uid
    assert revised.version != analyzed.version
    assert revised.provider_used is True
    assert all(candidate.selected_action == "KEEP" for candidate in revised.candidates)
    assert applied.applied is True
    assert applied.removed_count == 1
    assert applied.edited_count == 0
    assert applied.checkpoint_uid is not None
    assert applied.undo_available is True
    current = store.load_direct(source.name)
    assert len(current.memories) == 1
    assert [entry["command"] for entry in store.list_checkpoints(source.name)] == [
        "forget"
    ]


def test_public_forget_review_cannot_cross_client_store_boundary(tmp_path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _source(first_root, "forget/first")
    _source(second_root, "forget/second")
    provider = _ForgetProvider()
    first = MemCommitClient(
        root=first_root,
        semantic_provider_factory=lambda: provider,
    )
    second = MemCommitClient(
        root=second_root,
        semantic_provider_factory=lambda: provider,
    )
    review = first.analyze_forget("Forget the old desk.")

    with pytest.raises(ForgetInputError, match="different MemCommit Store"):
        second.apply_forget(review)


def test_public_forget_stale_source_fails_without_reviewed_removal(tmp_path) -> None:
    root = tmp_path / "store"
    store, source = _source(root)
    provider = _ForgetProvider()
    client = MemCommitClient(
        root=root,
        semantic_provider_factory=lambda: provider,
    )
    review = client.analyze_forget("Forget the old desk.")
    concurrent = store.load_direct(source.name)
    new_memory = Memory(uid=str(uuid.uuid4()), content="A concurrent note survives.")
    concurrent.add(new_memory)
    store.save(
        concurrent,
        AutoCheckpoint(
            command="add",
            args={},
            description="Concurrent test change.",
        ),
    )

    with pytest.raises(ForgetConflictError):
        client.apply_forget(review)

    current = store.load_direct(source.name)
    assert set(source.memories) <= set(current.memories)
    assert new_memory.uid in current.memories
    assert [entry["command"] for entry in store.list_checkpoints(source.name)].count(
        "forget"
    ) == 0
