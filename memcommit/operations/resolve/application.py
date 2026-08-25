"""Operation package contracts for repairing a non-fitting Memory frame.

Resolution is the semantic condition-to-condition operation: it selects one
reasonable Issue interpretation and proposes an authorized post-image whose
complete proposition frame independently Fits.
The shared :mod:`memcommit.resolution` package validates exact choices only;
automatic planning, assumption boundaries, and Apply remain here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from memcommit.operations.fit.judgment import FitAssessment
from memcommit.resolution import (
    ResolutionAttempt,
    ResolutionBinding,
    ResolutionCase,
    ResolutionRequirement,
    ResolutionSubmission,
    require_resolution_ready,
)

if TYPE_CHECKING:
    from memcommit.update import GrantedUpdateTarget


RESOLVE_CONTRACT_VERSION = "resolve-exact-rules-v3"
ResolveEffectKind = Literal["CREATE", "UPDATE", "DELETE"]
ResolveFitTarget = Literal["MAY", "YES"]
ResolveStatus = Literal[
    "ALREADY_FIT",
    "ASSUMED",
    "NEEDS_AUTHORITY",
    "NEEDS_INPUT",
    "PROPOSAL",
]


class ResolveError(RuntimeError):
    """A Resolve request, semantic result, or Apply boundary is invalid."""


class ResolveAuthorityError(ResolveError):
    """The frozen authority no longer permits the reviewed Resolve plan."""


class ResolveConflictError(ResolveError):
    """A frozen Context or exact Resolve choice changed before Apply."""


class ResolveProvider(Protocol):
    """The bounded completion primitive used by Resolve and Fit verification."""

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one complete structured semantic response."""


class ResolveProviderFactory(Protocol):
    def __call__(self) -> ResolveProvider:
        """Connect after the complete local frame and authority are frozen."""


@dataclass(frozen=True)
class ResolveSourcePrecondition:
    """Finder-owned direct-Memory source that must still back Resolve.

    The public display name is retained because a granted Context may have a
    different authority-local name. Authority and effect permissions are not
    carried across this boundary; the Resolve frame port freezes them again.
    """

    context_uid: str
    display_name: str
    direct_memory_digest: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.context_uid, self.display_name)
        ):
            raise ResolveError(
                "Resolve source precondition requires a Context identity."
            )
        if (
            not isinstance(self.direct_memory_digest, str)
            or len(self.direct_memory_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.direct_memory_digest
            )
        ):
            raise ResolveError(
                "Resolve source precondition requires a SHA-256 Memory digest."
            )


@dataclass(frozen=True)
class ResolveRequest:
    """One direct-Memory Fit repair request.

    UPDATE and information-preserving CREATE are ordinary Resolve effects.
    DELETE is an explicit expansion and additionally requires nonempty grounding
    guidance because Fit alone can never justify retiring a proposition.
    """

    context_name: str | None = None
    memory_selectors: tuple[str, ...] = ()
    # Resolve starts from information preservation: adding one grounded
    # interpretation or editing existing wording is ordinary, while DELETE
    # remains the exceptional effect that needs an explicit retirement basis.
    allow_create: bool = True
    allow_delete: bool = False
    guidance: str = ""
    target_fit: ResolveFitTarget = "MAY"
    source_precondition: ResolveSourcePrecondition | None = None

    def __post_init__(self) -> None:
        if self.context_name is not None and (
            not isinstance(self.context_name, str) or not self.context_name.strip()
        ):
            raise ResolveError("Resolve Context name must be nonblank when supplied.")
        if not isinstance(self.memory_selectors, tuple) or any(
            not isinstance(selector, str)
            or not selector
            or any(character in selector for character in "\r\n")
            for selector in self.memory_selectors
        ):
            raise ResolveError(
                "Resolve Memory selectors must be one-line uid prefixes."
            )
        if len(set(self.memory_selectors)) != len(self.memory_selectors):
            raise ResolveError("Resolve Memory selectors must not repeat.")
        if not isinstance(self.allow_create, bool) or not isinstance(
            self.allow_delete, bool
        ):
            raise ResolveError("Resolve effect opt-ins must be boolean values.")
        if not isinstance(self.guidance, str):
            raise ResolveError("Resolve guidance must be text.")
        if self.target_fit not in {"MAY", "YES"}:
            raise ResolveError("Resolve target Fit must be MAY or YES.")
        if self.source_precondition is not None and not isinstance(
            self.source_precondition,
            ResolveSourcePrecondition,
        ):
            raise ResolveError(
                "Resolve source precondition must use the typed contract."
            )
        if self.allow_delete and not self.guidance.strip():
            raise ResolveError(
                "Resolve --allow-delete requires grounding guidance that explains "
                "when retiring a Memory is valid."
            )

    @property
    def requested_effects(self) -> tuple[ResolveEffectKind, ...]:
        result: list[ResolveEffectKind] = ["UPDATE"]
        if self.allow_create:
            result.append("CREATE")
        if self.allow_delete:
            result.append("DELETE")
        return tuple(result)


