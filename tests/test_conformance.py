from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.conformance import (
    CASE_CONFORMANCE_OPERATION,
    CONTEXT_CONFORMANCE_OPERATION,
    ConformanceError,
    ConformanceReport,
    ConformanceRule,
    ConformanceSubject,
    check_case_conformance,
    check_context_conformance,
)
from memcommit.conformance_runtime import freeze_context_conformance
from memcommit.conformance_runtime import freeze_ground_conformance
from memcommit.cli import app
import memcommit.commands.check_conformance as check_conformance_command
import memcommit.commands.audit as audit_command
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_case,
    propose_ground_rule,
)
from memcommit.provider_types import ProviderIdentity
from memcommit.store import MemoryStore
from memcommit.commands.audit import _run_quality_audit_checks
from memcommit.quality_audit import (
    QUALITY_AUDIT_LEGACY_SCHEMA_VERSION,
    QualityAuditSession,
    quality_audit_resolution_view,
)
from memcommit.quality_audit_store import QualityAuditStore
from memcommit.store import context_record_digest


def _uid() -> str:
    return str(uuid.uuid4())


class Provider:
    identity = ProviderIdentity(provider="test", model="conformance-model")

    def __init__(self, response: dict[str, object]):
        self.response = response
        self.calls = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        return json.dumps(self.response)


def _rule(content="Use uppercase initials."):
    return ConformanceRule(_uid(), "r1", content)


def test_case_conformance_withholds_expected_and_derives_exact_pass_fail():
    rule = _rule()
    first = ConformanceSubject(
        _uid(), "c1", "North Star Energy Inc.", "NSE", "FIT", (rule.uid,)
    )
    second = ConformanceSubject(
        _uid(), "c2", "Axiom AI Technologies Inc.", "AAT", "BOUNDARY", (rule.uid,)
    )
    provider = Provider(
        {
            "overview": "The Rule determines both predictions.",
            "predictions": [
                {
                    "case_id": "c1",
                    "disposition": "PREDICTED",
                    "predicted": "NSE",
                    "reason": "Uses initials.",
                },
                {
                    "case_id": "c2",
                    "disposition": "PREDICTED",
                    "predicted": "AAIT",
                    "reason": "Preserves AI as a component.",
                },
            ],
        }
    )

    report = check_case_conformance(
        source_label="GROUND · ticker",
        rules_label="GROUND RULES · ticker",
        rules=(rule,),
        subjects=(first, second),
        provider=provider,
    )

    prompt, operation, _schema = provider.calls[0]
    payload = json.loads(prompt.split("CONFORMANCE CASE PAYLOAD:\n", 1)[1])
    assert operation == CASE_CONFORMANCE_OPERATION
    assert "expected" not in json.dumps(payload)
    assert [item.status for item in report.case_judgments] == ["PASS", "FAIL"]
    assert report.issue_count == 1
    assert ConformanceReport.from_dict(report.to_dict()) == report


def test_case_conformance_rejects_omitted_or_duplicate_case():
    rule = _rule()
    cases = tuple(
        ConformanceSubject(_uid(), f"c{index}", f"Case {index}", "X", "FIT", (rule.uid,))
        for index in (1, 2)
    )
    provider = Provider(
        {
            "overview": "Invalid duplicate coverage.",
            "predictions": [
                {"case_id": "c1", "disposition": "PREDICTED", "predicted": "X", "reason": "One."},
                {"case_id": "c1", "disposition": "PREDICTED", "predicted": "X", "reason": "Again."},
            ],
        }
    )

    with pytest.raises(ConformanceError, match="exactly once"):
        check_case_conformance(
            source_label="ground", rules_label="rules", rules=(rule,),
            subjects=cases, provider=provider,
        )


