"""Resolve requests, frozen inputs, analysis and receipt values."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from memcommit.application.capabilities.resolution.workbench import ResolutionOption
from memcommit.application.operations.audit.model import (
    QualityAuditSession,
    AuditTarget,
)


RESOLVE_CONTRACT_VERSION = "resolve-context-conflict-update"
ResolveIssueKind = Literal[
    "REDUNDANCY",
    "AMBIGUITY",
    "CONFLICT",
]
ResolveStatus = Literal[
    "NO_ISSUES",
    "NEEDS_INPUT",
]


class ResolveError(RuntimeError):
    """A Resolve request, semantic result, or Apply boundary is invalid."""


class ResolveConflictError(ResolveError):
    """A frozen Context or exact Resolve choice changed before Apply."""


@dataclass(frozen=True)
class ResolveSourcePrecondition:
    """Finder-owned direct Memory source whose identity and content must still back Resolve."""

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
    """Resolve the whole Context through reviewed additions, edits and removals."""

    context_name: str | None = None
    source_precondition: ResolveSourcePrecondition | None = None

    def __post_init__(self) -> None:
        if self.context_name is not None and (
            not isinstance(self.context_name, str) or not self.context_name.strip()
        ):
            raise ResolveError("Resolve Context name must be nonblank when supplied.")
        if self.source_precondition is not None and not isinstance(
            self.source_precondition,
            ResolveSourcePrecondition,
        ):
            raise ResolveError(
                "Resolve source precondition must use the typed contract."
            )


@dataclass(frozen=True)
class ResolveTarget:
    """Exact whole-Context source and freshness boundary for Resolve."""

    request: ResolveRequest
    display_name: str
    source: AuditTarget
    revision: str
    actionable_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, ResolveRequest):
            raise TypeError("Resolve frame requires a typed request.")
        if not isinstance(self.source, AuditTarget):
            raise ResolveError("Resolve requires a frozen Audit Source.")
        for value, label in (
            (self.display_name, "display name"),
            (self.revision, "revision"),
        ):
            if not isinstance(value, str) or not value:
                raise ResolveError(f"Resolve frame {label} must be nonempty text.")
        item_uids = {item.uid for item in self.source.items}
        if (
            (not self.actionable_uids and item_uids)
            or len(set(self.actionable_uids)) != len(self.actionable_uids)
            or set(self.actionable_uids) != item_uids
        ):
            raise ResolveError("Resolve must include every Memory in the Context.")


@dataclass(frozen=True, slots=True)
class AuditResolutionIssue:
    """One Audit finding projected for suggestion generation and reinspection."""

    audit_snapshot_digest: str
    audit_key: str
    kind: ResolveIssueKind
    classification: str
    item_uids: tuple[str, ...]
    reason: str
    question: str
    detail: dict[str, object]
    item_kind: str = "MEMORY"

    @property
    def uid(self) -> str:
        encoded = json.dumps(
            {"audit": self.audit_snapshot_digest, "item": self.audit_key},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return "audit-item-" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ResolveIssue:
    """One immutable Audit item plus its separately derived Resolve direction."""

    uid: str
    audit_key: str
    audit_snapshot_digest: str
    kind: ResolveIssueKind
    classification: str
    item_uids: tuple[str, ...]
    proposed_direction: str
    reason: str
    question: str = ""
    item_kind: str = "MEMORY"
    choices: tuple[ResolutionOption, ...] = ()
    default_choice: str | None = None

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
        }:
            raise ResolveError("Resolve Issue kind is invalid.")
        if (
            not isinstance(self.item_uids, tuple)
            or len(set(self.item_uids)) != len(self.item_uids)
            or any(not isinstance(value, str) or not value for value in self.item_uids)
            or not self.item_uids
        ):
            raise ResolveError("Resolve Issue members are invalid.")
        if self.item_kind not in {"MEMORY"}:
            raise ResolveError("Resolve Issue item kind is invalid.")
        if not isinstance(self.choices, tuple) or any(
            not isinstance(choice, ResolutionOption) for choice in self.choices
        ):
            raise ResolveError("Resolve fixed choices must be typed options.")
        if self.choices and (
            len({choice.uid for choice in self.choices}) != len(self.choices)
            or any(
                choice.uid
                not in {
                    "CONFIRM",
                    "INTENT",
                    "FORCE",
                    "KEEP_TARGET",
                    "TAKE_SOURCE",
                    "KEEP_BOTH",
                    "KEEP_AS_IS",
                }
                for choice in self.choices
            )
        ):
            raise ResolveError("Resolve fixed choice contract is invalid.")
        if self.default_choice is not None and self.default_choice not in {
            choice.uid for choice in self.choices
        }:
            raise ResolveError("Resolve default choice must be available.")
        if not isinstance(self.question, str):
            raise TypeError("Resolve Issue question must be text.")


@dataclass(frozen=True)
class ResolveAnalysis:
    """One exact Audit and its answerable directions over a frozen revision."""

    frame: ResolveTarget
    status: ResolveStatus
    audit: QualityAuditSession | None = None
    question: str = ""
    issues: tuple[ResolveIssue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.frame, ResolveTarget):
            raise TypeError("Resolve analysis requires a frozen frame.")
        if self.status not in {
            "NO_ISSUES",
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
        frame_uids = {item.uid for item in self.frame.source.items}
        if any(not set(issue.item_uids) <= frame_uids for issue in self.issues):
            raise ResolveError("Resolve review Issues name Memories outside the frame.")
        kinds = {item.uid: item.kind for item in self.frame.source.items}
        if any(
            any(kinds[uid] != issue.item_kind for uid in issue.item_uids)
            for issue in self.issues
        ):
            raise ResolveError("Resolve Issue role does not match its Source items.")
        if not isinstance(self.audit, QualityAuditSession):
            raise ResolveError("Resolve analysis requires one completed Audit.")
        if self.audit.source != self.frame.source:
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
    checkpoints: tuple[tuple[str, str], ...] = ()