@dataclass(frozen=True)
class ResolveFrameMemory:
    """One directly owned Memory in the frozen complete Fit frame."""

    alias: str
    uid: str
    content: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.alias, self.uid, self.content)
        ):
            raise ResolveError("Resolve frame Memories require complete values.")


@dataclass(frozen=True)
class FrozenResolveFrame:
    """Exact source, target capability, and freshness boundary for Resolve."""

    request: ResolveRequest
    context_uid: str
    context_name: str
    display_name: str
    context_digest: str
    revision: str
    memories: tuple[ResolveFrameMemory, ...]
    actionable_uids: tuple[str, ...]
    allowed_effects: tuple[ResolveEffectKind, ...]
    denied_effects: tuple[ResolveEffectKind, ...] = ()
    missing_authority: tuple[str, ...] = ()
    granted_binding: "GrantedUpdateTarget | None" = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, ResolveRequest):
            raise TypeError("Resolve frame requires a typed request.")
        for value, label in (
            (self.context_uid, "Context uid"),
            (self.context_name, "Context name"),
            (self.display_name, "display name"),
            (self.context_digest, "Context digest"),
            (self.revision, "revision"),
        ):
            if not isinstance(value, str) or not value:
                raise ResolveError(f"Resolve frame {label} must be nonempty text.")
        if len(self.memories) < 2 or any(
            not isinstance(memory, ResolveFrameMemory) for memory in self.memories
        ):
            raise ResolveError("Resolve requires at least two direct Memories.")
        memory_uids = tuple(memory.uid for memory in self.memories)
        aliases = tuple(memory.alias for memory in self.memories)
        if len(set(memory_uids)) != len(memory_uids) or len(set(aliases)) != len(
            aliases
        ):
            raise ResolveError("Resolve frame Memory identities must be unique.")
        if (
            not self.actionable_uids
            or len(set(self.actionable_uids)) != len(self.actionable_uids)
            or any(uid not in memory_uids for uid in self.actionable_uids)
        ):
            raise ResolveError("Resolve actionable Memory identities are invalid.")
        requested = set(self.request.requested_effects)
        if (
            len(set(self.allowed_effects)) != len(self.allowed_effects)
            or len(set(self.denied_effects)) != len(self.denied_effects)
            or set(self.allowed_effects) | set(self.denied_effects) != requested
            or set(self.allowed_effects) & set(self.denied_effects)
        ):
            raise ResolveError("Resolve effect capability projection is invalid.")
        if any(
            not isinstance(permission, str) or not permission
            for permission in self.missing_authority
        ):
            raise ResolveError("Resolve missing authority values are invalid.")

    @property
    def binding(self) -> ResolutionBinding:
        return ResolutionBinding(
            operation="resolve",
            artifact_uid=self.context_uid,
            revision=self.revision,
        )


@dataclass(frozen=True)
class ResolveEffect:
    """One exact primitive mutation in a candidate Context post-image."""

    kind: ResolveEffectKind
    owner_context_uid: str
    owner_context_name: str
    memory_uid: str
    old_content: str | None
    new_content: str | None
    source_memory_uids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.kind not in {"CREATE", "UPDATE", "DELETE"}:
            raise ResolveError("Resolve effect kind is invalid.")
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.owner_context_uid,
                self.owner_context_name,
                self.memory_uid,
                self.reason,
            )
        ):
            raise ResolveError("Resolve effect identity and reason must be complete.")
        if (
            not isinstance(self.source_memory_uids, tuple)
            or not self.source_memory_uids
            or len(set(self.source_memory_uids)) != len(self.source_memory_uids)
            or any(
                not isinstance(uid, str) or not uid for uid in self.source_memory_uids
            )
        ):
            raise ResolveError("Resolve effects require distinct source Memory uids.")
        if self.kind == "CREATE":
            valid = self.old_content is None and bool(
                isinstance(self.new_content, str) and self.new_content.strip()
            )
        elif self.kind == "UPDATE":
            valid = (
                isinstance(self.old_content, str)
                and isinstance(self.new_content, str)
                and bool(self.new_content.strip())
                and self.old_content != self.new_content
            )
        else:
            valid = isinstance(self.old_content, str) and self.new_content is None
        if not valid:
            raise ResolveError(f"Resolve {self.kind} effect has an invalid transition.")

    def canonical_value(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "owner_context_uid": self.owner_context_uid,
            "owner_context_name": self.owner_context_name,
            "memory_uid": self.memory_uid,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "source_memory_uids": list(self.source_memory_uids),
            "reason": self.reason,
        }

    def mutation_value(self) -> dict[str, object]:
        """Return the exact durable effect without explanatory provider prose."""

        return {
            "kind": self.kind,
            "owner_context_uid": self.owner_context_uid,
            "owner_context_name": self.owner_context_name,
            "memory_uid": self.memory_uid,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "source_memory_uids": list(self.source_memory_uids),
        }


