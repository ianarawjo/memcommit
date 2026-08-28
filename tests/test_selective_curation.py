import json

import pytest

from memcommit.application.capabilities.semantic.selective_curation import (
    CriterionFrame,
    CurationBatch,
    CurationItem,
    SelectiveCurationError,
    build_provider_frame,
    curation_output_schema,
    decode_curation_response,
)


def _frame():
    batch = CurationBatch(
        source_label="source",
        source=(
            CurationItem("one", "Keep this.", "source"),
            CurationItem("two", "Remove part and retain this.", "source"),
        ),
        criteria=CriterionFrame(
            kind="INSTRUCTION",
            label="Forget request",
            items=(CurationItem("request", "Forget the removable part."),),
        ),
    )
    return build_provider_frame(batch)


def test_instruction_and_memory_criteria_share_one_alias_safe_batch_contract():
    frame = _frame()

    assert frame.payload["criteria"]["kind"] == "INSTRUCTION"
    assert [item["item_id"] for item in frame.payload["source"]["memories"]] == [
        "s1",
        "s2",
    ]
    schema = curation_output_schema(frame, ("KEEP", "EDIT", "DELETE"))
    assert schema["properties"]["candidates"]["items"]["properties"]["decision"][
        "enum"
    ] == ["KEEP", "EDIT", "DELETE"]


def test_decode_requires_complete_source_coverage_and_shared_content_invariants():
    frame = _frame()
    raw = json.dumps(
        {
            "overview": "One item stays and one is edited.",
            "candidates": [
                {
                    "source_memory_id": "s1",
                    "decision": "KEEP",
                    "proposed_content": "Keep this.",
                    "rationale": "The request does not cover it.",
                    "criterion_item_ids": ["k1"],
                },
                {
                    "source_memory_id": "s2",
                    "decision": "EDIT",
                    "proposed_content": "Retain this.",
                    "rationale": "Only part is covered.",
                    "criterion_item_ids": ["k1"],
                },
            ],
        }
    )

    analysis = decode_curation_response(
        raw,
        frame,
        variant_actions={"KEEP": "KEEP", "EDIT": "TRANSFORM", "DELETE": "DROP"},
    )

    assert [decision.source_uid for decision in analysis.decisions] == ["one", "two"]
    assert [decision.action for decision in analysis.decisions] == ["KEEP", "TRANSFORM"]

    incomplete = json.loads(raw)
    incomplete["candidates"].pop()
    with pytest.raises(SelectiveCurationError, match="cover every Source"):
        decode_curation_response(
            json.dumps(incomplete),
            frame,
            variant_actions={
                "KEEP": "KEEP",
                "EDIT": "TRANSFORM",
                "DELETE": "DROP",
            },
        )


@pytest.mark.parametrize(
    ("decision", "content", "message"),
    [
        ("KEEP", "changed", "KEEP must preserve"),
        ("EDIT", "", "TRANSFORM requires"),
        ("DELETE", "still here", "DROP must have empty"),
    ],
)
def test_decode_rejects_variant_content_mismatches(decision, content, message):
    frame = _frame()
    candidates = [
        {
            "source_memory_id": "s1",
            "decision": decision,
            "proposed_content": content,
            "rationale": "Reason.",
            "criterion_item_ids": ["k1"],
        },
        {
            "source_memory_id": "s2",
            "decision": "KEEP",
            "proposed_content": "Remove part and retain this.",
            "rationale": "Reason.",
            "criterion_item_ids": ["k1"],
        },
    ]

    with pytest.raises(SelectiveCurationError, match=message):
        decode_curation_response(
            json.dumps({"overview": "Overview.", "candidates": candidates}),
            frame,
            variant_actions={
                "KEEP": "KEEP",
                "EDIT": "TRANSFORM",
                "DELETE": "DROP",
            },
        )
