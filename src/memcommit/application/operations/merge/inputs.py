"""Common Merge request and frozen input values with their own invariants."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Literal

from memcommit.core.context import Context

from .analysis.candidate import MergeCandidate, combine_contexts, digest
from .target_policy import MergeTargetPolicy

if TYPE_CHECKING:
    from memcommit.application.context_access.access import ContextAccess

MergeMethod = Literal["LITERAL", "SEMANTIC"]


class MergeDecision(str, Enum):
    KEEP_TARGET = "KEEP_TARGET"
    TAKE_SOURCE = "TAKE_SOURCE"
    KEEP_BOTH = "KEEP_BOTH"


@dataclass(frozen=True)
class MergeRequest:
    source: str
    target: str
    method: MergeMethod = "SEMANTIC"

    def __post_init__(self):
        if self.method not in {"LITERAL", "SEMANTIC"}:
            raise ValueError("Unknown Merge method.")
        if any(
            not isinstance(name, str) or not name for name in (self.source, self.target)
        ):
            raise ValueError("Merge requires two existing Context names.")
        if self.source == self.target:
            raise ValueError("Merge Source and Target must be distinct Contexts.")


@dataclass(frozen=True)
class MergeContextInputs:
    """One frozen Source/Target pair and authority, independent of Merge method."""

    operation_uid: str
    source_json: str
    target_json: str
    source_digest: str
    target_digest: str
    source_access: ContextAccess = field(repr=False, compare=False)
    target_access: ContextAccess = field(repr=False, compare=False)
    policy: MergeTargetPolicy
    lineage_targets: tuple[tuple[str, str], ...] = ()
    cross_profile_memory_only: bool = False

    def source(self) -> Context:
        return Context.from_dict(json.loads(self.source_json))

    def target(self) -> Context:
        return Context.from_dict(json.loads(self.target_json))

    @property
    def digest(self):
        from memcommit.application.context_access.access import (
            freeze_granted_context_binding,
        )

        def authority(access):
            return {
                "store": str(access.store.store_dir),
                "physical_name": access.context_name,
                "public_name": access.access_name,
                "permission": access.permission,
                "grant": freeze_granted_context_binding(access).to_dict()
                if access.is_granted
                else None,
            }

        return digest(
            {
                "operation": self.operation_uid,
                "source": self.source_json,
                "target": self.target_json,
                "source_authority": authority(self.source_access),
                "target_authority": authority(self.target_access),
                "source_digest": self.source_digest,
                "target_digest": self.target_digest,
                "effects": self.policy.allowed_effects,
                "mutable": self.policy.context_mutable,
                "protected": sorted(self.policy.protected_uids),
                "lineage": self.lineage_targets,
                "cross_profile": self.cross_profile_memory_only,
            }
        )


@dataclass(frozen=True, slots=True)
class StructuralAddition:
    source_uid: str
    target_uid: str | None


@dataclass(frozen=True, slots=True)
class StructuralConflict:
    issue_uid: str
    source_uid: str
    target_uids: tuple[str, ...]
    allowed_choices: tuple[str, ...]
    keep_both_uid: str | None


@dataclass(frozen=True, slots=True)
class StructuralResolutionInput:
    """Original endpoint values and exact allocations frozen by Merge."""

    revision: str
    source_json: str
    target_json: str
    additions: tuple[StructuralAddition, ...]
    conflicts: tuple[StructuralConflict, ...]

    def source(self) -> Context:
        return Context.from_dict(json.loads(self.source_json))

    def target(self) -> Context:
        return Context.from_dict(json.loads(self.target_json))


@dataclass(frozen=True)
class LiteralMergeInput:
    """A complete candidate and destination policy before structural analysis."""

    candidate: MergeCandidate
    source_json: str
    target_json: str
    target_policy: MergeTargetPolicy
    method: str
    binding_digest: str

    @property
    def digest(self):
        return digest(
            {
                "candidate": self.candidate.to_dict(),
                "source": self.source_json,
                "target": self.target_json,
                "policy": {
                    **asdict(self.target_policy),
                    "protected_uids": sorted(self.target_policy.protected_uids),
                },
                "method": self.method,
                "binding": self.binding_digest,
            }
        )


@dataclass(frozen=True)
class PreparedMerge:
    """Unaudited candidate bound to frozen endpoints and their original authority."""

    request: MergeRequest
    inputs: MergeContextInputs
    literal_input: LiteralMergeInput
    _frozen_digest: str = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        self._validate_inputs()
        object.__setattr__(self, "_frozen_digest", self.digest)

    def _validate_inputs(self):
        review = self.literal_input
        if not isinstance(review, LiteralMergeInput):
            raise ValueError("Prepared Merge requires its Resolve input.")
        if review.method != self.request.method:
            raise ValueError("Prepared Merge has a different method's review settings.")
        if (
            self.inputs.source_access.access_name,
            self.inputs.target_access.access_name,
        ) != (self.request.source, self.request.target):
            raise ValueError("Prepared Merge endpoints differ from its request.")
        if (
            review.binding_digest != self.inputs.digest
            or review.source_json != self.inputs.source_json
            or review.target_json != self.inputs.target_json
            or review.target_policy != self.inputs.policy
            or review.candidate
            != combine_contexts(
                (self.inputs.target(), self.inputs.source()),
                placement=self.request.target,
                identities={
                    (1, uid): target_uid
                    for uid, target_uid in self.inputs.lineage_targets
                },
            )
        ):
            raise ValueError("Prepared Merge changed its frozen input or authority.")

    def require_unchanged(self):
        # Frozen dataclasses can still contain mutable access objects. Retain the
        # original digest so a changed authority cannot redirect a reviewed result.
        if self.digest != self._frozen_digest:
            raise ValueError("Prepared Merge changed its frozen input or authority.")

    @property
    def digest(self):
        return digest(
            {
                "request": asdict(self.request),
                "inputs": self.inputs.digest,
                "literal_input": self.literal_input.digest,
            }
        )