@dataclass(frozen=True)
class ResolveIssue:
    """One incompatibility point interpreted inside the complete frame.

    An Issue narrows the mutation focus, never the semantic read boundary.  The
    provider sees every direct Memory on every turn and must cite exact members
    and bases from that frozen frame.  ``assumptions`` records a reasonable
    working interpretation that is not grounded strongly enough for durable
    Apply.
    """

    uid: str
    kind: str
    memory_uids: tuple[str, ...]
    selected_interpretation: str
    basis_memory_uids: tuple[str, ...]
    assumptions: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.uid,
                self.kind,
                self.selected_interpretation,
                self.reason,
            )
        ):
            raise ResolveError("Resolve Issues require complete text values.")
        for values, label in (
            (self.memory_uids, "members"),
            (self.basis_memory_uids, "basis"),
        ):
            if (
                not isinstance(values, tuple)
                or not values
                or len(set(values)) != len(values)
                or any(not isinstance(value, str) or not value for value in values)
            ):
                raise ResolveError(f"Resolve Issue {label} are invalid.")
        if not isinstance(self.assumptions, tuple) or any(
            not isinstance(assumption, str) or not assumption.strip()
            for assumption in self.assumptions
        ):
            raise ResolveError("Resolve Issue assumptions are invalid.")


@dataclass(frozen=True, order=True)
class ResolveCost:
    """A transparent diagnostic vector for one automatic interpretation plan."""

    deletes: int
    creates: int
    updates: int
    changed_units: int

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in (
                self.deletes,
                self.creates,
                self.updates,
                self.changed_units,
            )
        ):
            raise ResolveError("Resolve minimum-change costs must be nonnegative.")

    def dominates(self, other: "ResolveCost") -> bool:
        mine = (self.deletes, self.creates, self.updates, self.changed_units)
        theirs = (other.deletes, other.creates, other.updates, other.changed_units)
        return all(left <= right for left, right in zip(mine, theirs)) and any(
            left < right for left, right in zip(mine, theirs)
        )


@dataclass(frozen=True)
class ResolveCandidate:
    """One grounded or assumed, independently Fit-verified automatic plan."""

    uid: str
    summary: str
    classification: str
    resolution_level: ResolveFitTarget
    rule_ids: tuple[str, ...]
    issues: tuple[ResolveIssue, ...]
    effects: tuple[ResolveEffect, ...]
    grounded: bool
    verification_reason: str
    fit: FitAssessment
    cost: ResolveCost

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.uid,
                self.summary,
                self.classification,
                self.verification_reason,
            )
        ):
            raise ResolveError("Resolve candidate requires complete text values.")
        if self.resolution_level not in {"MAY", "YES"}:
            raise ResolveError("Resolve candidate level must be MAY or YES.")
        if (
            not self.rule_ids
            or len(self.rule_ids) != len(set(self.rule_ids))
            or any(
                not isinstance(rule_id, str) or not rule_id for rule_id in self.rule_ids
            )
        ):
            raise ResolveError("Resolve candidate requires distinct rule IDs.")
        if (
            not self.issues
            or any(not isinstance(issue, ResolveIssue) for issue in self.issues)
            or len({issue.uid for issue in self.issues}) != len(self.issues)
        ):
            raise ResolveError("Resolve candidate requires distinct typed Issues.")
        if not self.effects or any(
            not isinstance(effect, ResolveEffect) for effect in self.effects
        ):
            raise ResolveError("Resolve candidate requires exact effects.")
        if not isinstance(self.grounded, bool):
            raise TypeError("Resolve candidate grounded state must be boolean.")
        if self.grounded and any(issue.assumptions for issue in self.issues):
            raise ResolveError(
                "A grounded Resolve candidate cannot retain ungrounded assumptions."
            )
        targets = tuple(
            (effect.owner_context_uid, effect.memory_uid) for effect in self.effects
        )
        if len(set(targets)) != len(targets):
            raise ResolveError("Resolve candidate targets one Memory more than once.")
        if not isinstance(self.fit, FitAssessment) or self.fit.verdict not in {
            "MAY",
            "YES",
        }:
            raise ResolveError("Resolve candidate requires independent Fit MAY or YES.")
        if not isinstance(self.cost, ResolveCost):
            raise TypeError("Resolve candidate requires a minimum-change cost.")


