"""Classify Merge candidate additions, equivalent items and structural conflicts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from memcommit.models.memory import Memory

from .candidate import MergeCandidate


class MergeConflictKind(str, Enum):
    """Deterministic reasons why one Source item cannot be added as-is."""

    CONTENT_DIVERGENCE = "CONTENT_DIVERGENCE"


@dataclass(frozen=True)
class CandidateConflict:
    uid: str
    kind: MergeConflictKind
    source_uid: str
    target_uids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class MergeConflictReport:
    memory_count: int
    findings: tuple[CandidateConflict, ...]
    additions: tuple[str, ...]
    unchanged: tuple[str, ...]
    memory_matches: tuple[tuple[str, str], ...]


def analyze_merge_conflicts(candidate: MergeCandidate) -> MergeConflictReport:
    """Compare incoming occurrences against earlier baseline placements.

    Existing problems within one original frame are outside Merge's structural
    remit. Never invent permissions or discard a conflicting occurrence here.
    """
    baseline = tuple(
        o for o in candidate.origins if o.frame == candidate.frame_order[0]
    )
    incoming = tuple(
        o for o in candidate.origins if o.frame != candidate.frame_order[0]
    )
    items = {o.uid: candidate.original_item(o.uid) for o in candidate.origins}
    additions, unchanged, findings, matches = [], [], [], []
    for origin in incoming:
        source = items[origin.uid]
        targets = tuple(o for o in baseline if o.placement == origin.placement)
        same = next((o for o in targets if o.item_uid == origin.identity_uid), None)
        if same is not None:
            target = items[same.uid]
            matches.append((origin.uid, same.uid))
            equivalent = source.content == target.content
            if equivalent:
                unchanged.append(origin.uid)
                continue
            colliders = (same,)
            kind = MergeConflictKind.CONTENT_DIVERGENCE
        else:
            if origin.identity_uid != origin.item_uid:
                raise ValueError(
                    "Checkpoint lineage names an unavailable Target Memory."
                )
            additions.append(origin.uid)
            continue
        findings.append(
            CandidateConflict(
                uid=_conflict_uid(
                    source_name=origin.context_name,
                    target_name=colliders[0].context_name,
                    source=source,
                    targets=tuple(items[o.uid] for o in colliders),
                    kind=kind,
                ),
                kind=kind,
                source_uid=origin.uid,
                target_uids=tuple(o.uid for o in colliders),
                reason=_conflict_reason(kind),
            )
        )
    return MergeConflictReport(
        sum(isinstance(item, Memory) for item in items.values()),
        tuple(findings),
        tuple(additions),
        tuple(unchanged),
        tuple(matches),
    )


def _record(item: Memory) -> dict[str, object]:
    value = item.to_dict()
    if not isinstance(value, dict):  # pragma: no cover - closed direct item model.
        raise TypeError("Merge item serialization is invalid.")
    return value


def _conflict_reason(kind: MergeConflictKind) -> str:
    return {
        MergeConflictKind.CONTENT_DIVERGENCE: (
            "The Source Memory is related to an existing Target occurrence "
            "but their content differs."
        ),
    }[kind]


def _conflict_uid(
    *,
    source_name: str,
    target_name: str,
    source: Memory,
    targets: tuple[Memory, ...],
    kind: MergeConflictKind,
) -> str:
    # Include the complete mapping and every member identity so recursive or
    # repeated placements cannot accidentally share a decision key.
    payload = {
        "source_name": source_name,
        "target_name": target_name,
        "source_uid": source.uid,
        "source_record": _record(source),
        "target_uids": [item.uid for item in targets],
        "target_records": [_record(item) for item in targets],
        "kind": kind.value,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"merge-conflict:{digest[:20]}"
