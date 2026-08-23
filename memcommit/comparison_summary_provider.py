"""One concise provider turn for the default human-facing Compare report."""

from __future__ import annotations

import json
from typing import Protocol

from memcommit.comparison import ComparisonInput
from memcommit.comparison_summary import (
    ComparisonSummary,
    ComparisonSummaryError,
)
from memcommit.semantic_execution import (
    BudgetLimits,
    ExecutionMode,
    ExecutionStrategy,
    SemanticExecutionPolicy,
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
    json_budget,
    plan_semantic_execution,
)
from memcommit.understanding import (
    UnderstandingError,
    UnderstandingSummary,
    normalize_understanding_text,
    source_linked_understanding_schema,
)


COMPARISON_SUMMARY_OPERATION = "compare_summary"
COMPARISON_SUMMARY_PROVIDER_CONTRACT_VERSION = "single-paragraph-source-linked-v2"
COMPARISON_SUMMARY_TEXT_LIMIT = 2_000

COMPARISON_SUMMARY_EXECUTION_POLICY = SemanticExecutionPolicy(
    operation=COMPARISON_SUMMARY_OPERATION,
    strategy=ExecutionStrategy.HIERARCHICAL_REDUCE,
    one_shot_limits=BudgetLimits(
        max_input_chars=SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
    ),
    staged_supported=False,
)


class ComparisonSummaryProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str: ...


def _provider_payload(
    comparison_input: ComparisonInput,
) -> tuple[dict[str, object], dict[str, str], set[str], set[str]]:
    aliases: dict[str, str] = {}
    reference_ids: set[str] = set()
    compared_ids: set[str] = set()
    frames: list[dict[str, object]] = []
    for frame_index, frame in enumerate(comparison_input.frames):
        prefix = "A" if frame_index == 0 else "B"
        target = reference_ids if frame_index == 0 else compared_ids
        rows: list[dict[str, object]] = []
        for role, memories in (
            ("PRIMARY", frame.memories),
            ("CONTEXT", frame.context_evidence),
        ):
            for memory in memories:
                alias = f"{prefix}{len(target) + 1}"
                target.add(alias)
                aliases[alias] = memory.uid
                rows.append(
                    {
                        "id": alias,
                        "role": role,
                        "content": memory.content,
                    }
                )
        frames.append({"side": frame.side, "memories": rows})
    return {"frames": frames}, aliases, reference_ids, compared_ids


def comparison_summary_output_schema(
    aliases: tuple[str, ...],
) -> dict[str, object]:
    schema = source_linked_understanding_schema(
        aliases,
        limit=COMPARISON_SUMMARY_TEXT_LIMIT,
    )
    properties = schema["properties"]
    assert isinstance(properties, dict)
    text_schema = properties["text"]
    assert isinstance(text_schema, dict)
    text_schema["pattern"] = r"^[^\r\n]+$"
    return schema


def _prompt(payload: dict[str, object]) -> str:
    return (
        "Compare the two equal-authority Memory frames for a person who needs "
        "one concise read-only summary. Return exactly one natural-language "
        "prose paragraph that integrates the most important common ground, "
        "material differences, and side-specific points where they are useful. "
        "Do not use headings, labels, bullets, lists, line breaks, or a fixed "
        "category-by-category template. Cite only opaque source ids that "
        "directly support the paragraph. Do not build or imply an exhaustive "
        "relation graph, assign every Memory to a group, create grounding "
        "questions, recommend Meld dispositions, or repeat source text. PRIMARY "
        "rows are the requested comparison subjects; CONTEXT rows may clarify "
        "them but are not additional subjects. Keep the paragraph under about "
        "140 English words.\n\nCOMPARISON SUMMARY PAYLOAD:\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _decode_paragraph(
    value: object,
    *,
    aliases: dict[str, str],
    reference_ids: set[str],
    compared_ids: set[str],
) -> UnderstandingSummary:
    if not isinstance(value, dict) or set(value) != {"text", "source_ids"}:
        raise ComparisonSummaryError("Invalid lightweight Compare paragraph.")
    raw_text = value["text"]
    if isinstance(raw_text, str) and any(mark in raw_text for mark in ("\r", "\n")):
        raise ComparisonSummaryError(
            "Lightweight Compare must return exactly one prose paragraph."
        )
    text = normalize_understanding_text(
        raw_text,
        limit=COMPARISON_SUMMARY_TEXT_LIMIT,
    )
    raw_ids = value["source_ids"]
    if (
        not isinstance(raw_ids, list)
        or any(not isinstance(alias, str) or alias not in aliases for alias in raw_ids)
        or len(set(raw_ids)) != len(raw_ids)
        or not raw_ids
    ):
        raise ComparisonSummaryError(
            "Lightweight Compare paragraph has invalid source evidence."
        )
    if not any(alias in reference_ids for alias in raw_ids) or not any(
        alias in compared_ids for alias in raw_ids
    ):
        raise ComparisonSummaryError(
            "A Compare paragraph must cite both peer sides."
        )
    return UnderstandingSummary(
        text=text,
        source_uids=tuple(dict.fromkeys(aliases[alias] for alias in raw_ids)),
    )


def summarize_comparison(
    comparison_input: ComparisonInput,
    provider: ComparisonSummaryProvider,
) -> ComparisonSummary:
    """Produce one compact report without constructing a relation ledger."""

    if not isinstance(comparison_input, ComparisonInput):
        raise ComparisonSummaryError(
            "Lightweight Compare requires a frozen ComparisonInput."
        )
    comparison_input.validate()
    payload, aliases, reference_ids, compared_ids = _provider_payload(
        comparison_input
    )
    schema = comparison_summary_output_schema(tuple(aliases))
    plan = plan_semantic_execution(
        COMPARISON_SUMMARY_EXECUTION_POLICY,
        json_budget(
            payload,
            item_count=sum(len(frame.memories) for frame in comparison_input.frames),
            output_schema=schema,
            expected_output_items=1,
        ),
    )
    if plan.mode is not ExecutionMode.ONE_SHOT:
        raise ComparisonSummaryError(
            "This Context pair exceeds the bounded lightweight Compare frame."
        )
    try:
        decoded = json.loads(
            provider.complete(
                _prompt(payload),
                operation=COMPARISON_SUMMARY_OPERATION,
                output_schema=schema,
            )
        )
    except (json.JSONDecodeError, UnderstandingError) as error:
        raise ComparisonSummaryError(
            "The provider returned an invalid lightweight Compare report."
        ) from error
    try:
        paragraph = _decode_paragraph(
            decoded,
            aliases=aliases,
            reference_ids=reference_ids,
            compared_ids=compared_ids,
        )
    except UnderstandingError as error:
        raise ComparisonSummaryError(str(error)) from error
    return ComparisonSummary.from_input(
        comparison_input,
        paragraph=paragraph,
    )


__all__ = [
    "COMPARISON_SUMMARY_EXECUTION_POLICY",
    "COMPARISON_SUMMARY_OPERATION",
    "COMPARISON_SUMMARY_PROVIDER_CONTRACT_VERSION",
    "ComparisonSummaryProvider",
    "comparison_summary_output_schema",
    "summarize_comparison",
]
