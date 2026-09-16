"""Structured provider response schema for Atomize."""

from __future__ import annotations

from memcommit.application.capabilities.semantic.understanding import source_linked_understanding_schema

from ..model import (
    ATOMIZE_CHILD_CHAR_LIMIT,
    ATOMIZE_CHILD_LIMIT,
    ATOMIZE_CLASSIFICATIONS,
    ATOMIZE_CLARIFICATIONS,
    ATOMIZE_CONFLICTS,
    ATOMIZE_INTERPRETATIONS,
    ATOMIZE_OVERVIEW_CHAR_LIMIT,
    ATOMIZE_QUALITY_KINDS,
    ATOMIZE_QUALITY_READING_LIMIT,
    ATOMIZE_READING_LABEL_CHAR_LIMIT,
    ATOMIZE_REASON_CHAR_LIMIT,
    ATOMIZE_RULE_CODES,
    ATOMIZE_SCOPE_DIMENSIONS,
    ATOMIZE_SOURCE_SPAN_LIMIT,
    AtomizeCandidate,
)


def _output_schema(
    candidates: list[AtomizeCandidate],
) -> dict[str, object]:
    candidate_ids = [candidate.candidate_id for candidate in candidates]
    overview_section = source_linked_understanding_schema(
        tuple(candidate_ids),
        limit=ATOMIZE_OVERVIEW_CHAR_LIMIT,
        empty=True,
        # Structured output cannot express "one source iff text is nonempty"
        # with the flat strict schema accepted by the provider. Requiring one
        # source for every populated candidate frame is the safe side of that
        # conditional: a schema-valid nonempty overview can no longer be
        # rejected later as ungrounded. The decoder remains permissive for an
        # older genuinely empty section with no citations.
        require_sources=True,
    )
    quality_issue = {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": sorted(ATOMIZE_QUALITY_KINDS),
            },
            "source_ids": {
                "type": "array",
                "minItems": 1,
                "maxItems": 2,
                "items": {
                    "type": "string",
                    "enum": candidate_ids,
                },
            },
            # Strict provider schemas are more reliable with a complete flat
            # record than a oneOf union.  Kind-specific sentinel values are
            # rejected or normalized by the local parser below.
            "interpretation": {
                "type": "string",
                "enum": ["NONE", *sorted(ATOMIZE_INTERPRETATIONS)],
            },
            "clarification": {
                "type": "string",
                "enum": sorted(ATOMIZE_CLARIFICATIONS),
            },
            "conflict": {
                "type": "string",
                "enum": ["NONE", *sorted(ATOMIZE_CONFLICTS)],
            },
            "ordinary_readings": {
                "type": "array",
                "maxItems": ATOMIZE_QUALITY_READING_LIMIT,
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ATOMIZE_READING_LABEL_CHAR_LIMIT,
                        },
                        "text": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ATOMIZE_REASON_CHAR_LIMIT,
                        },
                    },
                    "required": ["label", "text"],
                    "additionalProperties": False,
                },
            },
            "scope_dimensions": {
                "type": "array",
                "maxItems": len(ATOMIZE_SCOPE_DIMENSIONS),
                "items": {
                    "type": "string",
                    "enum": sorted(ATOMIZE_SCOPE_DIMENSIONS),
                },
            },
            "reason": {
                "type": "string",
                "minLength": 1,
                "maxLength": ATOMIZE_REASON_CHAR_LIMIT,
            },
            "question": {
                "type": "string",
                "maxLength": 500,
            },
        },
        "required": [
            "kind",
            "source_ids",
            "interpretation",
            "clarification",
            "conflict",
            "ordinary_readings",
            "scope_dimensions",
            "reason",
            "question",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "overview": {
                "type": "object",
                "properties": {
                    "understood": overview_section,
                    "changed": overview_section,
                    "unresolved": overview_section,
                },
                "required": ["understood", "changed", "unresolved"],
                "additionalProperties": False,
            },
            "items": {
                "type": "array",
                "minItems": len(candidates),
                "maxItems": len(candidates),
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {
                            "type": "string",
                            "enum": candidate_ids,
                        },
                        "classification": {
                            "type": "string",
                            "enum": sorted(ATOMIZE_CLASSIFICATIONS),
                        },
                        "reason_codes": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": len(ATOMIZE_RULE_CODES),
                            # Codex strict schemas reject uniqueItems. The
                            # fail-closed parser enforces uniqueness locally.
                            "items": {
                                "type": "string",
                                "enum": sorted(ATOMIZE_RULE_CODES),
                            },
                        },
                        "children": {
                            "type": "array",
                            "maxItems": ATOMIZE_CHILD_LIMIT,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "content": {
                                        "type": "string",
                                        "minLength": 1,
                                        "maxLength": ATOMIZE_CHILD_CHAR_LIMIT,
                                    },
                                    "source_spans": {
                                        "type": "array",
                                        "minItems": 1,
                                        "maxItems": ATOMIZE_SOURCE_SPAN_LIMIT,
                                        "items": {
                                            "type": "string",
                                            "minLength": 1,
                                            "maxLength": (ATOMIZE_CHILD_CHAR_LIMIT),
                                        },
                                    },
                                },
                                "required": ["content", "source_spans"],
                                "additionalProperties": False,
                            },
                        },
                        "reason": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ATOMIZE_REASON_CHAR_LIMIT,
                        },
                    },
                    "required": [
                        "candidate_id",
                        "classification",
                        "reason_codes",
                        "children",
                        "reason",
                    ],
                    "additionalProperties": False,
                },
            },
            "quality_issues": {
                "type": "array",
                "maxItems": (
                    len(candidates) + len(candidates) * (len(candidates) - 1) // 2
                ),
                "items": quality_issue,
            },
        },
        "required": ["overview", "items", "quality_issues"],
        "additionalProperties": False,
    }
