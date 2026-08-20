from __future__ import annotations

import json

import memcommit.ops as ops
from memcommit.commands.impact_process_local import (
    distill_impact_presentation,
    elaborate_impact_presentation,
)
from memcommit.commands.impact_sessions import render_impact_session_snapshot
from memcommit.distill import DISTILL_OPERATION, DISTILL_PAYLOAD_MARKER
from memcommit.distill_application import DistillRequest
from memcommit.distill_runtime import execute_distill
from memcommit.elaborate import ELABORATE_OPERATION
from memcommit.elaborate_application import ElaborateRequest
from memcommit.elaborate_runtime import execute_elaborate
from memcommit.interfaces.cli.distill import distill_result_text
from memcommit.interfaces.cli.elaborate import elaborate_result_text
from memcommit.interfaces.tui.operations.distill import project_distill_clipboard
from memcommit.interfaces.tui.operations.elaborate import project_elaborate_clipboard
from memcommit.store import MemoryStore


LONG_RULE = (
    "When generating a synthetic ticker, preserve every meaningful company "
    "qualifier and apply the reviewed mapping only after checking the exact "
    "security class; "
    + "retain this complete operational qualification " * 18
    + "without shortening the Rule."
)


class _LongDistillProvider:
    def complete(self, prompt, *, operation, output_schema=None):
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
    assert presentation.view.items[0].summary == (
        "The full rationale remains in Rule detail."
    )
    assert "SUPPORT ·" in presentation.view.items[0].blocks[0].text
    assert "BOUNDARY ·" in presentation.view.items[0].blocks[0].text


def test_elaborate_rule_rows_keep_complete_unverified_content() -> None:
    result = execute_elaborate(
        ElaborateRequest(goal="Generate a qualified ticker Rule."),
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
    assert presentation.view.items[0].summary == (
        "The full unverified rationale remains in detail."
    )
    complete_copy = project_elaborate_clipboard(result, whole_document=True).text
    assert "PROPOSAL DETAILS" in complete_copy
    assert "WHY ·" in complete_copy
