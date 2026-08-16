from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest

from memcommit.context import Context, Memory
from memcommit.eval.forget_compact import (
    ForgetCompactError,
    build_benchmark_record,
    build_compact_forget_prompt,
    build_forget_frame,
    compact_forget_output_schema,
    decode_compact_forget_response,
    run_compact_forget,
    score_label_agreement,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


def _context() -> Context:
    context = Context(uid=str(uuid.uuid4()), name="personal")
    for content in (
        "Keep this unrelated Memory.",
        "Remove this part, but preserve the independent remainder.",
        "Delete this whole Memory.",
    ):
        context.add(Memory(uid=str(uuid.uuid4()), content=content))
    return context


def test_compact_schema_requires_one_fixed_action_row_per_source():
    schema = compact_forget_output_schema(300)

    assert set(schema["properties"]) == {"actions", "edits"}
    assert schema["properties"]["actions"]["minItems"] == 300
    assert schema["properties"]["actions"]["maxItems"] == 300
    assert schema["properties"]["actions"]["items"]["enum"] == ["K", "E", "D"]
    assert "rationale" not in json.dumps(schema)
    assert "source_memory_id" not in json.dumps(schema)


def test_compact_decode_reconstructs_exact_keep_sparse_edit_and_drop():
    context = _context()
    frame = build_forget_frame(context, "Forget the covered details.")

    analysis = decode_compact_forget_response(
        json.dumps(
            {
                "actions": ["K", "E", "D"],
                "edits": [{"i": 2, "c": "Preserve the independent remainder."}],
            }
        ),
        frame,
    )

    source = [item.content for item in context.iter_items()]
    assert [decision.variant for decision in analysis.decisions] == [
        "KEEP",
        "EDIT",
        "DELETE",
    ]
    assert [decision.proposed_content for decision in analysis.decisions] == [
        source[0],
        "Preserve the independent remainder.",
        "",
    ]
    assert all(
        decision.rationale.startswith("Host reconstruction")
        for decision in analysis.decisions
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (
            {"actions": ["K", "E"], "edits": [{"i": 2, "c": "Remainder."}]},
            "exactly 3",
        ),
    ],
)
def test_compact_decode_rejects_invalid_coverage(value, message):
    with pytest.raises(ForgetCompactError, match=message):
        decode_compact_forget_response(
            json.dumps(value),
            build_forget_frame(_context(), "Forget the covered details."),
        )


def test_compact_decode_normalizes_noop_edit_to_exact_keep():
    context = _context()
    source = [item.content for item in context.iter_items()]
    analysis = decode_compact_forget_response(
        json.dumps(
            {
                "actions": ["K", "E", "D"],
                "edits": [{"i": 2, "c": source[1]}],
            }
        ),
        build_forget_frame(context, "Forget the covered details."),
    )

    assert [decision.variant for decision in analysis.decisions] == [
        "KEEP",
        "KEEP",
        "DELETE",
    ]
    assert analysis.decisions[1].proposed_content == source[1]
    assert "normalized" in analysis.decisions[1].rationale


@pytest.mark.parametrize(
    "edits",
    [
        [],
        [
            {"i": 2, "c": "Remainder."},
            {"i": 2, "c": "Another remainder."},
        ],
    ],
)
def test_compact_decode_conservatively_normalizes_unusable_edit_to_keep(edits):
    context = _context()
    source = [item.content for item in context.iter_items()]

    analysis = decode_compact_forget_response(
        json.dumps({"actions": ["K", "E", "D"], "edits": edits}),
        build_forget_frame(context, "Forget the covered details."),
    )

    assert [decision.variant for decision in analysis.decisions] == [
        "KEEP",
        "KEEP",
        "DELETE",
    ]
    assert analysis.decisions[1].proposed_content == source[1]


def test_compact_decode_ignores_extra_edit_for_non_edit_action():
    analysis = decode_compact_forget_response(
        json.dumps(
            {
                "actions": ["K", "E", "D"],
                "edits": [
                    {"i": 1, "c": "Ignored text."},
                    {"i": 2, "c": "Preserve the independent remainder."},
                ],
            }
        ),
        build_forget_frame(_context(), "Forget the covered details."),
    )

    assert [decision.variant for decision in analysis.decisions] == [
        "KEEP",
        "EDIT",
        "DELETE",
    ]


class _Provider:
    identity = ProviderIdentity(provider="fake", model="compact")
    last_run = None

    def __init__(self) -> None:
        self.prompt = None
        self.operation = None
        self.output_schema = None

    def complete(self, prompt, *, operation, output_schema=None):
        self.prompt = prompt
        self.operation = operation
        self.output_schema = output_schema
        self.last_run = CompletionRun(identity=self.identity, operation=operation)
        return json.dumps(
            {
                "actions": ["K", "E", "D"],
                "edits": [{"i": 2, "c": "Preserve the independent remainder."}],
            }
        )


def test_compact_run_keeps_one_complete_frame_and_does_not_modify_source():
    context = _context()
    before = context.to_dict()
    provider = _Provider()

    result = run_compact_forget(
        provider,
        context,
        "Forget the covered details.",
    )

    assert provider.operation == "forget_compact_vector_eval_v1"
    assert provider.output_schema["properties"]["actions"]["maxItems"] == 3
    assert provider.prompt.count("Keep this unrelated Memory.") == 1
    assert provider.prompt.count(
        "Remove this part, but preserve the independent remainder."
    ) == 1
    assert provider.prompt.count("Delete this whole Memory.") == 1
    assert len(result.analysis.decisions) == 3
    assert context.to_dict() == before


def test_compact_prompt_forbids_narrative_and_per_memory_repetition():
    prompt = build_compact_forget_prompt(
        build_forget_frame(_context(), "Forget the covered details.")
    )

    assert "Do not return Source IDs" in prompt
    assert "rationales" in prompt
    assert "source_memory_id" not in prompt


def test_different_instruction_does_not_reuse_historical_agreement():
    context = _context()
    provider = _Provider()
    instruction = "건강 관련 정보는 지워줘."
    completion = run_compact_forget(provider, context, instruction)

    record = build_benchmark_record(
        provider=provider,
        completion=completion,
        before=context.to_dict(),
        after=context.to_dict(),
        instruction=instruction,
        historical_instruction="Forget the covered details.",
        criterion_id="HEALTH",
        before_path=Path(__file__),
        after_path=Path(__file__),
        baseline_path=None,
        baseline_labels_by_alias=None,
        baseline_ledger={},
        connection_seconds=0.0,
    )

    assert record["agreement"] is None
    assert record["historical_reference"]["applicable"] is False
    assert record["corpus"]["criterion_id"] == "HEALTH"


def test_label_agreement_separates_exact_labels_from_change_detection():
    result = score_label_agreement(
        {"a": "KEEP", "b": "EDIT", "c": "DELETE"},
        {"a": "KEEP", "b": "DELETE", "c": "DELETE"},
    )

    assert result["exact_label_accuracy"] == 2 / 3
    assert result["change_vs_keep"]["f1"] == 1.0