@dataclass(frozen=True)
class ResolveAnalysis:
    """One complete process-local proposal over a frozen Context revision."""

    frame: FrozenResolveFrame
    status: ResolveStatus
    initial_fit: FitAssessment | None
    candidates: tuple[ResolveCandidate, ...]
    question: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.frame, FrozenResolveFrame):
            raise TypeError("Resolve analysis requires a frozen frame.")
        if self.status not in {
            "ALREADY_FIT",
            "ASSUMED",
            "NEEDS_AUTHORITY",
            "NEEDS_INPUT",
            "PROPOSAL",
        }:
            raise ResolveError("Resolve analysis status is invalid.")
        if self.initial_fit is not None and not isinstance(
            self.initial_fit, FitAssessment
        ):
            raise TypeError("Resolve analysis Fit result is invalid.")
        if any(
            not isinstance(candidate, ResolveCandidate) for candidate in self.candidates
        ) or len({candidate.uid for candidate in self.candidates}) != len(
            self.candidates
        ):
            raise ResolveError("Resolve analysis candidates are invalid.")
        if self.status == "PROPOSAL" and (
            len(self.candidates) != 1 or not self.candidates[0].grounded
        ):
            raise ResolveError(
                "Resolve PROPOSAL requires exactly one grounded candidate."
            )
        if self.status == "ASSUMED" and (
            len(self.candidates) != 1 or self.candidates[0].grounded
        ):
            raise ResolveError(
                "Resolve ASSUMED requires one non-grounded working interpretation."
            )
        if self.status in {"ALREADY_FIT", "NEEDS_AUTHORITY", "NEEDS_INPUT"} and (
            self.candidates
        ):
            raise ResolveError("Terminal Resolve statuses cannot carry candidates.")
        if not isinstance(self.question, str):
            raise TypeError("Resolve analysis question must be text.")


@dataclass(frozen=True)
class ResolveReceipt:
    """Durable receipt for one exact candidate application."""

    context_uid: str
    context_name: str
    revision: str
    candidate_uid: str
    checkpoint_uid: str
    created_uids: tuple[str, ...]
    updated_uids: tuple[str, ...]
    deleted_uids: tuple[str, ...]


class ResolveFramePort(Protocol):
    """Freeze, revalidate, and apply one Resolve frame."""

    def freeze(self, request: ResolveRequest) -> FrozenResolveFrame:
        """Freeze direct Memories and effective effect capabilities."""

    def revalidate(self, frame: FrozenResolveFrame) -> None:
        """Fail when the Context or Grant changed during semantic execution."""

    def apply(
        self,
        frame: FrozenResolveFrame,
        candidate: ResolveCandidate,
    ) -> ResolveReceipt:
        """Apply an exact verified candidate or publish none of it."""


class ResolveSemanticPort(Protocol):
    def preflight(self, frame: FrozenResolveFrame) -> None:
        """Reject unsupported whole-frame work before provider connection."""

    def analyze(
        self,
        frame: FrozenResolveFrame,
        *,
        provider: ResolveProvider,
    ) -> ResolveAnalysis:
        """Generate and verify one automatic plan over one frozen frame."""


def resolve_case(analysis: ResolveAnalysis) -> ResolutionCase:
    """Project the automatic plan into the exact-approval lifecycle."""

    return ResolutionCase(
        binding=analysis.frame.binding,
        requirements=(
            ResolutionRequirement(
                item_uid="resolve-plan",
                choice_uids=tuple(candidate.uid for candidate in analysis.candidates),
            ),
        ),
    )


