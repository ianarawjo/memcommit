"""Provider limits, wire versions, protocol, and output schemas."""

from __future__ import annotations

from typing import Protocol

from memcommit.application.operations.semantic_updates.curate_integrate.meld.model import MELD_TEXT_LIMIT, MeldError
from memcommit.application.capabilities.reviewing.result_workbench import (
    RESULT_REPORT_SECTION_SOFT_MAX_WORDS,
    RESULT_REPORT_SECTION_TARGET_MIN_WORDS,
)
from memcommit.application.capabilities.semantic_execution import (
    BudgetLimits,
    ExecutionStrategy,
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
    SemanticExecutionPolicy,
    exact_source_assignment_schema,
)


MELD_PAYLOAD_MARKER = "MELD TURN PAYLOAD:\n"
MELD_INPUT_CHAR_LIMIT = SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT
MELD_RESPONSE_CHAR_LIMIT = 1_000_000
MELD_KEY_LIMIT = 100
MELD_OPTION_LIMIT = 5
# Exact Study prewarms bind to the provider-facing decision contract, not only
# Meld's durable schema. Changing the compact fields or their meaning must make
# an older prepared assessment miss instead of silently reusing it.
MELD_DIRECTIONAL_PROVIDER_CONTRACT_VERSION = "directional-compare-decisions-v2"
# Resolution-branch cache keys bind to the complete provider-facing request.
# Bump this when a decoder or validation change alters the meaning of a response
# without also changing the prompt or output schema.
MELD_RESOLUTION_REQUEST_CONTRACT_VERSION = "complete-ledger-resolution-v1"

MELD_EXECUTION_POLICY = SemanticExecutionPolicy(
    operation="meld_contexts",
    strategy=ExecutionStrategy.BLOCK_RELATIONS,
    one_shot_limits=BudgetLimits(max_input_chars=MELD_INPUT_CHAR_LIMIT),
    staged_supported=False,
)

_RELATIONS = {
    "EQUIVALENT",
    "COMPATIBLE",
    "SCOPED",
    "CONFLICT",
    "DISTINCT",
    "UNCLEAR",
}
_STATUSES = {"RESOLVED", "UNRESOLVED"}
_PRIORITIES = {"REQUIRED", "HELPFUL"}
_DISPOSITIONS = {"COALESCE", "PRESERVE", "SYNTHESIZE", "USER_ADD"}


class MeldProviderError(MeldError):
    """Safe failure from one semantic meld assessment."""


class MeldProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one structured model completion."""

def meld_output_schema(
    source_memory_ids: tuple[str, ...],
    *,
    mode: str = "SYMMETRIC",
    target_context_count: int = 1,
    allow_directional_add: bool = True,
) -> dict[str, object]:
    source_count = len(source_memory_ids)
    key = {"type": "string", "minLength": 1, "maxLength": MELD_KEY_LIMIT}
    text = {"type": "string", "minLength": 1, "maxLength": MELD_TEXT_LIMIT}
    overview_text = {
        **text,
        "description": (
            "One short English natural-language report paragraph using "
            "complete sentences, normally no more than roughly "
            f"{RESULT_REPORT_SECTION_TARGET_MIN_WORDS}-"
            f"{RESULT_REPORT_SECTION_SOFT_MAX_WORDS} words. Do not use "
            "bullets, headings, key-value records, opaque IDs, or counts."
        ),
    }
    memory_refs = {
        "type": "array",
        "maxItems": source_count,
        "items": key,
    }
    key_refs = {
        "type": "array",
        "items": key,
    }
    paired_relation = {
        "type": "object",
        "properties": {
            "relation_key": key,
            "kind": {
                "type": "string",
                "enum": sorted(_RELATIONS - {"DISTINCT"}),
            },
            "status": {
                "type": "string",
                "enum": sorted(_STATUSES),
            },
            "summary": text,
            "reason": text,
        },
        "required": [
            "relation_key",
            "kind",
            "status",
            "summary",
            "reason",
        ],
        "additionalProperties": False,
    }
    distinct_relation = {
        "type": "object",
        "properties": {
            "relation_key": key,
            "side": {"type": "string", "enum": ["LEFT", "RIGHT"]},
            "kind": {"type": "string", "enum": ["DISTINCT"]},
            "status": {
                "type": "string",
                "enum": sorted(_STATUSES),
            },
            "summary": text,
            "reason": text,
        },
        "required": [
            "relation_key",
            "side",
            "kind",
            "status",
            "summary",
            "reason",
        ],
        "additionalProperties": False,
    }
    option = {
        "type": "object",
        "properties": {"label": text, "text": text},
        "required": ["label", "text"],
        "additionalProperties": False,
    }
    issue = {
        "type": "object",
        "properties": {
            "issue_key": key,
            "relation_keys": key_refs,
            "priority": {
                "type": "string",
                "enum": sorted(_PRIORITIES),
            },
            "title": text,
            "question": text,
            "why_it_matters": text,
            "options": {
                "type": "array",
                "maxItems": MELD_OPTION_LIMIT,
                "items": option,
            },
        },
        "required": [
            "issue_key",
            "relation_keys",
            "priority",
            "title",
            "question",
            "why_it_matters",
            "options",
        ],
        "additionalProperties": False,
    }
    result = {
        "type": "object",
        "properties": {
            "result_key": key,
            "disposition": {
                "type": "string",
                "enum": sorted(_DISPOSITIONS),
            },
            "content": text,
            "reason": text,
            "relation_keys": key_refs,
            "source_memory_ids": memory_refs,
            "grounded_turn_ids": key_refs,
        },
        "required": [
            "result_key",
            "disposition",
            "content",
            "reason",
            "relation_keys",
            "source_memory_ids",
            "grounded_turn_ids",
        ],
        "additionalProperties": False,
    }
    if mode == "DIRECTIONAL":
        result["properties"]["operation"] = {
            "type": "string",
            "enum": (
                ["ADD", "EDIT"] if allow_directional_add else ["EDIT"]
            ),
        }
        result["properties"]["target_memory_ids"] = {
            "type": "array",
            "maxItems": 1,
            "items": key,
        }
        result["required"] = [
            *result["required"],
            "operation",
            "target_memory_ids",
        ]
        if target_context_count > 1:
            result["properties"]["target_context_id"] = key
            result["required"] = [
                *result["required"],
                "target_context_id",
            ]
    return {
        "type": "object",
        "properties": {
            "overview": overview_text,
            "paired_relations": {
                "type": "array",
                "maxItems": source_count,
                "items": paired_relation,
            },
            "distinct_relations": {
                "type": "array",
                "maxItems": source_count,
                "items": distinct_relation,
            },
            "source_assignments": exact_source_assignment_schema(
                source_memory_ids,
                relation_key_schema=key,
            ),
            "issues": {
                "type": "array",
                "maxItems": source_count,
                "items": issue,
            },
            "results": {
                "type": "array",
                "items": result,
            },
            "ready_to_apply": {"type": "boolean"},
        },
        "required": [
            "overview",
            "paired_relations",
            "distinct_relations",
            "source_assignments",
            "issues",
            "results",
            "ready_to_apply",
        ],
        "additionalProperties": False,
    }


def _directional_relation_basis_output_schema(
    source_memory_ids: tuple[str, ...],
    *,
    target_context_count: int,
) -> dict[str, object]:
    """Return only Directional decisions when relation analysis owns the ledger."""

    complete = meld_output_schema(
        source_memory_ids,
        mode="DIRECTIONAL",
        target_context_count=target_context_count,
    )
    properties = complete["properties"]
    assert isinstance(properties, dict)
    # Relations, source assignments, and imported issues are deterministic
    # host input. Making those fields unrepresentable prevents a stochastic
    # completion from rewriting the reviewed relation basis.
    return {
        "type": "object",
        "properties": {
            "overview": properties["overview"],
            "additional_issues": properties["issues"],
            "results": properties["results"],
            "ready_to_apply": properties["ready_to_apply"],
        },
        "required": [
            "overview",
            "additional_issues",
            "results",
            "ready_to_apply",
        ],
        "additionalProperties": False,
    }
