"""Operation contracts for resolving one complete Audit from human intent.

Audit owns issue discovery. Resolve owns direction and the human decision boundary.
The existing Update operation alone generates exact target mutations from the
finalized decisions; Resolve retains authority, verification, and publication.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from memcommit.application.capabilities.resolution import ResolutionBinding
from memcommit.application.operations.audit.application import get_or_run_quality_audit
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.audit.repository import AuditRecordRepository

if TYPE_CHECKING:
    from memcommit.application.operations.resolve.decisions import ResolveFinalizedInput
    from memcommit.application.operations.update.model import GrantedUpdateTarget, UpdatePlan
    from memcommit.core.context import Context


RESOLVE_CONTRACT_VERSION = "resolve-audit-direction-update"
ResolveEffectKind = Literal["CREATE", "UPDATE", "DELETE"]
ResolveIssueKind = Literal[
    "REDUNDANCY",
    "AMBIGUITY",
    "CONFLICT",
    "FIT",
    "CONFORMANCE",
]
ResolveStatus = Literal[
    "NO_ISSUES",
    "NEEDS_AUTHORITY",
    "NEEDS_INPUT",
]


class ResolveError(RuntimeError):
    """A Resolve request, semantic result, or Apply boundary is invalid."""


class ResolveAuthorityError(ResolveError):
    """The frozen authority no longer permits the reviewed Resolve plan."""


class ResolveConflictError(ResolveError):
    """A frozen Context or exact Resolve choice changed before Apply."""


class ResolveProvider(Protocol):
    """The bounded completion primitive used by Resolve semantic turns."""

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
    """One direct-Memory Audit-resolution request.

    UPDATE and information-preserving CREATE are ordinary Resolve effects.
    DELETE is an explicit expansion and additionally requires nonempty grounding
    guidance because conflict removal alone cannot justify retiring information.
    """

    context_name: str | None = None
    memory_selectors: tuple[str, ...] = ()
    # Resolve starts from information preservation: adding one grounded
    # interpretation or editing existing wording is ordinary, while DELETE
    # remains the exceptional effect that needs an explicit retirement basis.
    allow_create: bool = True
    allow_delete: bool = False
    guidance: str = ""
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
    """One directly owned Memory in the frozen complete Audit frame."""

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
class ResolveIssue:
    """One immutable Audit item plus its separately derived Resolve direction."""

    uid: str
    audit_key: str
    audit_snapshot_digest: str
    kind: ResolveIssueKind
    classification: str
    memory_uids: tuple[str, ...]
    proposed_direction: str
    reason: str
    question: str = ""

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.uid,
                self.audit_key,
                self.audit_snapshot_digest,
                self.kind,
                self.classification,
                self.proposed_direction,
                self.reason,
            )
        ):
            raise ResolveError("Resolve Issues require complete text values.")
        if self.kind not in {
            "REDUNDANCY",
            "AMBIGUITY",
            "CONFLICT",
            "FIT",
            "CONFORMANCE",
        }:
            raise ResolveError("Resolve Issue kind is invalid.")
        if (
            not isinstance(self.memory_uids, tuple)
            or len(set(self.memory_uids)) != len(self.memory_uids)
            or any(not isinstance(value, str) or not value for value in self.memory_uids)
            or (self.kind != "CONFORMANCE" and not self.memory_uids)
        ):
            raise ResolveError("Resolve Issue members are invalid.")
        if not isinstance(self.question, str):
            raise TypeError("Resolve Issue question must be text.")


@dataclass(frozen=True)
class ResolveAnalysis:
    """One exact Audit and its answerable directions over a frozen revision."""

    frame: FrozenResolveFrame
    status: ResolveStatus
    audit: QualityAuditSession | None = None
    question: str = ""
    issues: tuple[ResolveIssue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.frame, FrozenResolveFrame):
            raise TypeError("Resolve analysis requires a frozen frame.")
        if self.status not in {
            "NO_ISSUES",
            "NEEDS_AUTHORITY",
            "NEEDS_INPUT",
        }:
            raise ResolveError("Resolve analysis status is invalid.")
        if not isinstance(self.question, str):
            raise TypeError("Resolve analysis question must be text.")
        if (
            not isinstance(self.issues, tuple)
            or any(not isinstance(issue, ResolveIssue) for issue in self.issues)
            or len({issue.uid for issue in self.issues}) != len(self.issues)
        ):
            raise ResolveError("Resolve review Issues are invalid.")
        frame_uids = {memory.uid for memory in self.frame.memories}
        if any(
            not set(issue.memory_uids) <= frame_uids
            for issue in self.issues
        ):
            raise ResolveError("Resolve review Issues name Memories outside the frame.")
        if self.status == "NEEDS_AUTHORITY":
            if self.audit is not None or self.issues:
                raise ResolveError("Authority failure cannot publish Audit evidence.")
            return
        if not isinstance(self.audit, QualityAuditSession):
            raise ResolveError("Resolve analysis requires one completed Audit.")
        if (
            self.audit.source.context_uid != self.frame.context_uid
            or self.audit.source.context_digest != _direct_memory_digest(self.frame)
        ):
            raise ResolveError("Resolve Audit does not match its frozen Context.")
        if any(
            issue.audit_snapshot_digest != self.audit.snapshot_digest
            for issue in self.issues
        ):
            raise ResolveError("Resolve direction does not match its Audit snapshot.")
        if self.status == "NO_ISSUES" and self.issues:
            raise ResolveError("A no-Issues Resolve analysis cannot contain decisions.")
        if self.status == "NEEDS_INPUT" and not self.issues:
            raise ResolveError("Resolve needs input only when Audit items exist.")

    @property
    def review_issues(self) -> tuple[ResolveIssue, ...]:
        """Return the unresolved meanings presented for human decision."""

        return self.issues


@dataclass(frozen=True)
class ResolveReceipt:
    """Durable receipt for one exact Resolve-owned Update application."""

    context_uid: str
    context_name: str
    revision: str
    plan_uid: str
    checkpoint_uid: str
    created_uids: tuple[str, ...]
    updated_uids: tuple[str, ...]
    deleted_uids: tuple[str, ...]
    unresolved_issue_uids: tuple[str, ...] = ()


class ResolveFramePort(Protocol):
    """Freeze, revalidate, and apply one Resolve frame."""

    def freeze(self, request: ResolveRequest) -> FrozenResolveFrame:
        """Freeze direct Memories and effective effect capabilities."""

    def revalidate(self, frame: FrozenResolveFrame) -> None:
        """Fail when the Context or Grant changed during semantic execution."""

    def load_target(self, frame: FrozenResolveFrame) -> Context:
        """Return the exact detached whole Context frozen for Update planning."""

    def apply_update_plan(
        self,
        frame: FrozenResolveFrame,
        plan: UpdatePlan,
        *,
        unresolved_issue_uids: tuple[str, ...] = (),
        finalized_inputs: tuple[ResolveFinalizedInput, ...] = (),
    ) -> ResolveReceipt:
        """Publish one Resolve-generated exact Update plan atomically."""


class ResolveSemanticPort(Protocol):
    def preflight(
        self,
        frame: FrozenResolveFrame,
        audit: QualityAuditSession,
    ) -> None:
        """Reject unsupported complete-Audit direction work before connection."""

    def analyze(
        self,
        frame: FrozenResolveFrame,
        audit: QualityAuditSession,
        *,
        provider: ResolveProvider,
    ) -> ResolveAnalysis:
        """Generate exactly one non-mutating direction per actionable Audit item."""


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
    audit_repository: AuditRecordRepository,
    audit_provider_factory: ResolveProviderFactory,
    direction_provider_factory: ResolveProviderFactory,
    conformance_rules: Context | None = None,
    expected_revision: str | None = None,
) -> ResolveAnalysis:
    """Acquire one exact Audit, then derive directions without applying them."""

    if not isinstance(request, ResolveRequest):
        raise TypeError("Resolve requires a typed request.")
    frame = frame_port.freeze(request)
    _require_source_precondition(frame)
    if expected_revision is not None and expected_revision != frame.revision:
        raise ResolveConflictError(
            "The Resolve Context or requested capability frame changed before "
            "its decisions could be finalized."
        )
    if frame.missing_authority or not frame.allowed_effects:
        missing = frame.missing_authority or tuple(frame.denied_effects)
        return ResolveAnalysis(
            frame=frame,
            status="NEEDS_AUTHORITY",
            question=(
                "Grant authority is missing: " + ", ".join(missing)
                if missing
                else "No requested Resolve mutation effect is authorized."
            ),
        )
    target = frame_port.load_target(frame)
    audit = get_or_run_quality_audit(
        target,
        audit_provider_factory,
        audit_repository,
        conformance_rules=conformance_rules,
    )
    semantic_port.preflight(frame, audit)
    provider = direction_provider_factory()
    analysis = semantic_port.analyze(frame, audit, provider=provider)
    # No report is published from a stale semantic turn. Apply performs the
    # same check again under the mutation and Grant locks.
    frame_port.revalidate(frame)
    return analysis


__all__ = [
    "RESOLVE_CONTRACT_VERSION",
    "FrozenResolveFrame",
    "ResolveAnalysis",
    "ResolveAuthorityError",
    "ResolveConflictError",
    "ResolveEffectKind",
    "ResolveError",
    "ResolveFrameMemory",
    "ResolveFramePort",
    "ResolveIssue",
    "ResolveIssueKind",
    "ResolveProvider",
    "ResolveProviderFactory",
    "ResolveReceipt",
    "ResolveRequest",
    "ResolveSourcePrecondition",
    "ResolveSemanticPort",
    "ResolveStatus",
    "run_resolve",
]