def candidate_digest(
    frame: FrozenResolveFrame,
    effects: tuple[ResolveEffect, ...],
    *,
    resolution_level: ResolveFitTarget,
) -> str:
    """Bind one stable candidate identity to its exact frame and effects."""

    payload = {
        "contract": RESOLVE_CONTRACT_VERSION,
        "revision": frame.revision,
        "resolution_level": resolution_level,
        "effects": [effect.mutation_value() for effect in effects],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "resolve-" + hashlib.sha256(encoded).hexdigest()


def _direct_memory_digest(frame: FrozenResolveFrame) -> str:
    payload = [
        {"uid": memory.uid, "content": memory.content} for memory in frame.memories
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_source_precondition(frame: FrozenResolveFrame) -> None:
    expected = frame.request.source_precondition
    if expected is None:
        return
    if (
        frame.context_uid != expected.context_uid
        or frame.display_name != expected.display_name
        or _direct_memory_digest(frame) != expected.direct_memory_digest
    ):
        # Finder reports are observations, not mutation authority. Re-freezing
        # may therefore reauthorize, but it must never retarget stale evidence.
        raise ResolveConflictError(
            "The quality finding source no longer matches the frozen Resolve "
            "Context. Run the finder again before resolving it."
        )


def run_resolve(
    request: ResolveRequest,
    *,
    frame_port: ResolveFramePort,
    semantic_port: ResolveSemanticPort,
    provider_factory: ResolveProviderFactory,
    expected_revision: str | None = None,
) -> ResolveAnalysis:
    """Execute one all-or-nothing semantic analysis without applying it."""

    if not isinstance(request, ResolveRequest):
        raise TypeError("Resolve requires a typed request.")
    frame = frame_port.freeze(request)
    _require_source_precondition(frame)
    if expected_revision is not None and expected_revision != frame.revision:
        raise ResolveConflictError(
            "The Resolve Context or requested capability frame changed before "
            "the exact candidate could be regenerated."
        )
    if frame.missing_authority or not frame.allowed_effects:
        missing = frame.missing_authority or tuple(frame.denied_effects)
        return ResolveAnalysis(
            frame=frame,
            status="NEEDS_AUTHORITY",
            initial_fit=None,
            candidates=(),
            question=(
                "Grant authority is missing: " + ", ".join(missing)
                if missing
                else "No requested Resolve mutation effect is authorized."
            ),
        )
    semantic_port.preflight(frame)
    provider = provider_factory()
    analysis = semantic_port.analyze(frame, provider=provider)
    # No report is published from a stale semantic turn. Apply performs the
    # same check again under the mutation and Grant locks.
    frame_port.revalidate(frame)
    return analysis


def apply_resolve(
    analysis: ResolveAnalysis,
    candidate_uid: str,
    *,
    frame_port: ResolveFramePort,
) -> ResolveReceipt:
    """Validate one exact candidate choice, then cross the Apply boundary."""

    if not isinstance(analysis, ResolveAnalysis):
        raise TypeError("Resolve Apply requires a typed analysis.")
    if analysis.status != "PROPOSAL":
        if analysis.status == "ASSUMED":
            raise ResolveError(
                "Resolve working assumptions are process-local and cannot be applied."
            )
        raise ResolveError("Resolve analysis has no applicable verified candidate.")
    case = resolve_case(analysis)
    try:
        progress = require_resolution_ready(
            case,
            ResolutionAttempt(
                binding=case.binding,
                submissions=(
                    ResolutionSubmission(
                        item_uid="resolve-plan",
                        choice_uid=candidate_uid,
                    ),
                ),
            ),
        )
    except (TypeError, ValueError) as error:
        raise ResolveError(str(error)) from error
    selected_uid = progress.submissions[0].choice_uid
    candidate = next(
        (
            candidate
            for candidate in analysis.candidates
            if candidate.uid == selected_uid
        ),
        None,
    )
    if candidate is None:  # pragma: no cover - guarded by the common validator.
        raise ResolveError("Resolve candidate is unavailable.")
    if not candidate.grounded:  # pragma: no cover - guarded by ResolveAnalysis.
        raise ResolveError("An ungrounded Resolve interpretation cannot be applied.")
    return frame_port.apply(analysis.frame, candidate)


__all__ = [
    "RESOLVE_CONTRACT_VERSION",
    "FrozenResolveFrame",
    "ResolveAnalysis",
    "ResolveAuthorityError",
    "ResolveCandidate",
    "ResolveConflictError",
    "ResolveCost",
    "ResolveEffect",
    "ResolveEffectKind",
    "ResolveError",
    "ResolveFrameMemory",
    "ResolveFramePort",
    "ResolveFitTarget",
    "ResolveIssue",
    "ResolveProvider",
    "ResolveProviderFactory",
    "ResolveReceipt",
    "ResolveRequest",
    "ResolveSourcePrecondition",
    "ResolveSemanticPort",
    "ResolveStatus",
    "apply_resolve",
    "candidate_digest",
    "resolve_case",
    "run_resolve",
]
