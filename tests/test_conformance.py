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
            "judgments": [
                {"rule_id": "r1", "status": "CONFORMS", "evidence_memory_ids": ["m000001", "m000002"], "nonconforming_cases": [], "reason": "Both use initials."},
                {"rule_id": "r2", "status": "CONFORMS", "evidence_memory_ids": ["m000002"], "nonconforming_cases": [], "reason": "Class B uses .B."},
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
    assert [item.status for item in report.context_example_judgments] == [
        "CONFORMS",
        "CONFORMS",
        "NOT_APPLICABLE",
    ]
    assert report.outside_subject_uids == (subjects[2].uid,)
    assert check_conformance_command.render_conformance(report).startswith(
        "CONFORMANCE · 2/2 EXAMPLES CONFORM · 2/2 RULES MET · "
        "[EXAMPLES ticker/examples] · [RULES ticker/rules] · 1 EXAMPLE N/A"
    )
    assert ConformanceReport.from_dict(report.to_dict()) == report


def test_context_conformance_renders_rule_summary_and_exact_failing_cases():
    shape_rule = _rule("Use exactly three tokens with lowercase is.")
    initial_rule = ConformanceRule(
        _uid(), "r2", "The word must begin with the initial letter."
    )
    subjects = (
        ConformanceSubject(
            _uid(),
            "m000001",
            "a is apple",
            linked_rule_uids=(shape_rule.uid, initial_rule.uid),
        ),
        ConformanceSubject(
            _uid(),
            "m000002",
            "b is apple",
            linked_rule_uids=(shape_rule.uid, initial_rule.uid),
        ),
    )
    provider = Provider(
        {
            "judgments": [
                {
                    "rule_id": "r1",
                    "status": "CONFORMS",
                    "evidence_memory_ids": ["m000001", "m000002"],
                    "nonconforming_cases": [],
                    "reason": "Both cases use the required shape.",
                },
                {
                    "rule_id": "r2",
                    "status": "PARTIALLY_CONFORMS",
                    "evidence_memory_ids": ["m000001", "m000002"],
                    "nonconforming_cases": [
                        {
                            "memory_id": "m000002",
                            "reason": "The word apple does not begin with b.",
                        }
                    ],
                    "reason": "The second word does not begin with b.",
                },
            ],
            "outside_memory_ids": [],
        }
    )

    report = check_context_conformance(
        source_label="letters/examples",
        rules_label="letters/rules",
        rules=(shape_rule, initial_rule),
        subjects=subjects,
        provider=provider,
    )
    rendered = check_conformance_command.render_conformance(report)

    assert "ASSESSMENT OVERVIEW" not in rendered
    assert "WHAT MEM UNDERSTOOD" not in rendered
    assert (
        "CONFORMANCE · 1/2 EXAMPLES CONFORM · 1/2 RULES MET · "
        "[EXAMPLES letters/examples] · [RULES letters/rules]"
        in rendered
    )
    assert (
        "! VIOLATES · [EXAMPLE m000002] b is apple · "
        "[RULE r2] The word must begin with the initial letter. · WHY · "
        "The word apple does not begin with b."
        in rendered
    )
    assert len(rendered.splitlines()) == 2
    assert "NONCONFORMING CASES" not in rendered
    assert "  RULE ·" not in rendered
    assert "  EVIDENCE ·" not in rendered
    assert "  WHY ·" not in rendered
    assert "OUTSIDE RULE JUDGMENTS" not in rendered


def test_context_conformance_still_reads_schema_one_without_case_details():
    rule = _rule()
    subject = ConformanceSubject(
        _uid(), "m000001", "A -> A", linked_rule_uids=(rule.uid,)
    )
    report = check_context_conformance(
        source_label="legacy/examples",
        rules_label="legacy/rules",
        rules=(rule,),
        subjects=(subject,),
        provider=Provider(
            {
                "judgments": [
                    {
                        "rule_id": "r1",
                        "status": "CONFORMS",
                        "evidence_memory_ids": ["m000001"],
                        "nonconforming_cases": [],
                        "reason": "It follows the Rule.",
                    }
                ],
                "outside_memory_ids": [],
            }
        ),
    )
    legacy = report.to_dict()
    legacy["schema_version"] = 1
    legacy["ruleset_version"] = "conformance-v1"
    for judgment in legacy["context_judgments"]:
        judgment.pop("nonconforming_cases")

    restored = ConformanceReport.from_dict(legacy)

    assert restored.schema_version == 1
    assert restored.context_judgments[0].nonconforming_subject_uids == ()
    assert restored.to_dict() == legacy


def test_context_conformance_still_reads_schema_two_case_identities():
    rule = _rule("Use lowercase letters.")
    subject = ConformanceSubject(
        _uid(), "m000001", "A is apple", linked_rule_uids=(rule.uid,)
    )
    report = check_context_conformance(
        source_label="legacy/examples",
        rules_label="legacy/rules",
        rules=(rule,),
        subjects=(subject,),
        provider=Provider(
            {
                "judgments": [
                    {
                        "rule_id": "r1",
                        "status": "VIOLATES",
                        "evidence_memory_ids": ["m000001"],
                        "nonconforming_cases": [
                            {
                                "memory_id": "m000001",
                                "reason": "The initial letter is uppercase.",
                            }
                        ],
                        "reason": "The observed initial is uppercase.",
                    }
                ],
                "outside_memory_ids": [],
            }
        ),
    )
    schema_two = report.to_dict()
    schema_two["schema_version"] = 2
    schema_two["ruleset_version"] = "conformance-v1"
    for judgment in schema_two["context_judgments"]:
        cases = judgment.pop("nonconforming_cases")
        judgment["nonconforming_subject_uids"] = [
            case["subject_uid"] for case in cases
        ]

    restored = ConformanceReport.from_dict(schema_two)

    assert restored.schema_version == 2
    assert restored.context_judgments[0].nonconforming_subject_uids == (
        subject.uid,
    )
    assert restored.context_judgments[0].nonconforming_cases[0].reason is None
    assert restored.to_dict() == schema_two


def test_context_conformance_renders_unresolved_example_reason_inline():
    rule = _rule("Use the reviewed publication date.")
    subject = ConformanceSubject(
        _uid(), "m000001", "Publish it next Friday.", linked_rule_uids=(rule.uid,)
    )
    report = check_context_conformance(
        source_label="dates/examples",
        rules_label="dates/rules",
        rules=(rule,),
        subjects=(subject,),
        provider=Provider(
            {
                "judgments": [
                    {
                        "rule_id": "r1",
                        "status": "INSUFFICIENT_EVIDENCE",
                        "evidence_memory_ids": ["m000001"],
                        "nonconforming_cases": [],
                        "reason": "The reviewed publication date is not supplied.",
                    }
                ],
                "outside_memory_ids": [],
            }
        ),
    )

    rendered = check_conformance_command.render_conformance(report)

    assert rendered.splitlines() == [
        "CONFORMANCE · 0/1 EXAMPLES CONFORM · 0/1 RULES MET · "
        "[EXAMPLES dates/examples] · [RULES dates/rules]",
        "? INSUFFICIENT_EVIDENCE · [EXAMPLE m000001] Publish it next Friday. · "
        "[RULE r1] Use the reviewed publication date. · WHY · "
        "The reviewed publication date is not supplied.",
    ]


def test_context_conformance_rejects_silent_target_omission():
    rule = _rule()
    subjects = (
        ConformanceSubject(_uid(), "m000001", "One", linked_rule_uids=(rule.uid,)),
        ConformanceSubject(_uid(), "m000002", "Two", linked_rule_uids=(rule.uid,)),
    )
    provider = Provider(
        {
            "judgments": [
                {"rule_id": "r1", "status": "CONFORMS", "evidence_memory_ids": ["m000001"], "nonconforming_cases": [], "reason": "One."}
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
            "judgments": [
                {
                    "rule_id": "r1",
                    "status": "CONFORMS",
                    "evidence_memory_ids": [],
                    "nonconforming_cases": [],
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
            "judgments": [
                {
                    "rule_id": "r1",
                    "status": "CONFORMS",
                    "evidence_memory_ids": ["m000001"],
                    "nonconforming_cases": [],
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
    assert (
        "CONFORMANCE · 1/1 EXAMPLES CONFORM · 1/1 RULES MET · "
        "[EXAMPLES ticker/examples] · [RULES ticker/rules]"
        in result.output
    )
    assert "  RULE ·" not in result.output
    assert "  EVIDENCE ·" not in result.output
    assert "  WHY ·" not in result.output
    assert "OUTSIDE RULE JUDGMENTS" not in result.output
    assert result.output.count("\n") == 1


def _install_context_conformance_cli_fixture(monkeypatch):
    store = MemoryStore()
    target = ops.init("ticker/examples")
    ops.add(target, "North Star Energy → NSE")
    rules = ops.init("ticker/rules")
    ops.add(rules, "Use uppercase initials for multiword names.")
    store.create_context(target)
    store.create_context(rules)
    provider = Provider(
        {
            "judgments": [
                {
                    "rule_id": "r1",
                    "status": "CONFORMS",
                    "evidence_memory_ids": ["m000001"],
                    "nonconforming_cases": [],
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
    return store, target, rules, provider


@pytest.mark.parametrize(
    "arguments",
    [
        ["--rule", "ticker/rules", "--example", "ticker/examples"],
        ["--rule", "ticker/rules", "--case", "ticker/examples"],
        ["--from", "ticker/rules", "--to", "ticker/examples"],
    ],
)
def test_check_conformance_role_and_direction_aliases_share_context_route(
    isolated_store,
    monkeypatch,
    arguments,
):
    _store, _target, _rules, provider = _install_context_conformance_cli_fixture(
        monkeypatch
    )

    result = CliRunner().invoke(app, ["check-conformance", *arguments])

    assert result.exit_code == 0, result.output
    assert "[EXAMPLES ticker/examples]" in result.output
    assert "[RULES ticker/rules]" in result.output
    assert len(provider.calls) == 1


def test_check_conformance_from_accepts_unique_local_rule_memory_uid(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    target = ops.init("ticker/examples")
    ops.add(target, "North Star Energy → NSE")
    rules = ops.init("ticker/rules")
    rule = ops.add(rules, "Use uppercase initials for multiword names.")
    store.create_context(target)
    store.create_context(rules)
    store.set_current(target.name)
    provider = Provider(
        {
            "judgments": [
                {
                    "rule_id": "r1",
                    "status": "CONFORMS",
                    "evidence_memory_ids": ["m000001"],
                    "nonconforming_cases": [],
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
        ["check-conformance", "--from", rule.uid[:8] + "\N{NO-BREAK SPACE}"],
    )

    assert result.exit_code == 0, result.output
    assert f"[RULES MEMORY {rules.name}:{rule.uid[:8]}]" in result.output
    prompt, operation, _schema = provider.calls[0]
    payload = json.loads(prompt.split("CONFORMANCE CONTEXT PAYLOAD:\n", 1)[1])
    assert operation == CONTEXT_CONFORMANCE_OPERATION
    assert payload["rules"] == [{"rule_id": "r1", "content": rule.content}]
    assert payload["target_context"]["name"] == target.name


def test_check_conformance_from_accepts_literal_rule_text(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    target = ops.init("ticker/examples")
    ops.add(target, "North Star Energy → NSE")
    store.create_context(target)
    store.set_current(target.name)
    literal = "Use uppercase initials for multiword names."
    provider = Provider(
        {
            "judgments": [
                {
                    "rule_id": "r1",
                    "status": "CONFORMS",
                    "evidence_memory_ids": ["m000001"],
                    "nonconforming_cases": [],
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
        ["check-conformance", "--from", literal],
    )

    assert result.exit_code == 0, result.output
    assert f"[RULES TEXT {literal}]" in result.output
    prompt, _operation, _schema = provider.calls[0]
    payload = json.loads(prompt.split("CONFORMANCE CONTEXT PAYLOAD:\n", 1)[1])
    assert payload["rules"] == [{"rule_id": "r1", "content": literal}]


def test_check_conformance_revalidates_selected_rule_memory(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    target = ops.init("ticker/examples")
    ops.add(target, "North Star Energy → NSE")
    rules = ops.init("ticker/rules")
    rule = ops.add(rules, "Use uppercase initials for multiword names.")
    store.create_context(target)
    store.create_context(rules)
    store.set_current(target.name)

    class MutatingProvider(Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            response = super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            ops.edit(rules, rule.uid, "Use a different Rule now.")
            store.save(rules)
            return response

    provider = MutatingProvider(
        {
            "judgments": [
                {
                    "rule_id": "r1",
                    "status": "CONFORMS",
                    "evidence_memory_ids": ["m000001"],
                    "nonconforming_cases": [],
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
        ["check-conformance", "--from", rule.uid[:7]],
    )

    assert result.exit_code == 1
    assert "Rules source changed during Conformance" in result.output
    assert "CONFORMANCE ·" not in result.output


def test_check_conformance_uid_shaped_rule_is_strict_before_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    target = ops.init("ticker/examples")
    ops.add(target, "North Star Energy → NSE")
    store.create_context(target)
    store.set_current(target.name)
    provider = Provider({})
    monkeypatch.setattr(
        check_conformance_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = CliRunner().invoke(
        app,
        ["check-conformance", "--from", "deadbeef"],
    )

    assert result.exit_code == 1
    assert "No directly owned Memory" in result.output
    assert provider.calls == []


@pytest.mark.parametrize(
    ("arguments", "current_name"),
    [
        (["--rule", "ticker/rules"], "ticker/examples"),
        (["--from", "ticker/rules"], "ticker/examples"),
        (["--example", "ticker/examples"], "ticker/rules"),
        (["--to", "ticker/examples"], "ticker/rules"),
    ],
)
def test_check_conformance_alias_endpoints_fill_from_one_current_snapshot(
    isolated_store,
    monkeypatch,
    arguments,
    current_name,
):
    store, _target, _rules, provider = _install_context_conformance_cli_fixture(
        monkeypatch
    )
    store.set_current(current_name)

    result = CliRunner().invoke(app, ["check-conformance", *arguments])

    assert result.exit_code == 0, result.output
    assert "[EXAMPLES ticker/examples]" in result.output
    assert "[RULES ticker/rules]" in result.output
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            [
                "--rule",
                "ticker/rules",
                "--from",
                "ticker/rules",
                "--example",
                "ticker/examples",
            ],
            "Use only one of --against, --rule, or --from",
        ),
        (
            [
                "--rule",
                "ticker/rules",
                "--case",
                "ticker/examples",
                "--to",
                "ticker/examples",
            ],
            "Use only one of --example, --case, or --to",
        ),
        (
            [
                "ticker/examples",
                "--rule",
                "ticker/rules",
                "--case",
                "ticker/examples",
            ],
            "Target positional operand or --example/--case/--to",
        ),
        (
            ["--ground", "ticker", "--rule", "ticker/rules"],
            "--ground cannot be combined with direct operands",
        ),
    ],
)
def test_check_conformance_rejects_conflicting_aliases_before_provider(
    isolated_store,
    monkeypatch,
    arguments,
    message,
):
    _store, _target, _rules, provider = _install_context_conformance_cli_fixture(
        monkeypatch
    )

    result = CliRunner().invoke(app, ["check-conformance", *arguments])

    assert result.exit_code == 1
    assert message in result.output
    assert provider.calls == []


def test_check_conformance_legacy_positional_target_still_requires_rules(
    isolated_store,
    monkeypatch,
):
    store, _target, _rules, provider = _install_context_conformance_cli_fixture(
        monkeypatch
    )
    store.set_current("ticker/rules")

    result = CliRunner().invoke(
        app,
        ["check-conformance", "ticker/examples"],
    )

    assert result.exit_code == 1
    assert "requires a Rules or Subject endpoint" in result.output
    assert provider.calls == []


def test_check_conformance_help_exposes_role_and_direction_aliases():
    result = CliRunner().invoke(app, ["check-conformance", "--help"])

    assert result.exit_code == 0
    assert "--against,--rule,--from" in result.output
    assert "--example,--case,--to" in result.output
    assert "RULES_SOURCE" in result.output
    assert "SUBJECT_CONTEXT" in result.output
    assert "Memory UID/prefix" in result.output
    assert "text:VALUE" in result.output


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
                "judgments": [
                    {
                        "rule_id": "r1",
                        "status": "CONFORMS",
                        "evidence_memory_ids": ["m000001", "m000002"],
                        "nonconforming_cases": [],
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


@pytest.mark.parametrize("rules_option", ["--against", "--rule"])
def test_audit_cli_rules_alias_saves_one_read_only_four_check_report(
    isolated_store,
    monkeypatch,
    rules_option,
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
            rules_option,
            rules.name,
            "--snapshot",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "SAVED · 4/4 CHECKS" in result.output
    assert "CONFORMANCE · FINISHED" in result.output
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
    for check in legacy["checks"]:
        if check["kind"] == "conflicts":
            check["ruleset_version"] = "conflict-v1-draft"

    restored = QualityAuditSession.from_dict(legacy)

    assert restored.conformance is None
    assert "SAVED · 3/3 CHECKS" in quality_audit_resolution_view(restored).status
