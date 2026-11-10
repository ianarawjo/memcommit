"""Generate and validate suggestions for one complete Conflict issue frame."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from memcommit.application.capabilities.semantic_execution import (
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
    BudgetLimits,
    ExecutionMode,
    ExecutionStrategy,
    SemanticExecutionPolicy,
    json_budget,
    plan_semantic_execution,
)
from memcommit.application.operations.audit.model import QualityAuditSession
from ..convert_audit_to_issues import collect_resolution_issues
from ...model import (
    AuditResolutionIssue,
    ConflictResolutionTarget,
    ConflictResolutionAnalysis,
    ConflictResolutionError,
    ConflictResolutionIssue,
)
from .conflicts import SUGGESTION_INSTRUCTIONS

if TYPE_CHECKING:
    from ...application import ConflictResolutionProvider

CONFLICT_RESOLUTION_OPERATION = "conflict_resolution_directions"
CONFLICT_RESOLUTION_RESPONSE_LIMIT = 1_000_000
CONFLICT_RESOLUTION_TEXT_LIMIT = 20_000
CONFLICT_RESOLUTION_DIRECTION_WORD_LIMIT = 10
CONFLICT_RESOLUTION_EXECUTION_POLICY = SemanticExecutionPolicy(
    operation=CONFLICT_RESOLUTION_OPERATION,
    strategy=ExecutionStrategy.WHOLE_FRAME_ONLY,
    one_shot_limits=BudgetLimits(
        max_input_chars=SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
        max_items=2_000,
        max_output_items=2_000,
    ),
    staged_supported=False,
)


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ConflictResolutionError(f"Duplicate Conflict JSON key: {key}.")
        result[key] = value
    return result


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConflictResolutionError(f"Conflict {label} must be nonblank text.")
    result = value.strip()
    if len(result) > CONFLICT_RESOLUTION_TEXT_LIMIT:
        raise ConflictResolutionError(f"Conflict {label} is too long.")
    return result


def _payload(
    frame: ConflictResolutionTarget,
    audit: QualityAuditSession,
    items: tuple[AuditResolutionIssue, ...],
) -> dict[str, object]:
    memories = frame.source.memories
    alias_by_uid = {memory.uid: f"m{index}" for index, memory in enumerate(memories, 1)}
    actionable = set(frame.actionable_uids)
    return {
        "context": frame.display_name,
        "audit": {
            "uid": audit.uid,
            "snapshot_digest": audit.snapshot_digest,
            "items": [
                {
                    "item_id": item.uid,
                    "kind": item.kind,
                    "classification": item.classification,
                    "memory_ids": [alias_by_uid[uid] for uid in item.item_uids],
                    "reason": item.reason,
                    **({"question": item.question} if item.question else {}),
                    "detail": item.detail,
                }
                for item in items
            ],
        },
        "memories": [
            {
                "memory_id": alias_by_uid[memory.uid],
                "content": memory.content,
                "actionable": memory.uid in actionable,
            }
            for memory in memories
        ],
    }


def _schema(items: tuple[AuditResolutionIssue, ...]) -> dict[str, object]:
    item_ids = [item.uid for item in items]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["directions"],
        "properties": {
            "directions": {
                "type": "array",
                "minItems": len(items),
                "maxItems": len(items),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["item_id", "direction"],
                    "properties": {
                        "item_id": {"type": "string", "enum": item_ids},
                        "direction": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": CONFLICT_RESOLUTION_TEXT_LIMIT,
                            "description": "One English sentence, at most 10 whitespace-delimited words.",
                            "pattern": r"^\S+(?:[ \t]+\S+){0,9}$",
                        },
                    },
                },
            }
        },
    }


def _preflight(
    frame: ConflictResolutionTarget,
    audit: QualityAuditSession,
    items: tuple[AuditResolutionIssue, ...],
) -> tuple[tuple[AuditResolutionIssue, ...], dict[str, object], dict[str, object]]:
    if audit.source != frame.source:
        raise ConflictResolutionError(
            "Conflict Audit does not match its frozen Context."
        )
    known = {item.uid: item for item in collect_resolution_issues(audit)}
    if len({item.uid for item in items}) != len(items) or any(
        known.get(item.uid) != item for item in items
    ):
        raise ConflictResolutionError(
            "Review selection does not match its actionable Audit issues."
        )
    payload = _payload(frame, audit, items)
    schema = _schema(items)
    plan = plan_semantic_execution(
        CONFLICT_RESOLUTION_EXECUTION_POLICY,
        json_budget(
            payload,
            item_count=len(items) + len(frame.source.memories),
            output_schema=schema,
            expected_output_items=len(items),
        ),
    )
    if plan.mode is not ExecutionMode.ONE_SHOT:
        raise ConflictResolutionError(
            "The complete Conflict Audit frame exceeds its whole-frame semantic "
            f"plan ({', '.join(plan.exceeded_axes)})."
        )
    return items, payload, schema


def _prompt(payload: dict[str, object]) -> str:
    return (
        SUGGESTION_INSTRUCTIONS
        + "\n\nCONFLICT RESOLUTION PAYLOAD:\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _decode_directions(
    items: tuple[AuditResolutionIssue, ...],
    raw: str,
) -> dict[str, str]:
    if not isinstance(raw, str) or len(raw) > CONFLICT_RESOLUTION_RESPONSE_LIMIT:
        raise ConflictResolutionError(
            "Conflict provider returned an oversized response."
        )
    try:
        value = json.loads(raw, object_pairs_hook=_strict_object)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ConflictResolutionError(
            "Conflict provider returned invalid JSON."
        ) from error
    if not isinstance(value, dict) or set(value) != {"directions"}:
        raise ConflictResolutionError(
            "Conflict provider returned an invalid direction set."
        )
    records = value["directions"]
    if not isinstance(records, list):
        raise ConflictResolutionError(
            "Conflict provider returned an invalid direction list."
        )
    expected = {item.uid for item in items}
    result: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {"item_id", "direction"}:
            raise ConflictResolutionError(
                "Conflict provider returned an invalid direction."
            )
        item_uid = record["item_id"]
        if (
            not isinstance(item_uid, str)
            or item_uid not in expected
            or item_uid in result
        ):
            raise ConflictResolutionError(
                "Conflict provider returned an unknown or repeated item."
            )
        direction = _text(record["direction"], "direction")
        if len(direction.split()) > CONFLICT_RESOLUTION_DIRECTION_WORD_LIMIT or any(
            separator in direction for separator in ("\n", "\r")
        ):
            raise ConflictResolutionError(
                "Conflict suggestion must be one line with at most 10 words."
            )
        result[item_uid] = direction
    if set(result) != expected:
        raise ConflictResolutionError(
            "Conflict provider did not cover every Audit item exactly once."
        )
    return result


class ProviderConflictResolutionOptionsPort:
    """Generate directions from Audit evidence without rediscovering findings."""

    def analyze(
        self,
        frame: ConflictResolutionTarget,
        audit: QualityAuditSession,
        *,
        issues: tuple[AuditResolutionIssue, ...],
        provider: ConflictResolutionProvider | None = None,
    ) -> ConflictResolutionAnalysis:
        if not isinstance(frame, ConflictResolutionTarget) or not isinstance(
            audit, QualityAuditSession
        ):
            raise TypeError("Conflict direction execution requires a frame and Audit.")
        items, payload, schema = _preflight(frame, audit, issues)
        if not items:
            return ConflictResolutionAnalysis(
                frame=frame,
                audit=audit,
                status="NO_ISSUES",
                question="No issue remains to review.",
            )
        if items and provider is None:
            raise ConflictResolutionError("Memory issue directions require a provider.")
        directions = (
            _decode_directions(
                items,
                provider.complete(
                    _prompt(payload),
                    operation=CONFLICT_RESOLUTION_OPERATION,
                    output_schema=schema,
                ),
            )
            if items
            else {}
        )
        issues = tuple(
            ConflictResolutionIssue(
                uid=item.uid,
                audit_key=item.audit_key,
                audit_snapshot_digest=audit.snapshot_digest,
                kind=item.kind,
                classification=item.classification,
                item_uids=item.item_uids,
                item_kind=item.item_kind,
                proposed_direction=directions[item.uid],
                reason=item.reason,
                question=item.question,
            )
            for item in items
        )
        return ConflictResolutionAnalysis(
            frame=frame,
            audit=audit,
            status="NEEDS_INPUT",
            question="Finalize one decision for every issue in this round.",
            issues=issues,
        )