def test_context_conformance_judges_each_rule_and_accounts_every_memory():
    first_rule = _rule("Use uppercase initials for multiword names.")
    second_rule = ConformanceRule(_uid(), "r2", "Append .B for Class B.")
    subjects = (
        ConformanceSubject(_uid(), "m000001", "North Star Energy → NSE", linked_rule_uids=(first_rule.uid, second_rule.uid)),
        ConformanceSubject(_uid(), "m000002", "North Star Energy Class B → NSE.B", linked_rule_uids=(first_rule.uid, second_rule.uid)),
        ConformanceSubject(_uid(), "m000003", "Unrelated note", linked_rule_uids=(first_rule.uid, second_rule.uid)),
    )
    provider = Provider(
        {
            "overview": "The Context conforms to both applicable Rules.",
            "judgments": [
                {"rule_id": "r1", "status": "CONFORMS", "evidence_memory_ids": ["m000001", "m000002"], "reason": "Both use initials."},
                {"rule_id": "r2", "status": "CONFORMS", "evidence_memory_ids": ["m000002"], "reason": "Class B uses .B."},
            ],
            "outside_memory_ids": ["m000003"],
        }
    )

    report = check_context_conformance(
        source_label="ticker/examples", rules_label="ticker/rules",
        rules=(first_rule, second_rule), subjects=subjects, provider=provider,
    )

    assert provider.calls[0][1] == CONTEXT_CONFORMANCE_OPERATION
    assert [item.status for item in report.context_judgments] == ["CONFORMS", "CONFORMS"]
    assert report.outside_subject_uids == (subjects[2].uid,)
    assert ConformanceReport.from_dict(report.to_dict()) == report


def test_context_conformance_rejects_silent_target_omission():
    rule = _rule()
    subjects = (
        ConformanceSubject(_uid(), "m000001", "One", linked_rule_uids=(rule.uid,)),
        ConformanceSubject(_uid(), "m000002", "Two", linked_rule_uids=(rule.uid,)),
    )
    provider = Provider(
        {
            "overview": "Incomplete.",
            "judgments": [
                {"rule_id": "r1", "status": "CONFORMS", "evidence_memory_ids": ["m000001"], "reason": "One."}
            ],
            "outside_memory_ids": [],
        }
    )

    with pytest.raises(ConformanceError, match="every target Memory"):
        check_context_conformance(
            source_label="target", rules_label="rules", rules=(rule,),
            subjects=subjects, provider=provider,
        )


def test_context_conformance_rejects_observed_status_without_evidence():
    rule = _rule()
    subject = ConformanceSubject(
        _uid(), "m000001", "North Star Energy -> NSE", linked_rule_uids=(rule.uid,)
    )
    provider = Provider(
        {
            "overview": "Unsupported conformance claim.",
            "judgments": [
                {
                    "rule_id": "r1",
                    "status": "CONFORMS",
                    "evidence_memory_ids": [],
                    "reason": "No evidence was cited.",
                }
            ],
            "outside_memory_ids": ["m000001"],
        }
    )

    with pytest.raises(ConformanceError, match="needs evidence"):
        check_context_conformance(
            source_label="target",
            rules_label="rules",
            rules=(rule,),
            subjects=(subject,),
            provider=provider,
        )


def test_freeze_context_conformance_uses_direct_memories_as_rules_and_subjects():
    target = ops.init("ticker/examples")
    target_memory = ops.add(target, "North Star Energy → NSE")
    rules = ops.init("ticker/rules")
    rule_memory = ops.add(rules, "Use uppercase initials.")

    frozen = freeze_context_conformance(target, rules)

    assert frozen.rules[0].uid == rule_memory.uid
    assert frozen.subjects[0].uid == target_memory.uid
    assert frozen.subjects[0].linked_rule_uids == (rule_memory.uid,)


