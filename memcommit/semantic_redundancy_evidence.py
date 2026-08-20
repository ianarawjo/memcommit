"""Canonical public wire form for semantic Dedun evidence."""

from __future__ import annotations

import json

from memcommit.quality_finding_handoff import (
    QUALITY_FINDING_HANDOFF_CONTRACT_VERSION,
    QualityFindingHandoff,
    QualityFindingHandoffError,
)


SEMANTIC_REDUNDANCY_EVIDENCE_VERSION = "semantic-redundancy-evidence-v1"


def semantic_redundancy_evidence_dict(
    evidence: QualityFindingHandoff,
) -> dict[str, object]:
    """Project internal typed evidence under canonical public field values."""

    if not isinstance(evidence, QualityFindingHandoff):
        raise TypeError("Semantic redundancy evidence requires a typed value.")
    if evidence.kind != "DUPLICATE" or evidence.route != "DEDUP":
        raise QualityFindingHandoffError(
            "Only semantic redundancy evidence can enter Dedun."
        )
    payload = evidence.to_dict()
    payload["contract"] = SEMANTIC_REDUNDANCY_EVIDENCE_VERSION
    payload["kind"] = "REDUNDANCY"
    payload["route"] = "DEDUN"
    return payload


def semantic_redundancy_evidence_json(
    evidence: QualityFindingHandoff,
) -> str:
    """Serialize duplicate-finder evidence under canonical public names."""

    return json.dumps(
        semantic_redundancy_evidence_dict(evidence),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def semantic_redundancy_evidence_from_dict(
    value: object,
) -> QualityFindingHandoff:
    """Decode one public evidence object into the internal typed receipt."""

    if not isinstance(value, dict):
        raise QualityFindingHandoffError(
            "Semantic redundancy evidence must be one JSON object."
        )
    if value.get("contract") != SEMANTIC_REDUNDANCY_EVIDENCE_VERSION:
        raise QualityFindingHandoffError(
            "Unsupported semantic redundancy evidence contract."
        )
    if value.get("kind") != "REDUNDANCY" or value.get("route") != "DEDUN":
        raise QualityFindingHandoffError(
            "Semantic redundancy evidence kind or route is invalid."
        )
    internal = dict(value)
    internal["contract"] = QUALITY_FINDING_HANDOFF_CONTRACT_VERSION
    internal["kind"] = "DUPLICATE"
    internal["route"] = "DEDUP"
    return QualityFindingHandoff.from_dict(internal)


def semantic_redundancy_evidence_from_json(
    value: str,
) -> QualityFindingHandoff:
    """Decode strict public evidence JSON into the internal typed receipt."""

    if not isinstance(value, str) or not value.strip():
        raise QualityFindingHandoffError(
            "Semantic redundancy evidence JSON must be nonblank text."
        )

    def exact_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise QualityFindingHandoffError(
                    f"Duplicate semantic redundancy evidence key '{key}'."
                )
            result[key] = item
        return result

    try:
        decoded = json.loads(value, object_pairs_hook=exact_pairs)
    except (json.JSONDecodeError, ValueError) as error:
        if isinstance(error, QualityFindingHandoffError):
            raise
        raise QualityFindingHandoffError(
            "Semantic redundancy evidence JSON is invalid."
        ) from error
    return semantic_redundancy_evidence_from_dict(decoded)


__all__ = [
    "SEMANTIC_REDUNDANCY_EVIDENCE_VERSION",
    "semantic_redundancy_evidence_dict",
    "semantic_redundancy_evidence_from_dict",
    "semantic_redundancy_evidence_from_json",
    "semantic_redundancy_evidence_json",
]
