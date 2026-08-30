from __future__ import annotations

import json

import memcommit.application.operations.atomize.domain as atomize_module
import memcommit.application.operations.atomize.analysis_runtime as atomize_runtime_module
import memcommit.application.operations.compare.provider_contract as comparison_summary_module
import memcommit.application.capabilities.memory_issue_analysis.provider_contract as findings_module
import memcommit.application.capabilities.ops as ops
import memcommit.application.operations.query.answer as ordinary_query_module
from memcommit.application.operations.atomize.domain import (
    ATOMIZE_ANALYSIS_SCHEMA_VERSION,
    _payload as atomize_payload,
    _prompt as atomize_prompt,
    collect_atomize_candidates,
)
from tests.atomize_analysis_support import (
    open_or_create_atomize_review_record,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import ComparisonInput
from memcommit.application.operations.compare.compare_rules import (
    comparison_summary_ruleset_prompt_payload,
)
from memcommit.application.capabilities.semantic.generative_reduction_reference import (
    distill_elaborate_reference_payload,
    render_distill_elaborate_reference_examples,
)
from memcommit.application.operations.search.answer_references import (
    SearchAnswerEvidence,
)
from memcommit.application.operations.profile.config import (
    STUDY_RUN_AUTHORITY_SOURCE_KIND,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
    ProfileEntry,
    ProfileRegistry,
)
from memcommit.application.capabilities.semantic.prompt_policy import (
    GENERAL_PROMPT_POLICY_ID,
    GENERAL_SEMANTIC_PROMPT_POLICY,
    STUDY_PROMPT_POLICY_ID,
    STUDY_SEMANTIC_PROMPT_POLICY,
    resolve_semantic_prompt_policy,
)
from memcommit.persistence.store import MemoryStore


def _registry(profile: ProfileEntry) -> ProfileRegistry:
    return ProfileRegistry(
        generation=1,
        active_uid=profile.uid,
        profiles=(profile,),
    )


def _study_profile(*, role: str) -> ProfileEntry:
    return ProfileEntry(
        uid=(
            "11111111-1111-4111-8111-111111111111"
            if role == STUDY_RUN_PARTICIPANT_SOURCE_KIND
            else "22222222-2222-4222-8222-222222222222"
        ),
        name="participant" if role == STUDY_RUN_PARTICIPANT_SOURCE_KIND else "grant",
        kind="MANAGED",
        source={
            "kind": role,
            "study_uid": "33333333-3333-4333-8333-333333333333",
            "study_name": "study",
            "created_at": "2026-08-23T00:00:00+00:00",
            "baseline_sha256": "a" * 64,
            "baseline_profile_uid": "44444444-4444-4444-8444-444444444444",
            "baseline_profile_name": "baseline",
            "provider_policy_version": "study-provider-config-v1",
            "provider_policy_digest": "b" * 64,
        },
    )


def test_general_profile_retains_authored_examples() -> None:
    profile = ProfileEntry(
        uid="55555555-5555-4555-8555-555555555555",
        name="ordinary",
        kind="MANAGED",
    )

    policy = resolve_semantic_prompt_policy(registry=_registry(profile))

    assert policy.policy_id == GENERAL_PROMPT_POLICY_ID
    assert policy.scope == "GENERAL"
    assert policy.include_authored_examples is True


def test_both_study_roles_use_rules_only_prompts() -> None:
    for role in (
        STUDY_RUN_PARTICIPANT_SOURCE_KIND,
        STUDY_RUN_AUTHORITY_SOURCE_KIND,
    ):
        policy = resolve_semantic_prompt_policy(
            registry=_registry(_study_profile(role=role))
        )

        assert policy.policy_id == STUDY_PROMPT_POLICY_ID
        assert policy.scope == "STUDY"
        assert policy.include_authored_examples is False


def test_rules_only_projection_drops_examples_but_not_rules() -> None:
    general = comparison_summary_ruleset_prompt_payload()
    study = comparison_summary_ruleset_prompt_payload(include_cases=False)
    general_reference = distill_elaborate_reference_payload()
    study_reference = distill_elaborate_reference_payload(
        include_examples=False,
    )

    assert general["cases"]
    assert study["cases"] == []
    assert study["rules"] == general["rules"]
    assert general_reference["families"]
    assert study_reference["families"] == []
    assert render_distill_elaborate_reference_examples(include_examples=False) == ""


def test_atomize_study_prompt_keeps_input_and_rules_but_omits_demos() -> None:
    context = ops.init("prompt-policy/atomize")
    ops.add(context, "The entrance closes at five.")
    ops.add(context, "A card is required after closing.")
    candidates = collect_atomize_candidates(context)

    general = atomize_payload(
        context,
        candidates,
        prompt_policy=GENERAL_SEMANTIC_PROMPT_POLICY,
    )
    study = atomize_payload(
        context,
        candidates,
        prompt_policy=STUDY_SEMANTIC_PROMPT_POLICY,
    )

    assert study["memories"] == general["memories"]
    assert study["rules"] == general["rules"]
    assert "prompt_policy" not in general
    assert study["prompt_policy"] == STUDY_SEMANTIC_PROMPT_POLICY.to_prompt_record()
    assert general["calibration_cases"]
    assert study["calibration_cases"] == []
    assert general["quality_scan"]["ambiguity_calibration_cases"]
    assert study["quality_scan"]["ambiguity_calibration_cases"] == []
    assert general["quality_scan"]["conflict_calibration_cases"]
    assert study["quality_scan"]["conflict_calibration_cases"] == []
    assert "after that time a card is required" in atomize_prompt(general)
    assert "after that time a card is required" not in atomize_prompt(study)


def test_find_and_query_study_turns_omit_authored_examples(monkeypatch) -> None:
    monkeypatch.setattr(
        findings_module,
        "resolve_semantic_prompt_policy",
        lambda: STUDY_SEMANTIC_PROMPT_POLICY,
    )
    record, cases = findings_module._prompt_calibration_cases("ambiguity.json")
    assert record == STUDY_SEMANTIC_PROMPT_POLICY.to_prompt_record()
    assert cases == []

    evidence = (
        SearchAnswerEvidence(
            "m1",
            "policy",
            "memory",
            "11111111-policy",
            "The entrance closes at five.",
        ),
    )
    monkeypatch.setattr(
        ordinary_query_module,
        "resolve_semantic_prompt_policy",
        lambda: STUDY_SEMANTIC_PROMPT_POLICY,
    )
    study_prompt, _schema = ordinary_query_module._build_prompt(
        "When does the entrance close?",
        evidence,
    )
    study_payload = json.loads(study_prompt.split("ORDINARY QUERY PAYLOAD:\n", 1)[1])
    assert "PROVIDER-VISIBLE METHOD EXAMPLES" not in study_prompt
    assert study_payload["prompt_policy"] == (
        STUDY_SEMANTIC_PROMPT_POLICY.to_prompt_record()
    )


def test_comparison_payload_switches_only_the_authored_case_projection(
    monkeypatch,
) -> None:
    reference = ops.init("policy/reference")
    compared = ops.init("policy/compared")
    ops.add(reference, "Use two sentences.")
    ops.add(compared, "Use three sentences when needed.")
    frame = ComparisonInput.from_contexts(reference, compared)

    monkeypatch.setattr(
        comparison_summary_module,
        "resolve_semantic_prompt_policy",
        lambda: GENERAL_SEMANTIC_PROMPT_POLICY,
    )
    general = comparison_summary_module._provider_payload(frame)[0]
    monkeypatch.setattr(
        comparison_summary_module,
        "resolve_semantic_prompt_policy",
        lambda: STUDY_SEMANTIC_PROMPT_POLICY,
    )
    study = comparison_summary_module._provider_payload(frame)[0]

    assert general["frames"] == study["frames"]
    assert "prompt_policy" not in general
    assert study["prompt_policy"] == STUDY_SEMANTIC_PROMPT_POLICY.to_prompt_record()
    assert general["ruleset"]["rules"] == study["ruleset"]["rules"]
    assert general["ruleset"]["cases"]
    assert study["ruleset"]["cases"] == []


class _AtomicProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        return json.dumps(
            {
                "overview": {
                    "understood": {"text": "", "source_ids": []},
                    "changed": {"text": "", "source_ids": []},
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": item["candidate_id"],
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "The Memory has one focal commitment.",
                    }
                    for item in payload["memories"]
                ],
                "quality_issues": [],
            }
        )


