import json
import uuid

import memcommit.application.ops as ops
from memcommit.application.authority.access import ContextAccess
from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonInput,
    ComparisonMember,
    ComparisonRelation,
    ComparisonReports,
)
from memcommit.context import Context
from memcommit.eval.study_compare_prewarm import prewarm_pair
from memcommit.provider_types import CompletionRun, ProviderIdentity
from memcommit.store import MemoryStore


def _contexts(store: MemoryStore) -> tuple[Context, Context]:
    reference = Context(uid=str(uuid.uuid4()), name="reference")
    compared = Context(uid=str(uuid.uuid4()), name="compared")
    ops.add(reference, "private reference content")
    ops.add(compared, "private compared content")
    store.create_context(reference)
    store.create_context(compared)
    return reference, compared


def _analysis(comparison_input: ComparisonInput) -> ComparisonAnalysis:
    reference, compared = comparison_input.frames
    relation = ComparisonRelation.from_dict(
        {
            "uid": str(uuid.uuid4()),
            "kind": "EQUIVALENT",
            "status": "RESOLVED",
            "members": [
                ComparisonMember(
                    frame_uid=reference.uid,
                    memory_uid=reference.memories[0].uid,
                ).to_dict(),
                ComparisonMember(
                    frame_uid=compared.uid,
                    memory_uid=compared.memories[0].uid,
                ).to_dict(),
            ],
            "summary": "The two test Memories match.",
            "reason": "They contain the same test proposition.",
        }
    )
    return ComparisonAnalysis.create(
        comparison_input,
        overview="One complete test relation.",
        reports=ComparisonReports(
            both="One shared relation.",
            differences="",
            reference_only="",
            compared_only="",
        ),
        relations=(relation,),
        issues=(),
    )


class _Analyzer:
    def __init__(self):
        self.calls = 0
        self.provider = type(
            "ProviderEvidence",
            (),
            {
                "identity": ProviderIdentity(
                    provider="codex_chatgpt",
                    model="gpt-5.6-sol",
                    runtime="test",
                    reasoning_effort="medium",
                ),
                "last_run": CompletionRun(
                    identity=ProviderIdentity(
                        provider="codex_chatgpt",
                        model="gpt-5.6-sol",
                        runtime="test",
                        reasoning_effort="medium",
                    ),
                    operation="compare_contexts",
                ),
                "provider_seconds": 0.0,
            },
        )()

    def __call__(self, comparison_input: ComparisonInput) -> ComparisonAnalysis:
        self.calls += 1
        return _analysis(comparison_input)


def _accesses(
    store: MemoryStore,
    contexts: tuple[Context, Context],
) -> tuple[ContextAccess, ContextAccess]:
    return tuple(
        ContextAccess(
            store=store,
            context_name=context.name,
            display_name=context.name,
            attachment_name=None,
            permission="READ",
        )
        for context in contexts
    )  # type: ignore[return-value]


def test_study_compare_prewarm_publishes_then_reuses_exact_pair(isolated_store):
    store = MemoryStore()
    contexts = _contexts(store)
    accesses = _accesses(store, contexts)
    analyzer = _Analyzer()

    first, first_receipt = prewarm_pair(
        store=store,
        accesses=accesses,
        contexts=contexts,
        include_descendants=(False, False),
        analyze=analyzer,
        profile_name="study-test",
        requested_model="gpt-5.6-sol",
        requested_reasoning="medium",
    )
    second, second_receipt = prewarm_pair(
        store=store,
        accesses=accesses,
        contexts=contexts,
        include_descendants=(False, False),
        analyze=lambda _: (_ for _ in ()).throw(
            AssertionError("exact prewarm must reuse without analysis")
        ),
        profile_name="study-test",
        requested_model="gpt-5.6-sol",
        requested_reasoning="medium",
    )

    assert analyzer.calls == 1
    assert first.reused is False
    assert first_receipt["provider_calls"] == 1
    assert second.reused is True
    assert second_receipt["provider_calls"] == 0
    assert second.analysis.uid == first.analysis.uid
    assert second_receipt["semantic_content_in_receipt"] is False
    serialized = json.dumps(second_receipt)
    assert "private reference content" not in serialized
    assert "private compared content" not in serialized
