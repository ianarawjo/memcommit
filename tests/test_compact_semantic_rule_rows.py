from __future__ import annotations

import json

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.commands.impact.process_local import (
    distill_impact_presentation,
    elaborate_impact_presentation,
)
from memcommit.adapters.console.commands.impact.sessions import render_impact_session_snapshot
from memcommit.application.operations.distill.model import DISTILL_OPERATION, DISTILL_PAYLOAD_MARKER
from memcommit.application.operations.distill.application import DistillRequest
from memcommit.application.operations.distill.runtime import execute_distill
from memcommit.application.operations.elaborate.model import (
    ELABORATE_OPERATION,
    ELABORATE_PAYLOAD_MARKER,
    ElaborateTargetContext,
    ElaborateTargetContextItem,
)
from memcommit.application.operations.elaborate.application import ElaborateRequest
from memcommit.application.operations.elaborate.runtime import execute_elaborate
from memcommit.adapters.console.commands.distill.proposal import distill_result_text
from memcommit.adapters.console.commands.elaborate.proposal import elaborate_result_text
from memcommit.adapters.console.commands.distill.workbench import (
    project_distill_clipboard,
)
from memcommit.adapters.console.commands.elaborate.viewer import project_elaborate_clipboard
from memcommit.persistence.store import MemoryStore
from tests.elaborate_validation_support import (
    passing_elaborate_validation_response,
)
from tests.distill_goal_fit_support import passing_distill_goal_fit_response


LONG_RULE = (
    "When generating a synthetic ticker, preserve every meaningful company "
    "qualifier and apply the reviewed mapping only after checking the exact "
    "security class; "
    + "retain this complete operational qualification " * 18
    + "without shortening the Rule."
)


class _LongDistillProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        validation = passing_distill_goal_fit_response(prompt, operation)
        if validation is not None:
            return validation
        assert operation == DISTILL_OPERATION
        payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
        aliases = [item["memory_id"] for item in payload["source"]["memories"]]
        return json.dumps(
            {
                "overview": "The complete evidence supports one long Rule.",
                "rules": [
                    {
                        "content": LONG_RULE,
                        "rationale": "The full rationale remains in Rule detail.",
                        "support_memory_ids": aliases[:1],
                        "boundary_memory_ids": aliases[1:2],
                    }
                ],
                "outside_memory_ids": [],
            }
        )


class _LongElaborateProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == ELABORATE_OPERATION
        return json.dumps(
            {
                "overview": "One complete Rule elaborates the Goal.",
                "rules": [
                    {
                        "content": LONG_RULE,
                        "rationale": "The full unverified rationale remains in detail.",
                    }
                ],
            }
        )


class _CaseElaborateProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        validation = passing_elaborate_validation_response(prompt, operation)
        if validation is not None:
            return validation
        assert operation == ELABORATE_OPERATION
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        target = payload.get("target_context")
        target_refs = (
            [item["target_id"] for item in target["items"]]
            if isinstance(target, dict)
            else None
        )
        return json.dumps(
            {
                "overview": "One boundary Case probes the supplied Rule.",
                "cases": [
                    {
                        "proposition": "A preferred share class remains explicit.",
                        "expected": "Keep the class qualifier.",
                        "rationale": "The class can identify another security.",
                        "case_role": "BOUNDARY",
                        "rule_checks": [
                            {
                                "source_rule_index": 1,
                                "evidence": "The qualifier remains explicit.",
                            }
                        ],
                        **(
                            {"target_context_refs": target_refs}
                            if target_refs is not None
                            else {}
                        ),
                    }
                ],
            }
        )


def _distill_result(isolated_store):
    store = MemoryStore()
    source = ops.init("compact-rules/source")
    ops.add(source, "Apple Inc. trades under AAPL.")
    ops.add(source, "Alphabet Class C trades under GOOG.")
    store.create_context(source)
    target = ops.init("compact-rules/target")
    store.create_context(target)
    result = execute_distill(
        DistillRequest(context_locator=source.name),
        store=store,
        provider_factory=_LongDistillProvider,
    )
    return result, target.name


def test_distill_plain_rule_row_keeps_the_complete_rule(isolated_store) -> None:
    result, _target_name = _distill_result(isolated_store)

    rendered = distill_result_text(result)
    row = next(line for line in rendered.splitlines() if line.startswith("[1] "))

    assert row == f"[1] {LONG_RULE} — SUPPORT 1 · BOUNDARY 1"
    assert "…" not in row
    assert "WHY ·" not in rendered
    complete_copy = project_distill_clipboard(result, whole_document=True).text
    assert "RULE DETAILS" in complete_copy
    assert "SUPPORT ·" in complete_copy
    assert "BOUNDARY ·" in complete_copy
    assert "WHY ·" in complete_copy