def _patch_atomize_policy(monkeypatch, policy) -> None:
    monkeypatch.setattr(
        atomize_module,
        "resolve_semantic_prompt_policy",
        lambda: policy,
    )
    monkeypatch.setattr(
        atomize_runtime_module,
        "resolve_semantic_prompt_policy",
        lambda: policy,
    )


def test_atomize_cache_identity_changes_with_the_study_prompt_policy(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    context = ops.init("prompt-policy/cache")
    ops.add(context, "The entrance closes at five.")
    store.save(context)
    study_provider = _AtomicProvider()
    _patch_atomize_policy(monkeypatch, STUDY_SEMANTIC_PROMPT_POLICY)

    study = open_or_create_atomize_review_record(
        store=store,
        ctx=context,
        provider_factory=lambda: study_provider,
    )
    serialized = study.analysis.to_dict()

    assert study_provider.calls == 1
    assert study.analysis.prompt_policy_id == STUDY_PROMPT_POLICY_ID
    assert serialized["schema_version"] == ATOMIZE_ANALYSIS_SCHEMA_VERSION
    assert serialized["prompt_policy_id"] == STUDY_PROMPT_POLICY_ID

    reused = open_or_create_atomize_review_record(
        store=store,
        ctx=context,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("matching Study analysis opened a provider")
        ),
    )
    assert reused.analysis.uid == study.analysis.uid

    general_provider = _AtomicProvider()
    _patch_atomize_policy(monkeypatch, GENERAL_SEMANTIC_PROMPT_POLICY)
    general = open_or_create_atomize_review_record(
        store=store,
        ctx=context,
        provider_factory=lambda: general_provider,
    )

    assert general_provider.calls == 1
    assert general.analysis.uid != study.analysis.uid
    assert general.analysis.prompt_policy_id == GENERAL_PROMPT_POLICY_ID
    assert "prompt_policy_id" not in general.analysis.to_dict()
