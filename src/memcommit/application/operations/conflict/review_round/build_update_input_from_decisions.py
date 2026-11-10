"""Convert finalized decisions into the Source Context consumed by Update."""

from __future__ import annotations

import hashlib
import json
import uuid
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from ..model import ConflictResolutionAnalysis, ConflictResolutionError
from ..analysis.resolution_options.conflicts import build_update_instruction
from .finalize_review_decisions import ConflictResolutionDecisionSet


def _source_identity(decisions: ConflictResolutionDecisionSet) -> str:
    payload = {
        "revision": decisions.revision,
        "decisions": [
            {
                "issue_uid": decision.issue_uid,
                "kind": decision.kind,
                "intent": decision.intent,
            }
            for decision in decisions.decisions
            if decision.kind != "FORCE"
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolution_input_uid(
    decisions: ConflictResolutionDecisionSet, issue_uid: str
) -> str:
    """Identity linking planned effects to the exact authored review input."""
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"memcommit:conflict-resolution:{_source_identity(decisions)}:{issue_uid}",
        )
    )


def build_update_input_from_decisions(
    analysis: ConflictResolutionAnalysis, decisions: ConflictResolutionDecisionSet
) -> Context:
    """Build the process-local Source Context consumed by ordinary Update."""
    if decisions.revision != analysis.frame.revision:
        raise ConflictResolutionError(
            "Conflict decisions no longer match this Context revision."
        )
    issues = {issue.uid: issue for issue in analysis.issues}
    digest = _source_identity(decisions)
    source = Context(
        uid=str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"memcommit:conflict-resolution:{digest}")
        ),
        name=f"CONFLICT INPUT · {analysis.frame.display_name}",
    )
    for decision in decisions.decisions:
        if decision.kind not in {"CONFIRM", "INTENT"}:
            continue
        issue = issues[decision.issue_uid]
        content = build_update_instruction(analysis, issue, decision)
        memory_uid = resolution_input_uid(decisions, decision.issue_uid)
        source.add(Memory(uid=memory_uid, content=content))
    return source
