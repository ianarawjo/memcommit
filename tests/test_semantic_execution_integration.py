"""Staged execution preserves the public Find and Translate contracts."""

from __future__ import annotations

import json

import memcommit.application.ops as ops
import pytest
from memcommit.context import Memory
from memcommit.application.operations.search.model import SearchCandidate, rank_candidates
from memcommit.application.semantic_execution import SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT
from memcommit.application.operations.translate.runtime import plan_translation


def _large_text(marker: str) -> str:
    return marker + " " + (
        "x" * (SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT // 4 + 10_000)
    )


class FirstFindCandidateProvider:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "search"
        payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
        self.payloads.append(payload)
        candidate = payload["candidates"][0]
        return json.dumps(
            {
                "matches": [{"candidate_id": candidate["candidate_id"]}],
                "related_query": "",
                "related_matches": [],
            }
        )


def test_large_find_uses_context_batches_then_one_global_rerank():
    candidates = [
        SearchCandidate(
            candidate_id=f"c{index:06d}",
            kind="memory",
            context_uid=f"context-{index}",
            context_names=(f"root/context-{index}",),
            item=Memory(uid=f"memory-{index}", content=_large_text(f"item {index}")),
            search_text=_large_text(f"item {index}"),
        )
        for index in range(1, 5)
    ]
    provider = FirstFindCandidateProvider()
    progress: list[str] = []

    matches = rank_candidates(
        "item",
        candidates,
        provider,
        limit=5,
        on_progress=lambda value: progress.append(value.phase),
    )

    assert len(provider.payloads) == 3
    batch_ids = [
        candidate["candidate_id"]
        for payload in provider.payloads[:2]
        for candidate in payload["candidates"]
    ]
    assert batch_ids == [candidate.candidate_id for candidate in candidates]
    assert len(set(batch_ids)) == len(batch_ids)
    assert len(provider.payloads[2]["candidates"]) == 2
    assert [match.candidate.candidate_id for match in matches] == ["c000001"]
    assert progress == ["BATCH", "BATCH", "RECONCILE", "COMPLETE"]


class EchoTranslationProvider:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "translate"
        payload = json.loads(prompt.split("TRANSLATE PAYLOAD:\n", 1)[1])
        self.payloads.append(payload)
        return json.dumps(
            {
                "translations": [
                    {
                        "candidate_id": item["candidate_id"],
                        "translated_content": "translated " + item["content"],
                    }
                    for item in payload["memories"]
                ]
            }
        )


def test_large_translate_maps_every_memory_once_across_atomic_batches():
    ctx = ops.init("large-translate")
    memories = [
        ops.add(ctx, _large_text(f"source {index}"))
        for index in range(1, 5)
    ]
    provider = EchoTranslationProvider()
    progress: list[str] = []

    plan = plan_translation(
        ctx,
        "English",
        lambda: provider,
        on_progress=lambda value: progress.append(value.phase),
    )

    assert len(provider.payloads) == 2
    sent_ids = [
        item["candidate_id"]
        for payload in provider.payloads
        for item in payload["memories"]
    ]
    assert sent_ids == [f"m{index:06d}" for index in range(1, 5)]
    assert [proposal.source_uid for proposal in plan.proposals] == [
        memory.uid for memory in memories
    ]
    assert progress == ["BATCH", "BATCH", "COMPLETE"]


class KeepForgetLLM:
    model = "test-model"

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        payload = json.loads(
            messages[-1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
        )
        source = payload["source"]["memories"][0]
        return json.dumps(
            {
                "overview": "Keep the Source.",
                "candidates": [
                    {
                        "source_memory_id": source["item_id"],
                        "decision": "KEEP",
                        "proposed_content": source["content"],
                        "rationale": "The instruction does not cover it.",
                        "criterion_item_ids": ["k1"],
                    }
                ],
            }
        )


def test_forget_revision_cannot_bypass_whole_frame_budget_with_large_history():
    ctx = ops.init("forget-history")
    ops.add(ctx, "Keep this Memory.")
    first = KeepForgetLLM()
    _changes, history = ops.forget(ctx, "Forget nothing here.", first)
    history.insert(
        0,
        {
            "role": "system",
            "content": "x" * (SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT + 1),
        },
    )
    forbidden = KeepForgetLLM()

    with pytest.raises(ValueError, match="review history exceed"):
        ops.revise_forget("Keep the reviewed result.", forbidden, history, ctx)

    assert forbidden.calls == 0