def test_distill_impact_rule_row_is_compact_without_losing_detail(
    isolated_store,
) -> None:
    result, target_name = _distill_result(isolated_store)
    presentation = distill_impact_presentation(result, target_name=target_name)

    rendered = render_impact_session_snapshot(presentation)
    row = next(line.strip() for line in rendered.splitlines() if line.strip().startswith("[1] "))

    assert row == f"[1] {LONG_RULE} — SUPPORT 1 · BOUNDARY 1"
    assert "…" not in row
    assert rendered.count(LONG_RULE) == 1
    assert "IMPACT · DISTILL ADD" not in rendered
    assert "[ADD]" not in rendered
    assert presentation.view.show_results is False
    assert presentation.show_impact_ledger is False
    assert presentation.view.items[0].summary == (
        "The full rationale remains in Rule detail."
    )
    assert "SUPPORT ·" in presentation.view.items[0].blocks[0].text
    assert "BOUNDARY ·" in presentation.view.items[0].blocks[0].text


def test_elaborate_rule_rows_keep_complete_unverified_content() -> None:
    result = execute_elaborate(
        ElaborateRequest(goal="Generate a qualified ticker Rule.", number=1),
        provider_factory=_LongElaborateProvider,
    )
    plain = elaborate_result_text(result)
    presentation = elaborate_impact_presentation(
        result,
        source_name="compact-rules/goal",
        target_name="compact-rules/target",
    )
    impact = render_impact_session_snapshot(presentation)

    expected = f"[1] {LONG_RULE} — SUGGESTED · UNVERIFIED"
    assert next(line for line in plain.splitlines() if line.startswith("[1] ")) == expected
    assert next(
        line.strip()
        for line in impact.splitlines()
        if line.strip().startswith("[1] ")
    ) == expected
    assert "…" not in expected
    assert impact.count(LONG_RULE) == 1
    assert "PROPOSED RULES · 1" in impact
    assert "IMPACT · ELABORATE ADD" not in impact
    assert "[ADD]" not in impact
    assert presentation.view.show_results is False
    assert presentation.show_impact_ledger is False
    assert presentation.view.items[0].summary == (
        "The full unverified rationale remains in detail."
    )
    complete_copy = project_elaborate_clipboard(result, whole_document=True).text
    assert "PROPOSAL DETAILS" in complete_copy
    assert "WHY ·" in complete_copy


def test_elaborate_case_impact_uses_one_compact_proposal_catalog() -> None:
    result = execute_elaborate(
        ElaborateRequest(
            rules=("Preserve an exact security class.",),
            number=1,
        ),
        provider_factory=_CaseElaborateProvider,
        target_context=ElaborateTargetContext(
            context_name="compact-rules/target",
            items=(
                ElaborateTargetContextItem(
                    alias="t1",
                    kind="MEMORY",
                    context_name="compact-rules/target",
                    memory_uid="ambient-memory",
                    content="This complete ambient Memory stays off the default canvas.",
                ),
            ),
        ),
    )
    presentation = elaborate_impact_presentation(
        result,
        source_name="compact-rules/rules",
        target_name="compact-rules/target",
    )
    rendered = render_impact_session_snapshot(presentation)

    case = result.analysis.cases[0]
    expected = f"[1] {case.proposition} — ALL 1 RULES · UNVERIFIED"

    assert presentation.view.list_label == "PROPOSED CASES"
    assert next(
        line.strip()
        for line in rendered.splitlines()
        if line.strip().startswith("[1] ")
    ) == expected
    assert rendered.count(case.proposition) == 1
    assert "1 TARGET AMBIENT" in rendered
    assert "This complete ambient Memory stays off the default canvas." not in rendered
    assert presentation.view.show_results is False
    assert presentation.show_impact_ledger is False
    assert "IMPACT · ELABORATE ADD · ENDPOINTS UNCHANGED" not in rendered
    assert "[ADD]" not in rendered
    assert "[CHANGE]" not in rendered
    assert "PROPOSAL DETAIL" not in rendered
    assert presentation.view.items[0].priority == "SUGGESTED"
    assert presentation.view.items[0].role == "OPTIONAL_REVIEW"
    assert presentation.view.items[0].show_summary_priority is False
    assert len(presentation.view.items[0].blocks) == 1
    assert presentation.view.items[0].blocks[0].heading == "RULE COVERAGE · ALL 1"
    assert presentation.view.items[0].blocks[0].text == (
        "EXPECTED · Keep the class qualifier.\nTARGET USED · t1"
    )
    assert presentation.view.results[0].rules == (
        "RULE COVERAGE · ALL 1",
        "RULE 1 · The qualifier remains explicit.",
        "EXPECTED · Keep the class qualifier.",
        "TARGET USED · t1",
    )
