from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.commands.fit as fit_command
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.fit import (
    FitError,
    FitExample,
    FitReport,
    FitRule,
    fit_ground_examples,
)
from memcommit.fit_runtime import execute_and_save_ground_fit, freeze_ground_fit
from memcommit.fit_store import FitStore
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_case,
    propose_ground_example,
    propose_ground_rule,
    upgrade_ground_to_propositions,
)
from memcommit.store import MemoryStore, ground_session_record_digest


def _uid() -> str:
    return str(uuid.uuid4())


class _Provider:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.prompt = ""
        self.operation = ""

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.prompt = prompt
        self.operation = operation
        return json.dumps(self.response)


def _rule(statement: str = "Use the first four letters in uppercase.") -> FitRule:
    return FitRule(_uid(), "r1", statement)


def test_exact_output_fit_withholds_expected_and_converts_failure() -> None:
    rule = _rule()
    example = FitExample(
        _uid(),
        "e1",
        "Axiom AI Technologies -> AAT",
        "EXACT_OUTPUT",
        (rule.uid,),
        input_text="Axiom AI Technologies",
        expected_output="AAT",
    )
    provider = _Provider(
        {
            "overview": "The rule yields four letters.",
            "predictions": [
                {
                    "case_id": "e1",
                    "disposition": "PREDICTED",
                    "predicted": "AXIO",
                    "reason": "The rule explicitly selects four letters.",
                }
            ],
        }
    )
    report = fit_ground_examples(
        ground_uid=_uid(),
        ground_name="ticker",
        ground_revision=3,
        ground_digest="a" * 64,
        rules=(rule,),
        examples=(example,),
        provider=provider,
    )

    assert report.judgments[0].status == "CONTRADICTS"
    assert report.judgments[0].observed == "AXIO"
    assert '"expected"' not in provider.prompt
    assert "AAT" not in provider.prompt
    assert FitReport.from_dict(report.to_dict()) == report


def test_proposition_fit_accounts_for_observation_counterexample() -> None:
    rule = _rule("The sky is always blue.")
    example = FitExample(
        _uid(),
        "e1",
        "On August 15 the sky was yellow.",
        "PROPOSITION",
        (rule.uid,),
    )
    provider = _Provider(
        {
            "overview": "The observation conflicts with the universal claim.",
            "judgments": [
                {
                    "example_id": "e1",
                    "status": "CONTRADICTS",
                    "reason": "One yellow observation refutes always blue.",
                }
            ],
        }
    )
    report = fit_ground_examples(
        ground_uid=_uid(),
        ground_name="sky",
        ground_revision=1,
        ground_digest="b" * 64,
        rules=(rule,),
        examples=(example,),
        provider=provider,
    )

    assert report.judgments[0].status == "CONTRADICTS"
    assert provider.operation == "fit_ground_propositions"
    assert "Do not invent a cause" in provider.prompt
    assert "return UNDERDETERMINED rather than supplying" in provider.prompt
    assert "which characters it contributes" in provider.prompt


def test_fit_rejects_mixed_projection_and_incomplete_coverage() -> None:
    rule = _rule()
    exact = FitExample(
        _uid(), "e1", "Apple -> APPL", "EXACT_OUTPUT", (rule.uid,),
        input_text="Apple", expected_output="APPL",
    )
    proposition = FitExample(
        _uid(), "e2", "Apple maps to APPL.", "PROPOSITION", (rule.uid,)
    )
    with pytest.raises(FitError, match="cannot mix"):
        fit_ground_examples(
            ground_uid=_uid(),
            ground_name="ticker",
            ground_revision=1,
            ground_digest="c" * 64,
            rules=(rule,),
            examples=(exact, proposition),
            provider=_Provider({}),
        )

    with pytest.raises(FitError, match="omitted"):
        fit_ground_examples(
            ground_uid=_uid(),
            ground_name="ticker",
            ground_revision=1,
            ground_digest="c" * 64,
            rules=(rule,),
            examples=(proposition,),
            provider=_Provider({"overview": "none", "judgments": []}),
        )


def _saved_ground(store: MemoryStore):
    raw = ops.init("ticker/raw")
    candidates = ops.init("ticker/cases")
    case = ops.add(candidates, "Axiom AI Technologies")
    target = ops.init("ticker/output")
    for context in (raw, candidates, target):
        store.create_context(context)
    session = bind_ground_workbench(
        create_ground_session("ticker", goal="Generate reviewed ticker symbols."),
        description="Fit ticker-generation Rules to concrete Examples.",
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
        rule="Use uppercase initials after removing legal suffixes.",
        rationale="This is the current generalized ticker policy.",
        current_contexts=contexts,
    )
    rule = session.items_of_kind("RULE")[0]
    session = propose_ground_case(
        session,
        rule_selector=rule.uid,
        case=case.content,
        source_context_uid=candidates.uid,
        source_memory_uid=case.uid,
        target_context_names=(target.name,),
        expected="AAT",
        rationale="This is the reviewed concrete outcome.",
        current_contexts=contexts,
    )
    store.save_ground_session(session)
    return session, contexts


def _passing_provider() -> _Provider:
    return _Provider(
        {
            "overview": "The active Rule reproduces the reviewed Example.",
            "predictions": [
                {
                    "case_id": "e1",
                    "disposition": "PREDICTED",
                    "predicted": "AAT",
                    "reason": "The initials produce the expected symbol.",
                }
            ],
        }
    )


