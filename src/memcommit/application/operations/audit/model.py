"""Operation-owned durable Memory quality Audit model and validation.

Audit freezes one direct Context frame and retains independently typed issue
checks with their exact provider provenance. The completed record is immutable:
Audit Review reads this evidence but never adds responses or dispositions.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from memcommit.core.context import Context, Memory
from memcommit.application.operations.check_conformance.model import ConformanceReport
from memcommit.application.operations.fit.judgment import (
    FIT_JUDGMENT_CONTRACT_VERSION,
    FIT_JUDGMENT_OPERATION,
    FitVerdict,
)
from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
    QUALITY_RULESET_VERSIONS,
)
from memcommit.providers.types import ProviderIdentity
from memcommit.application.operations.review.model import direct_context_digest


# Schema 1 is retained as a review-only compatibility shape. Schema 2 adds the
# whole-Context Fit judgment required by current multi-Memory Audit consumers.
QUALITY_AUDIT_SCHEMA_VERSION = 2
QUALITY_AUDIT_LEGACY_SCHEMA_VERSION = 1
QUALITY_AUDIT_KINDS = ("duplicates", "ambiguities", "conflicts")
QUALITY_AUDIT_RULESETS = {
    "duplicates": QUALITY_RULESET_VERSIONS["find_duplicates"],
    "ambiguities": QUALITY_RULESET_VERSIONS["find_ambiguities"],
    "conflicts": QUALITY_RULESET_VERSIONS["find_conflicts"],
}

QualityAuditKind = Literal["duplicates", "ambiguities", "conflicts"]
QualityAuditReport = DuplicateReport | AmbiguityReport | ConflictReport


class QualityAuditError(ValueError):
    """Invalid, incomplete, or stale durable Audit state."""


def _exact_dict(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise QualityAuditError(f"Invalid {label}.")
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
class QualityAuditMemory:
    """One exact direct Memory supplied to every finder in the Audit."""

    uid: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"uid": self.uid, "content": self.content}

    @classmethod
    def from_dict(cls, value: object) -> "QualityAuditMemory":
        data = _exact_dict(value, {"uid", "content"}, "Audit Memory")
        return cls(
            uid=_canonical_uuid(data["uid"], "Audit Memory uid"),
            content=_string(
                data["content"],
                "Audit Memory content",
                empty=True,
                limit=1_000_000,
            ),
        )


@dataclass(frozen=True)
class QualityAuditSource:
    """The immutable direct-Context interpretation frame used by all checks."""

    context_uid: str
    context_name: str
    context_digest: str
    memories: tuple[QualityAuditMemory, ...]

    @classmethod
    def from_context(cls, ctx: Context) -> "QualityAuditSource":
        memories = tuple(
            QualityAuditMemory(item.uid, item.content)
            for item in ctx.iter_items()
            if isinstance(item, Memory)
        )
        frozen = Context(uid=ctx.uid, name=ctx.name)
        for memory in memories:
            frozen.add(Memory(memory.uid, memory.content))
        return cls(
            context_uid=ctx.uid,
            context_name=ctx.name,
            context_digest=direct_context_digest(frozen),
            memories=memories,
        )

    def context(self) -> Context:
        ctx = Context(uid=self.context_uid, name=self.context_name)
        for memory in self.memories:
            ctx.add(Memory(memory.uid, memory.content))
        return ctx

    def to_dict(self) -> dict[str, object]:
        return {
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
            "memories": [memory.to_dict() for memory in self.memories],
        }

    @classmethod
    def from_dict(cls, value: object) -> "QualityAuditSource":
        data = _exact_dict(
            value,
            {"context_uid", "context_name", "context_digest", "memories"},
            "Audit Source",
        )
        raw_memories = data["memories"]
        if not isinstance(raw_memories, list):
            raise QualityAuditError("Invalid Audit Source Memories.")
        memories = tuple(QualityAuditMemory.from_dict(item) for item in raw_memories)
        if len({memory.uid for memory in memories}) != len(memories):
            raise QualityAuditError("Duplicate Audit Source Memory uid.")
        source = cls(
            context_uid=_canonical_uuid(data["context_uid"], "Audit Context uid"),
            context_name=_string(data["context_name"], "Audit Context name", limit=500),
            context_digest=_string(
                data["context_digest"], "Audit Context digest", limit=64
            ),
            memories=memories,
        )
        if (
            len(source.context_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in source.context_digest
            )
            or direct_context_digest(source.context()) != source.context_digest
        ):
            raise QualityAuditError("Invalid Audit Context digest.")
        return source


@dataclass(frozen=True)
class QualityAuditProvenance:
    """Provider identity retained for one independent finder invocation."""

    operation: str
    provider_called: bool
    identity: ProviderIdentity | None = None
    upstream_model: str | None = None
    upstream_provider: str | None = None

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
        provider_called = data["provider_called"]
        if not isinstance(provider_called, bool):
            raise QualityAuditError("Invalid Audit provider-call marker.")
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

            def optional(field: str, *, limit: int = 500) -> str | None:
                raw = identity_data[field]
                return (
                    None
                    if raw is None
                    else _string(raw, f"Audit provider {field}", limit=limit)
                )

            identity = ProviderIdentity(
                provider=_string(
                    identity_data["provider"], "Audit provider", limit=100
                ),
                model=_string(identity_data["model"], "Audit model", limit=256),
                model_digest=optional("model_digest", limit=256),
                runtime=optional("runtime"),
                endpoint=optional("endpoint", limit=2_000),
                reasoning_effort=optional("reasoning_effort", limit=100),
            )
        if provider_called != (identity is not None):
            raise QualityAuditError("Invalid Audit provider provenance.")

        def optional_top(field: str) -> str | None:
            raw = data[field]
            return None if raw is None else _string(raw, f"Audit {field}", limit=500)

        return cls(
            operation=_string(data["operation"], "Audit operation", limit=100),
            provider_called=provider_called,
            identity=identity,
            upstream_model=optional_top("upstream_model"),
            upstream_provider=optional_top("upstream_provider"),
        )

    def display_name(self) -> str:
        if self.identity is None:
            return "LOCAL ONLY"
        return self.identity.display_name()


@dataclass(frozen=True)
class QualityAuditFit:
    """One whole-Context Fit judgment retained beside finder reports.

    Fit is set-level evidence rather than a pair or single-Memory finding.  The
    exact considered frame is retained so a MAY/NO result can become one
    Resolve item without fabricating independent per-Memory judgments.
    """

    uid: str
    created_at: str
    verdict: FitVerdict
    reason: str
    overview: str
    considered_memory_uids: tuple[str, ...]
    material_memory_uids: tuple[str, ...]
    consistent_reading: str
    inconsistent_reading: str
    provenance: QualityAuditProvenance
    contract_version: str = FIT_JUDGMENT_CONTRACT_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "created_at": self.created_at,
            "verdict": self.verdict,
            "reason": self.reason,
            "overview": self.overview,
            "considered_memory_uids": list(self.considered_memory_uids),
            "material_memory_uids": list(self.material_memory_uids),
            "consistent_reading": self.consistent_reading,
            "inconsistent_reading": self.inconsistent_reading,
            "provenance": self.provenance.to_dict(),
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
        *,
        source_memory_uids: tuple[str, ...],
    ) -> "QualityAuditFit":
        data = _exact_dict(
            value,
            {
                "uid",
                "created_at",
                "verdict",
                "reason",
                "overview",
                "considered_memory_uids",
                "material_memory_uids",
                "consistent_reading",
                "inconsistent_reading",
                "provenance",
                "contract_version",
            },
            "Audit Fit",
        )
        considered = data["considered_memory_uids"]
        material = data["material_memory_uids"]
        if not isinstance(considered, list) or not isinstance(material, list):
            raise QualityAuditError("Audit Fit Memory coverage must be arrays.")
        if any(not isinstance(uid, str) for uid in (*considered, *material)):
            raise QualityAuditError("Audit Fit Memory identities must be text.")
        considered_uids = tuple(considered)
        material_uids = tuple(material)
        if considered_uids != source_memory_uids:
            raise QualityAuditError(
                "Audit Fit must consider every frozen Source Memory exactly once."
            )
        if len(material_uids) != len(set(material_uids)) or any(
            uid not in considered_uids for uid in material_uids
        ):
            raise QualityAuditError("Audit Fit material Memories are invalid.")
        # Canonical Source order keeps the set-level issue key stable even if a
        # provider returns its material subset in a different order.
        if material_uids != tuple(uid for uid in considered_uids if uid in material_uids):
            raise QualityAuditError(
                "Audit Fit material Memories must retain frozen Source order."
            )
        verdict = data["verdict"]
        if verdict not in {"YES", "MAY", "NO"}:
            raise QualityAuditError("Audit Fit verdict is invalid.")
        consistent = _string(
            data["consistent_reading"],
            "Audit Fit consistent reading",
            empty=True,
        )
        inconsistent = _string(
            data["inconsistent_reading"],
            "Audit Fit inconsistent reading",
            empty=True,
        )
        if verdict == "YES":
            if material_uids or consistent or inconsistent:
                raise QualityAuditError(
                    "A YES Audit Fit cannot retain material Memories or split readings."
                )
        elif not material_uids:
            raise QualityAuditError(
                "A MAY or NO Audit Fit must identify material Memories."
            )
        if verdict == "MAY":
            if not consistent.strip() or not inconsistent.strip():
                raise QualityAuditError(
                    "A MAY Audit Fit must retain both ordinary readings."
                )
        elif consistent or inconsistent:
            raise QualityAuditError(
                "Only a MAY Audit Fit may retain split ordinary readings."
            )
        provenance = QualityAuditProvenance.from_dict(data["provenance"])
        if (
            provenance.operation != FIT_JUDGMENT_OPERATION
            or not provenance.provider_called
        ):
            raise QualityAuditError(
                "Audit Fit provenance must name its provider judgment."
            )
        if data["contract_version"] != FIT_JUDGMENT_CONTRACT_VERSION:
            raise QualityAuditError("Unsupported Audit Fit contract.")
        result = cls(
            uid=_canonical_uuid(data["uid"], "Audit Fit uid"),
            created_at=_string(data["created_at"], "Audit Fit creation time", limit=100),
            verdict=verdict,
            reason=_string(data["reason"], "Audit Fit reason"),
            overview=_string(data["overview"], "Audit Fit overview"),
            considered_memory_uids=considered_uids,
            material_memory_uids=material_uids,
            consistent_reading=consistent,
            inconsistent_reading=inconsistent,
            provenance=provenance,
        )
        try:
            datetime.fromisoformat(result.created_at)
        except ValueError as error:
            raise QualityAuditError("Invalid Audit Fit creation time.") from error
        return result


def _report_to_dict(
    kind: QualityAuditKind, report: QualityAuditReport
) -> dict[str, object]:
    if kind == "duplicates" and isinstance(report, DuplicateReport):
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
                "question": item.question,
            }
            for item in report.findings
        ]
        return {
            "memory_count": report.memory_count,
            "pair_count": report.pair_count,
            "findings": findings,
        }
    raise QualityAuditError("Audit check kind does not match its report type.")


def _report_from_dict(
    kind: QualityAuditKind,
    value: object,
    source_by_uid: dict[str, Memory],
) -> QualityAuditReport:
    keys = {"memory_count", "findings"}
    if kind == "conflicts":
        keys.add("pair_count")
    data = _exact_dict(value, keys, f"{kind} Audit report")
    memory_count = _integer(data["memory_count"], "Audit report Memory count")
    raw_findings = data["findings"]
    if not isinstance(raw_findings, list):
        raise QualityAuditError("Invalid Audit report findings.")

    def memory(uid: object) -> Memory:
        parsed = _canonical_uuid(uid, "Audit finding Memory uid")
        try:
            return source_by_uid[parsed]
        except KeyError as error:
            raise QualityAuditError(
                "Audit finding references a Memory outside its frozen Source."
            ) from error

    if kind == "duplicates":
        findings: list[DuplicateFinding] = []
        for raw in raw_findings:
            item = _exact_dict(
                raw,
                {"left_uid", "right_uid", "relation", "reason"},
                "Duplicate Audit finding",
            )
            relation = item["relation"]
            if relation not in {"EXACT", "SURFACE_EQUIVALENT", "SEMANTIC_EQUIVALENT"}:
                raise QualityAuditError("Invalid Duplicate Audit relation.")
            findings.append(
                DuplicateFinding(
                    left=memory(item["left_uid"]),
                    right=memory(item["right_uid"]),
                    relation=relation,
                    reason=_string(
                        item["reason"], "Duplicate Audit reason", limit=1_000
                    ),
                )
            )
        return DuplicateReport(memory_count=memory_count, findings=tuple(findings))
    if kind == "ambiguities":
        ambiguity_findings: list[AmbiguityFinding] = []
        for raw in raw_findings:
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
            interpretation = item["interpretation"]
            clarification = item["clarification"]
            readings = item["ordinary_readings"]
            if (
                interpretation not in {"SINGLE", "DOMINANT", "COMPETING"}
                or clarification not in {"NONE", "HELPFUL", "REQUIRED"}
                or not isinstance(readings, list)
            ):
                raise QualityAuditError("Invalid Ambiguity Audit finding.")
            ambiguity_findings.append(
                AmbiguityFinding(
                    memory=memory(item["memory_uid"]),
                    interpretation=interpretation,
                    clarification=clarification,
                    ordinary_readings=tuple(
                        _string(reading, "Audit ordinary reading", limit=500)
                        for reading in readings
                    ),
                    reason=_string(
                        item["reason"], "Ambiguity Audit reason", limit=1_000
                    ),
                    question=_string(
                        item["question"],
                        "Ambiguity Audit question",
                        empty=True,
                        limit=500,
                    ),
                )
            )
        return AmbiguityReport(
            memory_count=memory_count, findings=tuple(ambiguity_findings)
        )

    conflict_findings: list[ConflictFinding] = []
    for raw in raw_findings:
        item = _exact_dict(
            raw,
            {
                "left_uid",
                "right_uid",
                "conflict",
                "reason",
                "question",
            },
            "Conflict Audit finding",
        )
        conflict = item["conflict"]
        if conflict not in {"YES", "MAY"}:
            raise QualityAuditError("Invalid Conflict Audit finding.")
        conflict_findings.append(
            ConflictFinding(
                left=memory(item["left_uid"]),
                right=memory(item["right_uid"]),
                conflict=conflict,
                reason=_string(item["reason"], "Conflict Audit reason", limit=1_000),
                question=_string(
                    item["question"],
                    "Conflict Audit question",
                    empty=True,
                    limit=500,
                ),
            )
        )
    return ConflictReport(
        memory_count=memory_count,
        pair_count=_integer(data["pair_count"], "Audit pair count"),
        findings=tuple(conflict_findings),
    )


@dataclass(frozen=True)
class QualityAuditCheck:
    """One independently judged and provenance-bearing Audit section."""

    kind: QualityAuditKind
    ruleset_version: str
    report: QualityAuditReport
    provenance: QualityAuditProvenance

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
    source: QualityAuditSource
    checks: tuple[QualityAuditCheck, ...]
    fit: QualityAuditFit | None = None
    conformance: ConformanceReport | None = None

    @property
    def finding_count(self) -> int:
        return sum(len(check.report.findings) for check in self.checks)

    def snapshot_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "created_at": self.created_at,
            "source": self.source.to_dict(),
            "checks": [check.to_dict() for check in self.checks],
            "fit": None if self.fit is None else self.fit.to_dict(),
            "conformance": (
                self.conformance.to_dict() if self.conformance is not None else None
            ),
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
        if schema_version not in {
            QUALITY_AUDIT_LEGACY_SCHEMA_VERSION,
            QUALITY_AUDIT_SCHEMA_VERSION,
        }:
            raise QualityAuditError("Unsupported Audit session schema version.")
        keys = {
            "schema_version",
            "uid",
            "created_at",
            "source",
            "checks",
            "conformance",
        }
        if schema_version == QUALITY_AUDIT_SCHEMA_VERSION:
            keys.add("fit")
        data = _exact_dict(
            value,
            keys,
            "Audit session",
        )
        raw_fit = data.get("fit")
        raw_conformance = data["conformance"]
        source = QualityAuditSource.from_dict(data["source"])
        source_by_uid = {
            memory.uid: memory
            for memory in source.context().iter_items()
            if isinstance(memory, Memory)
        }
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
        if tuple(check.kind for check in checks) != QUALITY_AUDIT_KINDS:
            raise QualityAuditError(
                "A complete Audit must contain Duplicate, Ambiguity, and Conflict checks."
            )
        expected_memory_count = len(source.memories)
        for check in checks:
            if check.report.memory_count != expected_memory_count:
                raise QualityAuditError("Audit check does not match its frozen Source.")
            expected_ruleset = QUALITY_AUDIT_RULESETS[check.kind]
            if check.ruleset_version != expected_ruleset:
                raise QualityAuditError("Unsupported Audit finder ruleset.")
            if check.provenance.operation != f"find_{check.kind}":
                raise QualityAuditError(
                    "Audit check provenance does not match its finder."
                )
        conformance = (
            None
            if raw_conformance is None
            else ConformanceReport.from_dict(raw_conformance)
        )
        if conformance is not None:
            if (
                conformance.source_label != source.context_name
                or conformance.provider_identity is None
            ):
                raise QualityAuditError(
                    "Audit Conformance does not match its frozen Source or provider."
                )
            conformance_subjects = {
                item.uid: item.content for item in conformance.subjects
            }
            source_subjects = {item.uid: item.content for item in source.memories}
            if conformance_subjects != source_subjects:
                raise QualityAuditError(
                    "Audit Conformance does not cover the exact frozen Source."
                )
        fit = (
            None
            if raw_fit is None
            else QualityAuditFit.from_dict(
                raw_fit,
                source_memory_uids=tuple(item.uid for item in source.memories),
            )
        )
        if fit is not None and expected_memory_count < 2:
            raise QualityAuditError("Audit Fit requires at least two Source Memories.")
        conflict_report = checks[2].report
        assert isinstance(conflict_report, ConflictReport)
        if (
            conflict_report.pair_count
            != expected_memory_count * (expected_memory_count - 1) // 2
        ):
            raise QualityAuditError(
                "Conflict Audit does not cover its frozen pair frame."
            )

        session = cls(
            uid=_canonical_uuid(data["uid"], "Audit session uid"),
            created_at=_string(data["created_at"], "Audit creation time", limit=100),
            source=source,
            checks=checks,
            fit=fit,
            conformance=conformance,
        )
        try:
            datetime.fromisoformat(session.created_at)
        except ValueError as error:
            raise QualityAuditError("Invalid Audit creation time.") from error
        return session


def quality_audit_record_digest(session: QualityAuditSession) -> str:
    """Fingerprint the complete immutable Audit record."""

    return _digest(session.to_dict())
