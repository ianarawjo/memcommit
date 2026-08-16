"""Pure planning boundary from semantic Ground artifacts to reviewed actions.

Resolve never mutates a Ground and never upgrades a model result into accepted
knowledge.  It freezes one exact artifact and projects at most one existing
deterministic Ground action for a later approval and CAS-protected application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Literal, TypeAlias

GroundResolutionArtifactKind: TypeAlias = Literal[
    "FIT",
    "DISTILL",
    "ELABORATE",
]
GroundResolutionVerification: TypeAlias = Literal[
    "REVISION_BOUND_JUDGMENT",
    "EVIDENCE_BOUND",
    "UNVERIFIED",
]
GroundResolutionActionKind: TypeAlias = Literal[
    "REVISE_GOAL",
    "PROPOSE_RULE",
    "PROPOSE_EXAMPLE",
    "REFINE_RULE",
    "REFINE_EXAMPLE",
    "SET_EXAMPLE_USE",
    "DEFER",
]
GroundResolutionUse: TypeAlias = Literal["INCLUDE", "EXCLUDE", "UNRESOLVED"]


class GroundResolutionError(ValueError):
    """A Resolve source, selection, or Ground snapshot is unsafe to use."""


@dataclass(frozen=True)
class GroundResolutionIdentity:
    ground_uid: str
    ground_name: str
    ground_revision: int
    ground_digest: str


@dataclass(frozen=True)
class GroundResolutionSource:
    """One exact semantic artifact and its unchanged Ground snapshot."""

    kind: GroundResolutionArtifactKind
    artifact_uid: str
    artifact_digest: str
    verification: GroundResolutionVerification
    identity: GroundResolutionIdentity


@dataclass(frozen=True)
class GroundResolutionAction:
    """One unapproved deterministic Ground action."""

    kind: GroundResolutionActionKind
    content: str = ""
    rationale: str = ""
    selector: str = ""
    source_item_uid: str = ""
    case_role: str = ""
    expected: str = ""
    use: str = ""
    rule_provenance: str = ""

    def __post_init__(self) -> None:
        for value in (
            self.content,
            self.rationale,
            self.selector,
            self.source_item_uid,
            self.case_role,
            self.expected,
            self.use,
            self.rule_provenance,
        ):
            if not isinstance(value, str):
                raise GroundResolutionError("Resolve action fields must be text.")


@dataclass(frozen=True)
class GroundResolutionPlan:
    """A reviewable one-action plan; creation has no durable side effect."""

    source: GroundResolutionSource
    action: GroundResolutionAction
    explanation: str
    candidate_verification: GroundResolutionVerification
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise GroundResolutionError("Resolve explanation must be nonblank.")
        payload = {
            "source": {
                "kind": self.source.kind,
                "artifact_uid": self.source.artifact_uid,
                "artifact_digest": self.source.artifact_digest,
                "verification": self.source.verification,
                "ground_uid": self.source.identity.ground_uid,
                "ground_name": self.source.identity.ground_name,
                "ground_revision": self.source.identity.ground_revision,
                "ground_digest": self.source.identity.ground_digest,
            },
            "action": {
                "kind": self.action.kind,
                "content": self.action.content,
                "rationale": self.action.rationale,
                "selector": self.action.selector,
                "source_item_uid": self.action.source_item_uid,
                "case_role": self.action.case_role,
                "expected": self.action.expected,
                "use": self.action.use,
                "rule_provenance": self.action.rule_provenance,
            },
            "explanation": self.explanation,
            "candidate_verification": self.candidate_verification,
        }
        object.__setattr__(
            self,
            "digest",
            hashlib.sha256(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        )


@dataclass(frozen=True)
class GroundFitResolutionChoice:
    """A deliberate response to one non-FIT judgment in an exact receipt."""

    example_uid: str
    action: Literal[
        "REVISE_GOAL",
        "REFINE_RULE",
        "REFINE_EXAMPLE",
        "SET_EXAMPLE_USE",
        "DEFER",
    ]
    content: str = ""
    rationale: str = ""
    rule_uid: str = ""
    use: GroundResolutionUse | str = ""


__all__ = [
    "GroundFitResolutionChoice",
    "GroundResolutionAction",
    "GroundResolutionActionKind",
    "GroundResolutionError",
    "GroundResolutionIdentity",
    "GroundResolutionPlan",
    "GroundResolutionSource",
]
