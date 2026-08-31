"""Whole-Context Audit Fit projection into the shared Resolve/Meld issue loop."""

from __future__ import annotations

import json

import memcommit.application.capabilities.ops as ops
from memcommit.application.operations.audit.application import run_quality_audit
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.fit.judgment import (
    FIT_JUDGMENT_OPERATION,
    FIT_JUDGMENT_PAYLOAD_MARKER,
)
from memcommit.application.operations.resolve.application import (
    FrozenResolveFrame,
    ResolveFrameMemory,
    ResolveRequest,
)
from memcommit.application.operations.resolve.semantic import (
    RESOLVE_OPERATION,
    ProviderResolveSemanticPort,
    all_audit_issue_keys,
)
from memcommit.providers.types import ProviderIdentity


class MayFitAuditProvider:
    identity = ProviderIdentity(provider="test", model="audit-fit-model")

    def complete(self, prompt, *, operation, output_schema=None):
        del output_schema
        if operation.startswith("find_"):
            return '{"findings": []}'
        assert operation == FIT_JUDGMENT_OPERATION
        payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
        aliases = tuple(
            item["proposition_id"] for item in payload["questions"][0]["propositions"]
        )
        return json.dumps(
            {
                "overview": "The schedule has two materially ordinary readings.",
                "judgments": [
                    {
                        "question_id": "fit",
                        "verdict": "MAY",
                        "reason": "The first and third Memories may govern one door.",
                        "considered_proposition_ids": list(aliases),
                        "material_proposition_ids": [aliases[0], aliases[-1]],
                        "consistent_reading": "The times govern different doors.",
                        "inconsistent_reading": "The times govern the same door.",
                    }
                ],
            }
        )


class DirectionProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        del output_schema
        assert operation == RESOLVE_OPERATION
        payload = json.loads(prompt.split("RESOLVE AUDIT PAYLOAD:\n", 1)[1])
        assert len(payload["audit"]["items"]) == 1
        item = payload["audit"]["items"][0]
        assert item["kind"] == "FIT"
        return json.dumps(
            {
                "directions": [
                    {
                        "item_id": item["item_id"],
                        "direction": "State which door each schedule governs.",
                    }
                ]
            }
        )


def _context():
    context = ops.init("audit/fit-source")
    first = ops.add(context, "The entrance opens at 8:00.")
    second = ops.add(context, "The loading dock opens at 7:00.")
    third = ops.add(context, "The entrance remains closed until 9:00.")
    return context, first, second, third


def test_audit_fit_may_becomes_one_set_level_resolve_item():
    context, first, _second, third = _context()
    audit = run_quality_audit(context, MayFitAuditProvider)
    restored = QualityAuditSession.from_dict(audit.to_dict())

    assert restored.fit is not None
    assert restored.fit.verdict == "MAY"
    assert restored.fit.material_memory_uids == (first.uid, third.uid)
    expected_key = f"FIT:{first.uid}:{third.uid}"
    assert all_audit_issue_keys(restored) == (expected_key,)

    frame = FrozenResolveFrame(
        request=ResolveRequest(context.name),
        context_uid=context.uid,
        context_name=context.name,
        display_name=context.name,
        context_digest="0" * 64,
        revision="1" * 64,
        memories=tuple(
            ResolveFrameMemory(f"m{index}", memory.uid, memory.content)
            for index, memory in enumerate(context.memories.values(), 1)
        ),
        actionable_uids=tuple(context.memories),
        allowed_effects=("CREATE", "UPDATE"),
        denied_effects=(),
    )
    semantic = ProviderResolveSemanticPort()
    semantic.preflight(frame, restored)
    analysis = semantic.analyze(frame, restored, provider=DirectionProvider())

    assert len(analysis.review_issues) == 1
    issue = analysis.review_issues[0]
    assert issue.kind == "FIT"
    assert issue.classification == "MAY"
    assert issue.audit_key == expected_key
    assert issue.memory_uids == (first.uid, third.uid)
    assert issue.proposed_direction == "State which door each schedule governs."


def test_audit_fit_yes_creates_no_resolve_issue():
    context, _first, _second, _third = _context()

    class YesFitAuditProvider(MayFitAuditProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            if operation != FIT_JUDGMENT_OPERATION:
                return super().complete(
                    prompt,
                    operation=operation,
                    output_schema=output_schema,
                )
            payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
            aliases = [
                item["proposition_id"]
                for item in payload["questions"][0]["propositions"]
            ]
            return json.dumps(
                {
                    "overview": "The Context is compatible.",
                    "judgments": [
                        {
                            "question_id": "fit",
                            "verdict": "YES",
                            "reason": "Every Memory can jointly hold.",
                            "considered_proposition_ids": aliases,
                            "material_proposition_ids": [],
                            "consistent_reading": "",
                            "inconsistent_reading": "",
                        }
                    ],
                }
            )

    audit = run_quality_audit(context, YesFitAuditProvider)

    assert audit.fit is not None and audit.fit.verdict == "YES"
    assert all_audit_issue_keys(audit) == ()


def test_single_memory_audit_skips_set_level_fit():
    context = ops.init("audit/one-memory")
    ops.add(context, "The entrance opens at 8:00.")

    class FinderOnlyProvider:
        identity = ProviderIdentity(provider="test", model="finder-only")

        def complete(self, prompt, *, operation, output_schema=None):
            del prompt, output_schema
            assert operation.startswith("find_")
            return '{"findings": []}'

    audit = run_quality_audit(context, FinderOnlyProvider)

    assert audit.fit is None
    assert all_audit_issue_keys(audit) == ()


def test_schema_one_audit_remains_reviewable_without_fit():
    context, _first, _second, _third = _context()
    current = run_quality_audit(context, MayFitAuditProvider)
    legacy = current.to_dict()
    legacy["schema_version"] = 1
    legacy.pop("fit")

    restored = QualityAuditSession.from_dict(legacy)

    assert restored.fit is None
    assert restored.source.context_digest == current.source.context_digest
