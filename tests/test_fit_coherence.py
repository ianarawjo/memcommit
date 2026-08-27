from __future__ import annotations

import json

import memcommit.application.ops as ops
from memcommit.application.operations.fit.coherence import (
    FIT_COHERENCE_OPERATION,
    FIT_COHERENCE_PAYLOAD_MARKER,
    FitCoherenceError,
    execute_ground_coherence,
    freeze_ground_coherence,
    prepare_ground_coherence,
)
from memcommit.application.operations.ground.model import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_example,
    propose_ground_rule,
    upgrade_ground_to_propositions,
)


class _Provider:
    def __init__(self, *, omit_last: bool = False) -> None:
        self.omit_last = omit_last
        self.operation = ""
        self.prompt = ""

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.operation = operation
        self.prompt = prompt
        payload = json.loads(prompt.split(FIT_COHERENCE_PAYLOAD_MARKER, 1)[1])
        findings = []
        for check in payload["checks"]:
            status = "FIT"
            material: list[str] = []
            reason = "The frozen relation stays within the reviewed scope."
            if check["check_id"] == "context:e1":
                status = "UNDERDETERMINED"
                material = ["e1", "k2"]
                reason = (
                    "The scope requires a real sourced company, but this "
                    "Example has no source-linked Context Memory."
                )
            elif check["check_id"] == "vertical:goal-examples":
                status = "CONTRADICTS"
                material = ["g1", "e1"]
                reason = (
                    "The unsourced synthetic Example does not exercise the "
                    "Goal's real-company boundary."
                )
            findings.append(
                {
                    **check,
                    "status": status,
                    "material_aliases": material,
                    "reason": reason,
                }
            )
        if self.omit_last:
            findings.pop()
        return json.dumps(
            {
                "overview": "One initial Example needs review.",
                "findings": findings,
            }
        )


def _ground():
    raw = ops.init("ticker/raw")
    ops.add(
        raw,
        "Use actual United States listed companies and source-grounded tickers.",
    )
    examples = ops.init("ticker/examples")
    output = ops.init("ticker/output")
    session = bind_ground_workbench(
        create_ground_session(
            "ticker-context-fit",
            goal="Learn how real United States company ticker symbols are formed.",
        ),
        description="Refine ticker Rules against real sourced company Examples.",
        raw_context=raw,
        derived_context=examples,
        target_contexts=(output,),
        target_requirements=(
            GroundTargetSpec(
                context_name=output.name,
                description="Publish only reviewed ticker Rules.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    contexts = (raw, examples, output)
    session = propose_ground_rule(
        session,
        rule="Use actual companies and their observed tickers.",
        rationale="This is the reviewed scope boundary.",
        current_contexts=contexts,
        rule_provenance="USER_STATED",
    )
    session = propose_ground_example(
        session,
        proposition="North Star Energy Inc. has ticker NSE.",
        rationale="This initial synthetic Example still needs verification.",
        current_contexts=contexts,
    )
    return session, contexts


def test_ground_coherence_detects_context_and_vertical_example_issues() -> None:
    session, contexts = _ground()
    frozen = freeze_ground_coherence(session, contexts)
    prepared = prepare_ground_coherence(frozen)
    provider = _Provider()

    report = execute_ground_coherence(prepared, provider=provider)

    assert provider.operation == FIT_COHERENCE_OPERATION
    assert "Do not use pretrained knowledge as factual verification" in provider.prompt
    assert tuple(item.check_id for item in report.findings) == tuple(
        item.check_id for item in frozen.checks
    )
    issues = {
        item.check_id: item.status for item in report.findings if item.status != "FIT"
    }
    assert issues == {
        "context:e1": "UNDERDETERMINED",
        "vertical:goal-examples": "CONTRADICTS",
    }
    assert report.issue_count == 2
    assert type(report).from_dict(report.to_dict()) == report


def test_ground_coherence_rejects_incomplete_provider_coverage() -> None:
    session, contexts = _ground()
    prepared = prepare_ground_coherence(freeze_ground_coherence(session, contexts))

    try:
        execute_ground_coherence(prepared, provider=_Provider(omit_last=True))
    except FitCoherenceError as error:
        assert "omitted" in str(error)
    else:
        raise AssertionError("Incomplete Ground coherence unexpectedly passed.")
