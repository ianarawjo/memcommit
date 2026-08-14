"""Application and Store-backed runtime tests for structural Merge."""

from __future__ import annotations

from dataclasses import replace

import pytest

import memcommit.ops as ops
from memcommit.context import Memory
from memcommit.merge_application import (
    FrozenMergePlan,
    MergeAddition,
    MergeContextResult,
    MergeError,
    MergeItemKind,
    MergeReach,
    MergeRequest,
    MergeResult,
    prepare_merge,
    run_merge,
)
from memcommit.merge_runtime import execute_merge
from memcommit.store import MemoryStore


class _FakePort:
    def __init__(self):
        self.requests: list[MergeRequest] = []
        self.plans: list[FrozenMergePlan] = []

    def freeze(self, request: MergeRequest) -> FrozenMergePlan:
        self.requests.append(request)
        plan = FrozenMergePlan(
            request=request,
            source_name="source",
            source_uid="source-uid",
            source_digest="source-digest",
            target_name="target",
            target_uid="target-uid",
            target_digest="target-digest",
            additions=(MergeAddition(uid="memory-uid", kind=MergeItemKind.MEMORY),),
            contexts=(
                MergeContextResult(
                    source_name="source",
                    source_uid="source-uid",
                    target_name="target",
                    target_uid="target-uid",
                    target_created=False,
                    additions=(
                        MergeAddition(
                            uid="memory-uid",
                            kind=MergeItemKind.MEMORY,
                        ),
                    ),
                ),
            ),
            cross_profile_memory_only=False,
            token=self,
        )
        self.plans.append(plan)
        return plan

    def apply(self, plan: FrozenMergePlan) -> MergeResult:
        return MergeResult(
            source_name=plan.source_name,
            source_uid=plan.source_uid,
            target_name=plan.target_name,
            target_uid=plan.target_uid,
            reach=plan.request.reach,
            additions=plan.additions,
            contexts=plan.contexts,
            checkpoint_uid="checkpoint-uid",
            checkpoint_uids=("checkpoint-uid",),
            cross_profile_memory_only=plan.cross_profile_memory_only,
        )


def test_application_validates_before_freezing_a_store():
    port = _FakePort()

    with pytest.raises(MergeError, match="Source locator"):
        run_merge(MergeRequest(source_locator=""), port=port)

    assert port.requests == []


def test_application_accepts_descendant_reach_without_store_knowledge():
    port = _FakePort()

    plan = prepare_merge(
        MergeRequest(source_locator="source", reach=MergeReach.DESCENDANTS),
        port=port,
    )

    assert plan.request.reach is MergeReach.DESCENDANTS
    assert port.requests == [plan.request]


def test_application_rejects_a_receipt_that_does_not_match_the_plan():
    class WrongPort(_FakePort):
        def apply(self, plan: FrozenMergePlan) -> MergeResult:
            return replace(super().apply(plan), target_uid="other-target")

    with pytest.raises(MergeError, match="receipt does not match"):
        run_merge(MergeRequest(source_locator="source"), port=WrongPort())


def test_store_runtime_merges_without_terminal_output(isolated_store, capsys):
    store = MemoryStore()
    source = ops.init("source")
    shared_uid = "00000000-0000-0000-0000-000000000001"
    source.add(Memory(uid=shared_uid, content="source revision"))
    novel = ops.add(source, "new fact")
    store.create_context(source)
    target = ops.init("target")
    target.add(Memory(uid=shared_uid, content="target revision"))
    store.create_context(target)
    store.set_current(target.name)

    result = execute_merge(MergeRequest(source_locator="source"), store=store)

    assert capsys.readouterr() == ("", "")
    assert result.source_name == "source"
    assert result.target_name == "target"
    assert result.additions == (
        MergeAddition(uid=novel.uid, kind=MergeItemKind.MEMORY),
    )
    assert result.checkpoint_uid
    merged = store.load_direct("target")
    assert merged.memories[shared_uid].content == "target revision"
    assert merged.memories[novel.uid].content == "new fact"