def test_freeze_ground_conformance_uses_typed_expected_outputs():
    raw = ops.init("ticker/raw")
    candidates = ops.init("ticker/cases")
    first = ops.add(candidates, "North Star Energy Inc.")
    target = ops.init("ticker/output")
    session = bind_ground_workbench(
        create_ground_session("ticker-rules", goal="Generate synthetic tickers."),
        description="Test ticker-generation Rules.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish checked ticker outputs.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    contexts = (raw, candidates, target)
    session = propose_ground_rule(
        session,
        rule="Use uppercase initials after removing the legal suffix.",
        rationale="The example supplies the mapping.",
        current_contexts=contexts,
    )
    rule = session.items_of_kind("RULE")[0]
    session = propose_ground_case(
        session,
        rule_selector=rule.uid,
        case=first.content,
        source_context_uid=candidates.uid,
        source_memory_uid=first.uid,
        target_context_names=(target.name,),
        expected="NSE",
        rationale="The initials produce NSE.",
        current_contexts=contexts,
    )

    frozen = freeze_ground_conformance(session)

    assert frozen.rules[0].content.startswith("Use uppercase initials")
    assert frozen.subjects[0].content == "North Star Energy Inc."
    assert frozen.subjects[0].expected == "NSE"
    assert frozen.subjects[0].linked_rule_uids == tuple(
        item.uid for item in frozen.rules
    )


def test_check_conformance_cli_runs_the_shared_context_core(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    target = ops.init("ticker/examples")
    ops.add(target, "North Star Energy → NSE")
    rules = ops.init("ticker/rules")
    ops.add(rules, "Use uppercase initials for multiword names.")
    store.create_context(target)
    store.create_context(rules)
    provider = Provider(
        {
            "overview": "The example follows the Rule.",
            "judgments": [
                {
                    "rule_id": "r1",
                    "status": "CONFORMS",
                    "evidence_memory_ids": ["m000001"],
                    "reason": "NSE uses the three initials.",
                }
            ],
            "outside_memory_ids": [],
        }
    )
    monkeypatch.setattr(
        check_conformance_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = CliRunner().invoke(
        app,
        ["check-conformance", "ticker/examples", "--against", "ticker/rules"],
    )

    assert result.exit_code == 0, result.output
    assert "CHECK CONFORMANCE · CONTEXT" in result.output
    assert "r1 · CONFORMS" in result.output
    assert "NO CONTEXT CHANGES" in result.output


class AuditProvider:
    identity = ProviderIdentity(provider="test", model="audit-conformance-model")
    calls = []

    def complete(self, prompt, *, operation, output_schema=None):
        type(self).calls.append(operation)
        if operation.startswith("find_"):
            return '{"findings": []}'
        assert operation == CONTEXT_CONFORMANCE_OPERATION
        return json.dumps(
            {
                "overview": "The frozen Context conforms.",
                "judgments": [
                    {
                        "rule_id": "r1",
                        "status": "CONFORMS",
                        "evidence_memory_ids": ["m000001", "m000002"],
                        "reason": "Both Memories follow the Rule.",
                    }
                ],
                "outside_memory_ids": [],
            }
        )


def test_audit_optionally_embeds_the_same_context_conformance_report():
    target = ops.init("ticker/examples")
    ops.add(target, "North Star Energy → NSE")
    ops.add(target, "Blue River Holdings → BRH")
    rules = ops.init("ticker/rules")
    ops.add(rules, "Use uppercase initials for multiword names.")
    AuditProvider.calls = []

    session = _run_quality_audit_checks(
        target,
        AuditProvider,
        conformance_rules=rules,
        interactive=False,
        interval=0.001,
    )

    assert AuditProvider.calls == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
        CONTEXT_CONFORMANCE_OPERATION,
    ]
    assert session.conformance is not None
    assert session.conformance.context_judgments[0].status == "CONFORMS"
    assert "SAVED · 4/4 CHECKS" in quality_audit_resolution_view(session).status
    assert QualityAuditSession.from_dict(session.to_dict()).conformance == session.conformance


def test_audit_cli_against_rules_saves_one_read_only_four_check_report(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    target = ops.init("ticker/examples")
    ops.add(target, "North Star Energy -> NSE")
    ops.add(target, "Blue River Holdings -> BRH")
    rules = ops.init("ticker/rules")
    ops.add(rules, "Use uppercase initials for multiword names.")
    store.create_context(target)
    store.create_context(rules)
    target_before = context_record_digest(store.load_direct(target.name))
    rules_before = context_record_digest(store.load_direct(rules.name))
    AuditProvider.calls = []
    monkeypatch.setattr(
        audit_command,
        "connect_codex_chatgpt_provider",
        AuditProvider,
    )

    result = CliRunner().invoke(
        app,
        [
            "audit",
            "--context",
            target.name,
            "--against",
            rules.name,
            "--snapshot",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "SAVED · 4/4 CHECKS" in result.output
    assert "CONFORMANCE · COMPLETE" in result.output
    saved = QualityAuditStore(store).list()
    assert len(saved) == 1
    assert saved[0].conformance is not None
    assert context_record_digest(store.load_direct(target.name)) == target_before
    assert context_record_digest(store.load_direct(rules.name)) == rules_before
    assert store.list_checkpoints(target.name) == []
    assert store.list_checkpoints(rules.name) == []


def test_audit_still_reads_legacy_three_check_records_without_conformance():
    target = ops.init("audit/legacy")
    ops.add(target, "One Memory.")
    AuditProvider.calls = []
    session = _run_quality_audit_checks(
        target,
        AuditProvider,
        interactive=False,
        interval=0.001,
    )
    legacy = session.to_dict()
    legacy["schema_version"] = QUALITY_AUDIT_LEGACY_SCHEMA_VERSION
    legacy.pop("conformance")

    restored = QualityAuditSession.from_dict(legacy)

    assert restored.conformance is None
    assert "SAVED · 3/3 CHECKS" in quality_audit_resolution_view(restored).status