def test_version_three_fit_uses_native_propositions_and_explicit_rule_scope(
    isolated_store,
) -> None:
    store = MemoryStore()
    session, contexts = _saved_ground(store)
    session = upgrade_ground_to_propositions(session)
    session = propose_ground_rule(
        session,
        rule="Preserve an explicitly reviewed symbol exception.",
        rationale="A second active Rule makes scope selection observable.",
        current_contexts=contexts,
    )
    rules = session.items_of_kind("RULE")
    session = propose_ground_example(
        session,
        proposition="On August 15 the sky over Toronto was yellow.",
        rationale="An outputless observation uses all active Rules by default.",
        current_contexts=contexts,
    )
    session = propose_ground_example(
        session,
        proposition="Apple Inc. may be represented by AAPL.",
        rationale="This Example explicitly exercises only the second Rule.",
        current_contexts=contexts,
        rule_selectors=(rules[1].uid,),
        input_text="Apple Inc.",
        expected_output="AAPL",
    )

    frozen = freeze_ground_fit(session)

    assert {example.projection for example in frozen.examples} == {
        "PROPOSITION"
    }
    assert all(
        example.input_text is None and example.expected_output is None
        for example in frozen.examples
    )
    by_statement = {example.statement: example for example in frozen.examples}
    assert by_statement[
        "On August 15 the sky over Toronto was yellow."
    ].rule_uids == tuple(rule.uid for rule in frozen.rules)
    assert by_statement[
        "Apple Inc. may be represented by AAPL."
    ].rule_uids == (rules[1].uid,)


def test_fit_store_publishes_current_receipt_then_reports_stale(
    isolated_store,
) -> None:
    store = MemoryStore()
    session, contexts = _saved_ground(store)
    report = execute_and_save_ground_fit(
        store=store,
        ground_name=session.contract_name,
        provider_factory=_passing_provider,
    )
    receipt = FitStore(store).latest_for_ground(session)

    assert receipt is not None and receipt.current
    assert receipt.report.uid == report.uid
    assert FitStore(store).load(report.uid) == report

    revised = propose_ground_rule(
        session,
        rule="Preserve an established short symbol when explicitly supplied.",
        rationale="A later Rule changes the fitted Rule set.",
        current_contexts=contexts,
    )
    store.save_ground_session(
        revised,
        replace=True,
        expected_uid=session.uid,
        expected_revision=session.revision,
        expected_digest=ground_session_record_digest(session),
    )
    stale = FitStore(store).latest_for_ground(revised)

    assert stale is not None and not stale.current
    assert stale.report.uid == report.uid


def test_fit_store_rejects_publication_after_ground_changes(
    isolated_store,
) -> None:
    store = MemoryStore()
    session, contexts = _saved_ground(store)
    report = fit_ground_examples(
        ground_uid=session.uid,
        ground_name=session.contract_name,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        rules=(
            FitRule(
                session.items_of_kind("RULE")[0].uid,
                "r1",
                session.items_of_kind("RULE")[0].content,
            ),
        ),
        examples=(
            FitExample(
                session.items_of_kind("CASE")[0].uid,
                "e1",
                "Axiom AI Technologies -> AAT",
                "EXACT_OUTPUT",
                (session.items_of_kind("RULE")[0].uid,),
                input_text="Axiom AI Technologies",
                expected_output="AAT",
            ),
        ),
        provider=_passing_provider(),
    )
    revised = propose_ground_rule(
        session,
        rule="A later Rule.",
        rationale="Makes the report stale before publication.",
        current_contexts=contexts,
    )
    store.save_ground_session(revised, replace=True)

    with pytest.raises(FitError, match="changed before"):
        FitStore(store).save(report)


def test_mem_fit_runs_and_reopens_immutable_receipt(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    session, _contexts = _saved_ground(store)
    monkeypatch.setattr(
        fit_command,
        "connect_semantic_provider",
        _passing_provider,
    )

    result = CliRunner().invoke(app, ["fit", session.contract_name])

    assert result.exit_code == 0, result.output
    assert result.output == "✓ ticker · 1/1\n"
    receipt = FitStore(store).latest_for_ground(session)
    assert receipt is not None

    reopened = CliRunner().invoke(
        app,
        ["fit", session.contract_name, "--receipt", receipt.report.uid],
    )
    assert reopened.exit_code == 0, reopened.output
    assert reopened.output == "✓ ticker · 1/1\n"


def test_mem_fit_plain_flag_preserves_one_line_noninteractive_result(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    session, _contexts = _saved_ground(store)
    monkeypatch.setattr(
        fit_command,
        "connect_semantic_provider",
        _passing_provider,
    )

    result = CliRunner().invoke(app, ["fit", session.contract_name, "--plain"])

    assert result.exit_code == 0, result.output
    assert result.output == "✓ ticker · 1/1\n"


def test_mem_fit_forced_tui_fails_before_opening_storage(monkeypatch) -> None:
    def fail_store(*_args, **_kwargs):
        raise AssertionError("Fit must validate the TUI route before storage")

    monkeypatch.setattr(fit_command, "MemoryStore", fail_store)

    result = CliRunner().invoke(app, ["fit", "ticker", "--tui"])

    assert result.exit_code == 1
    assert "Interactive presentation requires a TTY" in result.output
