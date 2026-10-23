"""Operation-owned durable Memory quality Audit model and validation.

Audit freezes one direct Context frame and retains independently typed issue
checks with their exact provider provenance. The completed record is immutable:
Audit Review reads this evidence but never adds responses or dispositions.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Literal

from memcommit.application.capabilities.memory_issue_analysis.model import (
    QUALITY_RULESET_VERSIONS,
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    ExactDuplicateGroup,
    find_exact_duplicate_groups,
)
from memcommit.application.operations.duplicates.find_duplicates.application import (
    ExactDuplicateReport,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.persistence.store.context_memory.records import context_record_digest
from memcommit.providers.types import ProviderIdentity

# Audit records retain individual findings; whole-set Fit is a separate operation.
QUALITY_AUDIT_SCHEMA_VERSION = 11
QUALITY_AUDIT_KINDS = ("dup", "dun", "ambiguities", "conflicts")
QUALITY_AUDIT_RULESETS = {
    "dup": "exact-direct-items-v1",
    "dun": QUALITY_RULESET_VERSIONS["find_duplicates"],
    "ambiguities": QUALITY_RULESET_VERSIONS["find_ambiguities"],
    "conflicts": QUALITY_RULESET_VERSIONS["find_conflicts"],
}
QUALITY_AUDIT_OPERATIONS = {
    "dup": "find_exact_duplicates",
    "dun": "find_duplicates",
    "ambiguities": "find_ambiguities",
    "conflicts": "find_conflicts",
}

QualityAuditKind = Literal["dup", "dun", "ambiguities", "conflicts"]
QualityAuditReport = (
    ExactDuplicateReport | DuplicateReport | AmbiguityReport | ConflictReport
)


class QualityAuditError(ValueError):
    """Invalid, incomplete, or stale durable Audit state."""


class AuditCheckKind(str, Enum):
    """Selectable Audit operations, in their canonical execution order."""

    DUP = "dup"
    DUN = "dun"
    AMBIGUITIES = "ambiguities"
    CONFLICTS = "conflicts"


def _exact_dict(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise QualityAuditError(f"Invalid {label}.")
    return value


def _array(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise QualityAuditError(f"Invalid {label} array.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = 20_000,
) -> str:
    if not isinstance(value, str) or (not empty and not value) or len(value) > limit:
        raise QualityAuditError(f"Invalid {label}.")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise QualityAuditError(f"Invalid {label}.")
    return value


def _canonical_uuid(value: object, label: str) -> str:
    parsed = _string(value, label, limit=100)
    try:
        canonical = str(uuid.UUID(parsed))
    except ValueError as error:
        raise QualityAuditError(f"Invalid {label}.") from error
    if canonical != parsed:
        raise QualityAuditError(f"Invalid {label}.")
    return canonical


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class QualityAuditMemory(Memory):
    """One exact direct Memory supplied to every finder in the Audit."""

    uid: str
    content: str


@dataclass(frozen=True)
class QualityAuditItem:
    """One directly owned Memory occurrence in the Audit frame."""

    uid: str
    kind: str
    summary: str


def _copy_source_context(context: Context) -> Context:
    """Copy the selected local Memory frame without retaining Store bindings."""
    copied = Context(uid=context.uid, name=context.name)
    for item in context.iter_memories():
        if isinstance(item, Memory):
            copied.add(Memory(item.uid, item.content))
    # An analysis snapshot is not a Store load or an optimistic-write handle.
    copied.corresponding_document_metadata = deepcopy(
        context.corresponding_document_metadata
    )
    copied.asset_metadata = deepcopy(context.asset_metadata)
    return copied


@dataclass(frozen=True)
class AuditTarget:
    """Detached direct Context; callers receive copies, never its owned snapshot."""

    context_uid: str
    context_name: str
    context_digest: str
    _context: Context = field(repr=False, compare=False)

    def __post_init__(self):
        context = self._context
        _canonical_uuid(context.uid, "Audit Context uid")
        _string(context.name, "Audit Context name", limit=500)
        for item in context.iter_memories():
            _canonical_uuid(item.uid, "Audit item uid")
            if isinstance(item, Memory):
                _string(
                    item.content, "Audit Memory content", empty=True, limit=1_000_000
                )
            else:
                raise QualityAuditError("Invalid Audit direct-item type.")
        if (context.uid, context.name, context_record_digest(context)) != (
            self.context_uid,
            self.context_name,
            self.context_digest,
        ):
            raise QualityAuditError("Invalid Audit Context identity or digest.")
        object.__setattr__(self, "_context", _copy_source_context(context))

    @classmethod
    def from_context(cls, ctx: Context) -> "AuditTarget":
        return cls(ctx.uid, ctx.name, context_record_digest(ctx), ctx)

    def context(self) -> Context:
        return _copy_source_context(self._context)

    @property
    def memories(self) -> tuple[QualityAuditMemory, ...]:
        return tuple(
            QualityAuditMemory(item.uid, item.content)
            for item in self._context.iter_memories()
            if isinstance(item, Memory)
        )

    @property
    def items(self) -> tuple[QualityAuditItem, ...]:
        result = []
        for item in self._context.iter_memories():
            kind, summary = "MEMORY", item.content
            result.append(QualityAuditItem(item.uid, kind, summary))
        return tuple(result)

    def to_dict(self) -> dict[str, object]:
        return {
            "context": self._context.to_dict(),
            "context_digest": self.context_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> "AuditTarget":
        data = _exact_dict(value, {"context", "context_digest"}, "Audit Source")
        try:
            record = data["context"]
            context = Context.from_dict(record)
            # The general Context codec accepts old omissions; retained Audit
            # evidence must not silently discard or normalize malformed input.
            if context.to_dict() != record:
                raise QualityAuditError("Audit Context record is not canonical.")
            return cls(context.uid, context.name, data["context_digest"], context)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise QualityAuditError(f"Invalid Audit Source: {error}") from error


@dataclass(frozen=True)
class QualityAuditProvenance:
    """Provider identity retained for one independent finder invocation."""

    operation: str
    provider_called: bool
    identity: ProviderIdentity | None = None
    upstream_model: str | None = None
    upstream_provider: str | None = None

    def __post_init__(self):
        _string(self.operation, "Audit operation", limit=100)
        if not isinstance(self.provider_called, bool) or self.provider_called != (
            self.identity is not None
        ):
            raise QualityAuditError("Invalid Audit provider provenance.")
        if self.identity is not None:
            if not isinstance(self.identity, ProviderIdentity):
                raise QualityAuditError("Invalid Audit provider identity.")
            _string(self.identity.provider, "Audit provider", limit=100)
            _string(self.identity.model, "Audit model", limit=256)
            for name, limit in (
                ("model_digest", 256),
                ("runtime", 500),
                ("endpoint", 2000),
                ("reasoning_effort", 100),
            ):
                value = getattr(self.identity, name)
                if value is not None:
                    _string(value, f"Audit provider {name}", limit=limit)
        for name in ("upstream_model", "upstream_provider"):
            value = getattr(self, name)
            if value is not None:
                _string(value, f"Audit {name}", limit=500)

    def to_dict(self) -> dict[str, object]:
        identity = self.identity
        return {
            "operation": self.operation,
            "provider_called": self.provider_called,
            "identity": (
                None
                if identity is None
                else {
                    "provider": identity.provider,
                    "model": identity.model,
                    "model_digest": identity.model_digest,
                    "runtime": identity.runtime,
                    "endpoint": identity.endpoint,
                    "reasoning_effort": identity.reasoning_effort,
                }
            ),
            "upstream_model": self.upstream_model,
            "upstream_provider": self.upstream_provider,
        }

    @classmethod
    def from_dict(cls, value: object) -> "QualityAuditProvenance":
        data = _exact_dict(
            value,
            {
                "operation",
                "provider_called",
                "identity",
                "upstream_model",
                "upstream_provider",
            },
            "Audit provenance",
        )
        raw_identity = data["identity"]
        identity = None
        if raw_identity is not None:
            identity_data = _exact_dict(
                raw_identity,
                {
                    "provider",
                    "model",
                    "model_digest",
                    "runtime",
                    "endpoint",
                    "reasoning_effort",
                },
                "Audit provider identity",
            )
            identity = ProviderIdentity(**identity_data)
        return cls(**(data | {"identity": identity}))

    def display_name(self) -> str:
        if self.identity is None:
            return "LOCAL ONLY"
        return self.identity.display_name()


def _report_to_dict(
    kind: QualityAuditKind, report: QualityAuditReport
) -> dict[str, object]:
    if kind == "dup" and isinstance(report, ExactDuplicateReport):
        return {
            "memory_count": report.memory_count,
            "item_count": report.item_count,
            "groups": [
                asdict(group) | {"absorbed_uids": list(group.absorbed_uids)}
                for group in report.groups
            ],
        }
    if kind == "dun" and isinstance(report, DuplicateReport):
        findings = [
            {
                "left_uid": item.left.uid,
                "right_uid": item.right.uid,
                "relation": item.relation,
                "reason": item.reason,
            }
            for item in report.findings
        ]
        return {"memory_count": report.memory_count, "findings": findings}
    if kind == "ambiguities" and isinstance(report, AmbiguityReport):
        findings = [
            {
                "memory_uid": item.memory.uid,
                "interpretation": item.interpretation,
                "clarification": item.clarification,
                "ordinary_readings": list(item.ordinary_readings),
                "reason": item.reason,
                "question": item.question,
            }
            for item in report.findings
        ]
        return {"memory_count": report.memory_count, "findings": findings}
    if kind == "conflicts" and isinstance(report, ConflictReport):
        findings = [
            {
                "left_uid": item.left.uid,
                "right_uid": item.right.uid,
                "conflict": item.conflict,
                "reason": item.reason,
            }
            for item in report.findings
        ]
        return {
            "memory_count": report.memory_count,
            "pair_count": report.pair_count,
            "findings": findings,
        }
    raise QualityAuditError("Audit check kind does not match its report type.")


def _bind_report(
    kind: QualityAuditKind, report: QualityAuditReport, source: AuditTarget
) -> QualityAuditReport:
    """Validate typed findings and bind immutable leaves to the frozen Source."""
    types = {
        "dup": ExactDuplicateReport,
        "dun": DuplicateReport,
        "ambiguities": AmbiguityReport,
        "conflicts": ConflictReport,
    }
    if not isinstance(report, types[kind]):
        raise QualityAuditError("Audit check kind does not match its report type.")
    _integer(report.memory_count, "Audit report Memory count")
    if kind in {"dup", "dun"}:
        groups = find_exact_duplicate_groups(source.context())
        if kind == "dup":
            _integer(report.item_count, "DUP item count")
            if report != ExactDuplicateReport(
                len(source.memories), groups, len(source.items)
            ):
                raise QualityAuditError(
                    "DUP report does not match the exact frozen Source."
                )
            return report
    memories = {memory.uid: memory for memory in source.memories}

    def memory(item):
        if not isinstance(item, Memory) or item.uid not in memories:
            raise QualityAuditError(
                "Audit finding references a Memory outside its frozen Source."
            )
        frozen = memories[item.uid]
        if item.content != frozen.content:
            raise QualityAuditError(
                "Audit finding content differs from its frozen Source."
            )
        return frozen

    if not isinstance(report.findings, tuple):
        raise QualityAuditError("Audit findings must be immutable ordered values.")
    findings = []
    for finding in report.findings:
        _string(finding.reason, "Audit finding reason", limit=1000)
        if kind == "dun":
            if not isinstance(finding, DuplicateFinding):
                raise QualityAuditError("Invalid Duplicate Audit finding.")
            findings.append(
                replace(finding, left=memory(finding.left), right=memory(finding.right))
            )
        elif kind == "ambiguities":
            if (
                not isinstance(finding, AmbiguityFinding)
                or finding.interpretation not in {"SINGLE", "DOMINANT", "COMPETING"}
                or finding.clarification not in {"NONE", "HELPFUL", "REQUIRED"}
                or (not isinstance(finding.ordinary_readings, tuple))
            ):
                raise QualityAuditError("Invalid Ambiguity Audit finding.")
            for reading in finding.ordinary_readings:
                _string(reading, "Audit ordinary reading", limit=500)
            _string(finding.question, "Ambiguity Audit question", empty=True, limit=500)
            findings.append(replace(finding, memory=memory(finding.memory)))
        else:
            if not isinstance(finding, ConflictFinding) or finding.conflict not in {
                "YES",
                "MAY",
            }:
                raise QualityAuditError("Invalid Conflict Audit finding.")
            findings.append(
                replace(finding, left=memory(finding.left), right=memory(finding.right))
            )
    if kind == "conflicts":
        _integer(report.pair_count, "Audit pair count")
    return replace(report, findings=tuple(findings))


def _report_from_dict(
    kind: QualityAuditKind,
    value: object,
    source_by_uid: dict[str, Memory],
) -> QualityAuditReport:
    """Decode wire shapes; Session construction validates the bound object graph."""
    keys = (
        {"memory_count", "groups", "item_count"}
        if kind == "dup"
        else {"memory_count", "findings"}
    )
    if kind == "conflicts":
        keys.add("pair_count")
    data = _exact_dict(value, keys, f"{kind} Audit report")

    def groups(raw):
        result = []
        for entry in _array(raw, "DUP groups"):
            item = _exact_dict(
                entry,
                {"item_kind", "survivor_uid", "absorbed_uids", "summary", "content"},
                "DUP group",
            )
            result.append(
                ExactDuplicateGroup(
                    item_kind=item["item_kind"],
                    survivor_uid=item["survivor_uid"],
                    absorbed_uids=tuple(
                        _array(item["absorbed_uids"], "DUP absorbed identities")
                    ),
                    summary=item["summary"],
                    content=item["content"],
                )
            )
        return tuple(result)

    def memory(uid):
        parsed = _canonical_uuid(uid, "Audit finding Memory uid")
        try:
            return source_by_uid[parsed]
        except KeyError as error:
            raise QualityAuditError(
                "Audit finding references a Memory outside its frozen Source."
            ) from error

    if kind == "dup":
        return ExactDuplicateReport(
            data["memory_count"], groups(data["groups"]), data["item_count"]
        )
    findings = []
    for raw in _array(data["findings"], "Audit findings"):
        if kind == "ambiguities":
            item = _exact_dict(
                raw,
                {
                    "memory_uid",
                    "interpretation",
                    "clarification",
                    "ordinary_readings",
                    "reason",
                    "question",
                },
                "Ambiguity Audit finding",
            )
            findings.append(
                AmbiguityFinding(
                    memory(item["memory_uid"]),
                    item["interpretation"],
                    item["clarification"],
                    tuple(_array(item["ordinary_readings"], "Audit ordinary readings")),
                    item["reason"],
                    item["question"],
                )
            )
        else:
            keys = {"left_uid", "right_uid", "reason"} | (
                {"relation"} if kind == "dun" else {"conflict"}
            )
            item = _exact_dict(raw, keys, f"{kind} Audit finding")
            if kind == "dun":
                if item["relation"] not in {
                    "EXACT",
                    "SURFACE_EQUIVALENT",
                    "SEMANTIC_EQUIVALENT",
                }:
                    raise QualityAuditError("Invalid Duplicate Audit relation.")
                findings.append(
                    DuplicateFinding(
                        memory(item["left_uid"]),
                        memory(item["right_uid"]),
                        item["relation"],
                        item["reason"],
                    )
                )
            else:
                findings.append(
                    ConflictFinding(
                        memory(item["left_uid"]),
                        memory(item["right_uid"]),
                        item["conflict"],
                        item["reason"],
                    )
                )
    if kind == "dun":
        return DuplicateReport(data["memory_count"], tuple(findings))
    if kind == "ambiguities":
        return AmbiguityReport(data["memory_count"], tuple(findings))
    return ConflictReport(data["memory_count"], data["pair_count"], tuple(findings))


@dataclass(frozen=True)
class QualityAuditCheck:
    """One independently judged and provenance-bearing Audit section."""

    kind: QualityAuditKind
    ruleset_version: str
    report: QualityAuditReport
    provenance: QualityAuditProvenance

    def __post_init__(self):
        if self.kind not in QUALITY_AUDIT_KINDS:
            raise QualityAuditError("Invalid Audit check kind.")
        _string(self.ruleset_version, "Audit ruleset", limit=100)
        if not isinstance(self.provenance, QualityAuditProvenance):
            raise QualityAuditError("Invalid Audit provenance.")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "ruleset_version": self.ruleset_version,
            "report": _report_to_dict(self.kind, self.report),
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
        source_by_uid: dict[str, Memory],
    ) -> "QualityAuditCheck":
        data = _exact_dict(
            value,
            {"kind", "ruleset_version", "report", "provenance"},
            "Audit check",
        )
        kind = data["kind"]
        if kind not in QUALITY_AUDIT_KINDS:
            raise QualityAuditError("Invalid Audit check kind.")
        return cls(
            kind=kind,
            ruleset_version=_string(
                data["ruleset_version"], "Audit ruleset", limit=100
            ),
            report=_report_from_dict(
                kind,
                data["report"],
                source_by_uid,
            ),
            provenance=QualityAuditProvenance.from_dict(data["provenance"]),
        )


@dataclass(frozen=True)
class QualityAuditSession:
    """One completed immutable Audit record."""

    uid: str
    created_at: str
    source: AuditTarget
    checks: tuple[QualityAuditCheck, ...]
    requested_checks: tuple[AuditCheckKind, ...]

    def __post_init__(self):
        _canonical_uuid(self.uid, "Audit session uid")
        _string(self.created_at, "Audit creation time", limit=100)
        try:
            datetime.fromisoformat(self.created_at)
        except ValueError as error:
            raise QualityAuditError("Invalid Audit creation time.") from error
        source = self.source
        if not isinstance(self.checks, tuple) or not isinstance(
            self.requested_checks, tuple
        ):
            raise QualityAuditError("Audit checks must be immutable ordered values.")
        requested_checks = self.requested_checks
        if not requested_checks or any(
            not isinstance(kind, AuditCheckKind) for kind in requested_checks
        ):
            raise QualityAuditError("Audit must request typed checks.")
        checks = tuple(
            replace(check, report=_bind_report(check.kind, check.report, source))
            for check in self.checks
        )
        object.__setattr__(self, "checks", checks)
        expected_memory_count = len(source.memories)
        for check in checks:
            if check.report.memory_count != expected_memory_count:
                raise QualityAuditError("Audit check does not match its frozen Source.")
            if check.kind == "dup" and check.provenance.provider_called:
                raise QualityAuditError(
                    "Deterministic Audit cannot have provider provenance."
                )
            expected_ruleset = QUALITY_AUDIT_RULESETS[check.kind]
            if check.ruleset_version != expected_ruleset:
                raise QualityAuditError("Unsupported Audit finder ruleset.")
            if check.provenance.operation != QUALITY_AUDIT_OPERATIONS[check.kind]:
                raise QualityAuditError(
                    "Audit check provenance does not match its finder."
                )
        for check in checks:
            if check.kind == "conflicts":
                conflict_report = check.report
                assert isinstance(conflict_report, ConflictReport)
                if (
                    conflict_report.pair_count
                    != expected_memory_count * (expected_memory_count - 1) // 2
                ):
                    raise QualityAuditError(
                        "Conflict Audit does not cover its frozen pair frame."
                    )

        completed_checks = tuple(AuditCheckKind(check.kind) for check in checks)
        canonical = tuple(kind for kind in AuditCheckKind if kind in requested_checks)
        if requested_checks != canonical:
            raise QualityAuditError(
                "Requested Audit checks must be unique and ordered."
            )
        if completed_checks != requested_checks:
            raise QualityAuditError(
                "A completed Audit must contain exactly its requested checks."
            )

    @property
    def completed_checks(self) -> tuple[AuditCheckKind, ...]:
        """Only checks with results; an absent check does not mean no findings."""

        return tuple(AuditCheckKind(check.kind) for check in self.checks)

    @property
    def finding_count(self) -> int:
        return sum(
            len(check.report.groups)
            if isinstance(check.report, ExactDuplicateReport)
            else len(check.report.findings)
            for check in self.checks
            if not (check.kind == "dup" and AuditCheckKind.DUN in self.requested_checks)
        )

    def snapshot_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "created_at": self.created_at,
            "source": self.source.to_dict(),
            "checks": [check.to_dict() for check in self.checks],
            "requested_checks": [kind.value for kind in self.requested_checks],
        }

    @property
    def snapshot_digest(self) -> str:
        return _digest(self.snapshot_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": QUALITY_AUDIT_SCHEMA_VERSION,
            **self.snapshot_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> "QualityAuditSession":
        if not isinstance(value, dict):
            raise QualityAuditError("Invalid Audit session.")
        schema_version = value.get("schema_version")
        if schema_version != QUALITY_AUDIT_SCHEMA_VERSION:
            raise QualityAuditError("Unsupported Audit session schema version.")
        keys = {
            "schema_version",
            "uid",
            "created_at",
            "source",
            "checks",
            "requested_checks",
        }
        data = _exact_dict(
            value,
            keys,
            "Audit session",
        )
        source = AuditTarget.from_dict(data["source"])
        source_by_uid = {memory.uid: memory for memory in source.memories}
        raw_checks = data["checks"]
        if not isinstance(raw_checks, list):
            raise QualityAuditError("Invalid Audit checks.")
        checks = tuple(
            QualityAuditCheck.from_dict(
                check,
                source_by_uid,
            )
            for check in raw_checks
        )

        raw_requested = data["requested_checks"]
        if not isinstance(raw_requested, list) or not raw_requested:
            raise QualityAuditError("Audit must request at least one check.")
        try:
            requested_checks = tuple(AuditCheckKind(kind) for kind in raw_requested)
        except (TypeError, ValueError) as error:
            raise QualityAuditError("Invalid requested Audit check kind.") from error

        return cls(
            uid=data["uid"],
            created_at=data["created_at"],
            source=source,
            checks=checks,
            requested_checks=requested_checks,
        )


def quality_audit_record_digest(session: QualityAuditSession) -> str:
    """Fingerprint the complete immutable Audit record."""

    return _digest(session.to_dict())
