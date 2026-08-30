"""Canonical public wire form for complete exact-plus-semantic DUN evidence."""

from __future__ import annotations

import json

from memcommit.application.capabilities.reviewing.memory_issue.resolution.handoff import (
    QUALITY_FINDING_HANDOFF_CONTRACT_VERSION,
    QualityFindingHandoff,
    QualityFindingHandoffError,
)


REDUNDANCY_EVIDENCE_VERSION = "redundancy-evidence-v2"
LEGACY_SEMANTIC_REDUNDANCY_EVIDENCE_VERSION = "semantic-redundancy-evidence-v1"
# Compatibility export for plugins importing the former constant name. New
# serialization uses the inclusive v2 contract.
SEMANTIC_REDUNDANCY_EVIDENCE_VERSION = REDUNDANCY_EVIDENCE_VERSION
_RELATIONS = frozenset({"EXACT", "SURFACE_EQUIVALENT", "SEMANTIC_EQUIVALENT"})


def redundancy_evidence_dict(
    evidence: QualityFindingHandoff,
) -> dict[str, object]:
    """Project internal typed evidence under canonical public field values."""

    if not isinstance(evidence, QualityFindingHandoff):
        raise TypeError("Redundancy evidence requires a typed value.")
    if (
        evidence.kind != "DUPLICATE"
        or evidence.route != "DEDUP"
        or evidence.classification not in _RELATIONS
    ):
        raise QualityFindingHandoffError(
            "Only exact or semantic redundancy evidence can enter Dedun."
        )
    payload = evidence.to_dict()
    payload["contract"] = REDUNDANCY_EVIDENCE_VERSION
    payload["kind"] = "REDUNDANCY"
    payload["route"] = "DEDUN"
    return payload


def redundancy_evidence_json(
    evidence: QualityFindingHandoff,
) -> str:
    """Serialize complete DUN evidence under canonical public names."""

    return json.dumps(
        redundancy_evidence_dict(evidence),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def redundancy_evidence_from_dict(
    value: object,
) -> QualityFindingHandoff:
    """Decode one public evidence object into the internal typed receipt."""

    if not isinstance(value, dict):
        raise QualityFindingHandoffError("Redundancy evidence must be one JSON object.")
    contract = value.get("contract")
    if contract not in {
        REDUNDANCY_EVIDENCE_VERSION,
        LEGACY_SEMANTIC_REDUNDANCY_EVIDENCE_VERSION,
    }:
        raise QualityFindingHandoffError("Unsupported redundancy evidence contract.")
    if value.get("kind") != "REDUNDANCY" or value.get("route") != "DEDUN":
        raise QualityFindingHandoffError(
            "Redundancy evidence kind or route is invalid."
        )
    classification = value.get("classification")
    if classification not in _RELATIONS or (
        contract == LEGACY_SEMANTIC_REDUNDANCY_EVIDENCE_VERSION
        and classification == "EXACT"
    ):
        raise QualityFindingHandoffError(
            "Redundancy evidence classification is invalid for its contract."
        )
    internal = dict(value)
    internal["contract"] = QUALITY_FINDING_HANDOFF_CONTRACT_VERSION
    internal["kind"] = "DUPLICATE"
    internal["route"] = "DEDUP"
    return QualityFindingHandoff.from_dict(internal)


def redundancy_evidence_from_json(
    value: str,
) -> QualityFindingHandoff:
    """Decode strict public evidence JSON into the internal typed receipt."""

    if not isinstance(value, str) or not value.strip():
        raise QualityFindingHandoffError(
            "Redundancy evidence JSON must be nonblank text."
        )

    def exact_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise QualityFindingHandoffError(
                    f"Duplicate redundancy evidence key '{key}'."
                )
            result[key] = item
        return result

    try:
        decoded = json.loads(value, object_pairs_hook=exact_pairs)
    except (json.JSONDecodeError, ValueError) as error:
        if isinstance(error, QualityFindingHandoffError):
            raise
        raise QualityFindingHandoffError(
            "Redundancy evidence JSON is invalid."
        ) from error
    return redundancy_evidence_from_dict(decoded)


# Compatibility callables keep existing plugins importable while all new
# payloads use the inclusive v2 contract.
semantic_redundancy_evidence_dict = redundancy_evidence_dict
semantic_redundancy_evidence_json = redundancy_evidence_json
semantic_redundancy_evidence_from_dict = redundancy_evidence_from_dict
semantic_redundancy_evidence_from_json = redundancy_evidence_from_json


__all__ = [
    "LEGACY_SEMANTIC_REDUNDANCY_EVIDENCE_VERSION",
    "REDUNDANCY_EVIDENCE_VERSION",
    "SEMANTIC_REDUNDANCY_EVIDENCE_VERSION",
    "redundancy_evidence_dict",
    "redundancy_evidence_from_dict",
    "redundancy_evidence_from_json",
    "redundancy_evidence_json",
    "semantic_redundancy_evidence_dict",
    "semantic_redundancy_evidence_from_dict",
    "semantic_redundancy_evidence_from_json",
    "semantic_redundancy_evidence_json",
]
