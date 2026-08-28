"""Operation-neutral batch contract for selective Memory retention.

Forget and Sever differ at their authority and materialization boundaries, but
both ask one provider turn to classify a frozen Source frame against a frozen
criterion frame.  This module owns only that shared semantic boundary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Mapping

from memcommit.application.capabilities.semantic_execution import (
    BudgetLimits,
    ExecutionPlan,
    ExecutionStrategy,
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
    SemanticExecutionPolicy,
    json_budget,
    plan_semantic_execution,
)


SELECTIVE_CURATION_INPUT_CHAR_LIMIT = SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT
SELECTIVE_CURATION_EXECUTION_POLICY = SemanticExecutionPolicy(
    operation="selective curation",
    strategy=ExecutionStrategy.WHOLE_FRAME_ONLY,
    one_shot_limits=BudgetLimits(
        max_input_chars=SELECTIVE_CURATION_INPUT_CHAR_LIMIT,
    ),
    staged_supported=False,
)


CurationAction = Literal["KEEP", "TRANSFORM", "DROP"]
CriterionKind = Literal["INSTRUCTION", "MEMORY_FRAME"]


class SelectiveCurationError(ValueError):
    """A batch input or provider result violates the shared contract."""


@dataclass(frozen=True)
class CurationItem:
    uid: str
    content: str
    context_name: str = ""

    def __post_init__(self) -> None:
        if not self.uid or not isinstance(self.uid, str):
            raise SelectiveCurationError("A curation item requires an id.")
        if not isinstance(self.content, str) or not self.content.strip():
            raise SelectiveCurationError("A curation item requires content.")
        if not isinstance(self.context_name, str):
            raise SelectiveCurationError("Invalid curation item owner.")


@dataclass(frozen=True)
class CriterionFrame:
    kind: CriterionKind
    label: str
    items: tuple[CurationItem, ...]

    def __post_init__(self) -> None:
        if self.kind not in {"INSTRUCTION", "MEMORY_FRAME"}:
            raise SelectiveCurationError("Invalid criterion frame kind.")
        if not isinstance(self.label, str) or not self.label.strip():
            raise SelectiveCurationError("A criterion frame requires a label.")
        if not self.items:
            raise SelectiveCurationError("A criterion frame requires an item.")
        if len({item.uid for item in self.items}) != len(self.items):
            raise SelectiveCurationError("Duplicate criterion item id.")
        if self.kind == "INSTRUCTION" and len(self.items) != 1:
            raise SelectiveCurationError(
                "An instruction criterion frame requires exactly one item."
            )


@dataclass(frozen=True)
class CurationBatch:
    source_label: str
    source: tuple[CurationItem, ...]
    criteria: CriterionFrame

    def __post_init__(self) -> None:
        if not isinstance(self.source_label, str) or not self.source_label.strip():
            raise SelectiveCurationError("A curation batch requires a Source label.")
        if not self.source:
            raise SelectiveCurationError("A curation batch requires a Source Memory.")
        if len({item.uid for item in self.source}) != len(self.source):
            raise SelectiveCurationError("Duplicate Source Memory id.")


@dataclass(frozen=True)
class CurationDecision:
    source_uid: str
    action: CurationAction
    variant: str
    proposed_content: str
    rationale: str
    criterion_uids: tuple[str, ...]


@dataclass(frozen=True)
class CurationAnalysis:
    overview: str
    decisions: tuple[CurationDecision, ...]


@dataclass(frozen=True)
class CurationProviderFrame:
    """Alias-safe payload plus the maps needed to validate its response."""

    batch: CurationBatch
    payload: dict[str, object]
    source_aliases: Mapping[str, str]
    criterion_aliases: Mapping[str, str]


def build_provider_frame(batch: CurationBatch) -> CurationProviderFrame:
    source_aliases = {
        item.uid: f"s{index}" for index, item in enumerate(batch.source, 1)
    }
    criterion_aliases = {
        item.uid: f"k{index}" for index, item in enumerate(batch.criteria.items, 1)
    }

    def record(item: CurationItem, alias: str) -> dict[str, str]:
        value = {"item_id": alias, "content": item.content}
        if item.context_name:
            value["owner"] = item.context_name
        return value

    payload: dict[str, object] = {
        "source": {
            "label": batch.source_label,
            "memories": [
                record(item, source_aliases[item.uid]) for item in batch.source
            ],
        },
        "criteria": {
            "kind": batch.criteria.kind,
            "label": batch.criteria.label,
            "items": [
                record(item, criterion_aliases[item.uid])
                for item in batch.criteria.items
            ],
        },
    }
    return CurationProviderFrame(
        batch=batch,
        payload=payload,
        source_aliases=source_aliases,
        criterion_aliases=criterion_aliases,
    )


def plan_curation_execution(
    frame: CurationProviderFrame,
    *,
    payload: object | None = None,
    output_schema: object | None = None,
) -> ExecutionPlan:
    """Require one complete Source × Criteria turn under a shared budget."""

    return plan_semantic_execution(
        SELECTIVE_CURATION_EXECUTION_POLICY,
        json_budget(
            frame.payload if payload is None else payload,
            item_count=len(frame.batch.source) + len(frame.batch.criteria.items),
            output_schema=output_schema,
            expected_output_items=len(frame.batch.source),
        ),
    )


def curation_output_schema(
    frame: CurationProviderFrame,
    variants: tuple[str, ...],
    *,
    criterion_refs_field: str = "criterion_item_ids",
) -> dict[str, object]:
    if not variants or len(set(variants)) != len(variants):
        raise SelectiveCurationError("Curation variants must be unique.")
    if not criterion_refs_field:
        raise SelectiveCurationError("A criterion reference field is required.")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["overview", "candidates"],
        "properties": {
            "overview": {"type": "string"},
            "candidates": {
                "type": "array",
                "minItems": len(frame.batch.source),
                "maxItems": len(frame.batch.source),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "source_memory_id",
                        "decision",
                        "proposed_content",
                        "rationale",
                        criterion_refs_field,
                    ],
                    "properties": {
                        "source_memory_id": {
                            "type": "string",
                            "enum": list(frame.source_aliases.values()),
                        },
                        "decision": {"type": "string", "enum": list(variants)},
                        "proposed_content": {"type": "string"},
                        "rationale": {"type": "string"},
                        criterion_refs_field: {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": list(frame.criterion_aliases.values()),
                            },
                        },
                    },
                },
            },
        },
    }


def decode_curation_response(
    raw: str,
    frame: CurationProviderFrame,
    *,
    variant_actions: Mapping[str, CurationAction],
    criterion_refs_field: str = "criterion_item_ids",
) -> CurationAnalysis:
    """Decode a complete Source-indexed batch or reject the whole response."""
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise SelectiveCurationError("Invalid curation provider output.") from error
    if not isinstance(value, dict) or set(value) != {"overview", "candidates"}:
        raise SelectiveCurationError("Invalid curation provider output.")
    overview = value["overview"]
    records = value["candidates"]
    if (
        not isinstance(overview, str)
        or not overview.strip()
        or not isinstance(records, list)
    ):
        raise SelectiveCurationError("Invalid curation provider output.")

    source_by_alias = {alias: uid for uid, alias in frame.source_aliases.items()}
    criterion_by_alias = {
        alias: uid for uid, alias in frame.criterion_aliases.items()
    }
    source_by_uid = {item.uid: item for item in frame.batch.source}
    seen: set[str] = set()
    decisions: list[CurationDecision] = []
    required_keys = {
        "source_memory_id",
        "decision",
        "proposed_content",
        "rationale",
        criterion_refs_field,
    }
    for record in records:
        if not isinstance(record, dict) or set(record) != required_keys:
            raise SelectiveCurationError("Invalid curation candidate.")
        alias = record["source_memory_id"]
        variant = record["decision"]
        refs = record[criterion_refs_field]
        if (
            not isinstance(alias, str)
            or alias not in source_by_alias
            or alias in seen
            or not isinstance(variant, str)
            or variant not in variant_actions
            or not isinstance(refs, list)
            or any(not isinstance(ref, str) for ref in refs)
        ):
            raise SelectiveCurationError("Invalid curation candidate.")
        if len(refs) != len(set(refs)):
            raise SelectiveCurationError(
                "The provider cited a criterion more than once."
            )
        try:
            criterion_uids = tuple(criterion_by_alias[ref] for ref in refs)
        except KeyError as error:
            raise SelectiveCurationError("Unavailable criterion citation.") from error
        proposed = record["proposed_content"]
        rationale = record["rationale"]
        if not isinstance(proposed, str) or not isinstance(rationale, str) or not rationale.strip():
            raise SelectiveCurationError("Invalid curation candidate content.")
        source_uid = source_by_alias[alias]
        action = variant_actions[variant]
        if action == "KEEP" and proposed != source_by_uid[source_uid].content:
            raise SelectiveCurationError("KEEP must preserve exact Source text.")
        if action == "DROP" and proposed:
            raise SelectiveCurationError("DROP must have empty proposed content.")
        if action == "TRANSFORM" and not proposed.strip():
            raise SelectiveCurationError("TRANSFORM requires proposed content.")
        seen.add(alias)
        decisions.append(
            CurationDecision(
                source_uid=source_uid,
                action=action,
                variant=variant,
                proposed_content=proposed,
                rationale=rationale,
                criterion_uids=criterion_uids,
            )
        )
    if seen != set(source_by_alias):
        raise SelectiveCurationError(
            "Curation candidates must cover every Source Memory exactly once."
        )
    return CurationAnalysis(overview=overview, decisions=tuple(decisions))
