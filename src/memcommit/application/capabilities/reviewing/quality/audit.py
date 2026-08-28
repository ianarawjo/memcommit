"""Durable Memory quality Audit snapshots and review projection.

Audit is an orchestration boundary, not a fourth semantic judge. It freezes one
direct Context frame, runs the existing Duplicate, Ambiguity, and Conflict
finders independently, and may retain one separately typed Conformance check
against an explicit Rules Context. Version-1/2 records remain readable, but
version 3 drops Conflict's unused scope-dimension tags. Historical response
fields remain annotations; the Audit Review route no longer edits them.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Literal

from memcommit.core.context import Context, Memory
from memcommit.application.operations.conformance.model import ConformanceReport
from memcommit.application.capabilities.reviewing.quality.findings import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
    FindingsProvider,
    QUALITY_RULESET_VERSIONS,
    find_ambiguities,
    find_conflicts,
    find_redundancies,
)
from memcommit.providers.types import CompletionRun, ProviderIdentity
from memcommit.application.capabilities.reviewing.quality.report import (
    quality_find_category_label,
    quality_find_report_summary_text,
)
from memcommit.application.capabilities.reviewing.quality.workbench import (
    QualityFindResponse,
    QualityFindSourceFrame,
    QualityFindWorkbenchSession,
    quality_find_report_view,
    quality_find_resolution_view,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionContextLocation,
    ResolutionMetric,
    ResolutionOverviewSection,
    ResolutionWorkbenchView,
    resolution_overview_text,
)
from memcommit.application.operations.review.model import REVIEW_RESPONSE_CHAR_LIMIT, direct_context_digest


QUALITY_AUDIT_SCHEMA_VERSION = 3
QUALITY_AUDIT_LEGACY_SCHEMA_VERSION = 1
QUALITY_AUDIT_PREVIOUS_SCHEMA_VERSION = 2
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
    *,
    schema_version: int,
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
        item_keys = {
            "left_uid",
            "right_uid",
            "conflict",
            "reason",
            "question",
        }
        if schema_version <= QUALITY_AUDIT_PREVIOUS_SCHEMA_VERSION:
            item_keys.add("scope_dimensions")
        item = _exact_dict(
            raw,
            item_keys,
            "Conflict Audit finding",
        )
        conflict = item["conflict"]
        if conflict not in {"YES", "MAY"}:
            raise QualityAuditError("Invalid Conflict Audit finding.")
        if schema_version <= QUALITY_AUDIT_PREVIOUS_SCHEMA_VERSION:
            # Old records retain these tags as historical bytes only. They did
            # not affect Resolve and do not re-enter the version-3 model.
            dimensions = item["scope_dimensions"]
            if not isinstance(dimensions, list):
                raise QualityAuditError("Invalid Conflict Audit finding.")
            tuple(
                _string(dimension, "legacy Audit scope dimension", limit=100)
                for dimension in dimensions
            )
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
        *,
        schema_version: int,
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
                schema_version=schema_version,
            ),
            provenance=QualityAuditProvenance.from_dict(data["provenance"]),
        )


def _finding_item_uids(check: QualityAuditCheck) -> tuple[str, ...]:
    report = check.report
    if isinstance(report, AmbiguityReport):
        return tuple(f"ambiguity:{item.memory.uid}" for item in report.findings)
    prefix = "duplicate" if isinstance(report, DuplicateReport) else "conflict"
    return tuple(
        f"{prefix}:{item.left.uid}:{item.right.uid}" for item in report.findings
    )


@dataclass
class QualityAuditSession:
    """One immutable Audit plus legacy durable review annotations."""

    uid: str
    created_at: str
    source: QualityAuditSource
    checks: tuple[QualityAuditCheck, ...]
    conformance: ConformanceReport | None = None
    responses: dict[str, QualityFindResponse] = field(default_factory=dict)

    @property
    def finding_count(self) -> int:
        return sum(len(check.report.findings) for check in self.checks)

    @property
    def answered_count(self) -> int:
        return sum(response.answered for response in self.responses.values())

    def response_for(self, item_uid: str) -> QualityFindResponse:
        valid_uids = {uid for check in self.checks for uid in _finding_item_uids(check)}
        if item_uid not in valid_uids:
            raise QualityAuditError("Unknown Audit response target.")
        response = self.responses.get(item_uid)
        if response is None:
            response = QualityFindResponse()
            self.responses[item_uid] = response
        return response

    def snapshot_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "created_at": self.created_at,
            "source": self.source.to_dict(),
            "checks": [check.to_dict() for check in self.checks],
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
            "responses": {
                uid: {
                    "selected_option_uid": response.selected_option_uid,
                    "text": response.text,
                }
                for uid, response in self.responses.items()
            },
        }

    @classmethod
    def from_dict(cls, value: object) -> "QualityAuditSession":
        if not isinstance(value, dict):
            raise QualityAuditError("Invalid Audit session.")
        schema_version = value.get("schema_version")
        if schema_version == QUALITY_AUDIT_LEGACY_SCHEMA_VERSION:
            data = _exact_dict(
                value,
                {
                    "schema_version",
                    "uid",
                    "created_at",
                    "source",
                    "checks",
                    "responses",
                },
                "legacy Audit session",
            )
            raw_conformance = None
        elif schema_version in {
            QUALITY_AUDIT_PREVIOUS_SCHEMA_VERSION,
            QUALITY_AUDIT_SCHEMA_VERSION,
        }:
            data = _exact_dict(
                value,
                {
                    "schema_version",
                    "uid",
                    "created_at",
                    "source",
                    "checks",
                    "conformance",
                    "responses",
                },
                "Audit session",
            )
            raw_conformance = data["conformance"]
        else:
            raise QualityAuditError("Unsupported Audit session schema version.")
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
                schema_version=schema_version,
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
            if (
                schema_version <= QUALITY_AUDIT_PREVIOUS_SCHEMA_VERSION
                and check.kind == "conflicts"
            ):
                expected_ruleset = "conflict-v1-draft"
            valid_rulesets = {expected_ruleset}
            if (
                schema_version == QUALITY_AUDIT_SCHEMA_VERSION
                and check.kind == "conflicts"
            ):
                # Normalized historical records retain truthful v1 provenance
                # even though their discarded display-only tags are not
                # rewritten into the version-3 body.
                valid_rulesets.add("conflict-v1-draft")
            if check.ruleset_version not in valid_rulesets:
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
                conformance.mode != "CONTEXT"
                or conformance.source_label != source.context_name
                or conformance.provider_identity is None
            ):
                raise QualityAuditError(
                    "Audit Conformance does not match its frozen Source or provider."
                )
            conformance_subjects = {
                item.uid: item.content for item in conformance.subjects
            }
            source_subjects = {item.uid: item.content for item in source.memories}
            if conformance_subjects != source_subjects or any(
                item.expected is not None for item in conformance.subjects
            ):
                raise QualityAuditError(
                    "Audit Conformance does not cover the exact frozen Source."
                )
        conflict_report = checks[2].report
        assert isinstance(conflict_report, ConflictReport)
        if (
            conflict_report.pair_count
            != expected_memory_count * (expected_memory_count - 1) // 2
        ):
            raise QualityAuditError(
                "Conflict Audit does not cover its frozen pair frame."
            )

        raw_responses = data["responses"]
        if not isinstance(raw_responses, dict):
            raise QualityAuditError("Invalid Audit responses.")
        valid_uids = {uid for check in checks for uid in _finding_item_uids(check)}
        responses: dict[str, QualityFindResponse] = {}
        for item_uid, raw_response in raw_responses.items():
            if not isinstance(item_uid, str) or item_uid not in valid_uids:
                raise QualityAuditError("Invalid Audit response target.")
            response_data = _exact_dict(
                raw_response,
                {"selected_option_uid", "text"},
                "Audit response",
            )
            selected = response_data["selected_option_uid"]
            if selected is not None and (not isinstance(selected, str) or not selected):
                raise QualityAuditError("Invalid selected Audit option.")
            responses[item_uid] = QualityFindResponse(
                selected_option_uid=selected,
                text=_string(
                    response_data["text"],
                    "Audit response text",
                    empty=True,
                    limit=REVIEW_RESPONSE_CHAR_LIMIT,
                ),
            )
        session = cls(
            uid=_canonical_uuid(data["uid"], "Audit session uid"),
            created_at=_string(data["created_at"], "Audit creation time", limit=100),
            source=source,
            checks=checks,
            conformance=conformance,
            responses=responses,
        )
        try:
            datetime.fromisoformat(session.created_at)
        except ValueError as error:
            raise QualityAuditError("Invalid Audit creation time.") from error
        # Re-project once so a persisted selected option cannot name a choice
        # that its exact typed finding does not expose.
        view = quality_audit_resolution_view(session)
        for item_uid, response in responses.items():
            item = view.item(item_uid)
            if response.selected_option_uid is not None:
                item.option(response.selected_option_uid)
        return session


class _CapturingProviderFactory:
    """Capture the exact provider run without changing a finder's call contract."""

    def __init__(self, factory: Callable[[], FindingsProvider]):
        self._factory = factory
        self.provider: FindingsProvider | None = None

    def __call__(self) -> FindingsProvider:
        if self.provider is not None:
            raise QualityAuditError("An Audit finder requested more than one provider.")
        self.provider = self._factory()
        return self.provider

    def provenance(self, operation: str) -> QualityAuditProvenance:
        if self.provider is None:
            return QualityAuditProvenance(operation=operation, provider_called=False)
        last_run = getattr(self.provider, "last_run", None)
        identity = getattr(self.provider, "identity", None)
        if isinstance(last_run, CompletionRun):
            identity = last_run.identity
        if not isinstance(identity, ProviderIdentity):
            raise QualityAuditError(
                "A durable Audit requires provider and model provenance."
            )
        if last_run is not None and (
            not isinstance(last_run, CompletionRun) or last_run.operation != operation
        ):
            raise QualityAuditError(
                "Audit provider provenance does not match its finder."
            )
        return QualityAuditProvenance(
            operation=operation,
            provider_called=True,
            identity=identity,
            upstream_model=(
                last_run.upstream_model if isinstance(last_run, CompletionRun) else None
            ),
            upstream_provider=(
                last_run.upstream_provider
                if isinstance(last_run, CompletionRun)
                else None
            ),
        )


def create_quality_audit(
    ctx: Context,
    checks: tuple[QualityAuditCheck, ...],
    *,
    conformance: ConformanceReport | None = None,
    uid: str | None = None,
    created_at: str | None = None,
) -> QualityAuditSession:
    """Create and fully validate one completed Audit snapshot."""

    source = QualityAuditSource.from_context(ctx)
    session = QualityAuditSession(
        uid=uid or str(uuid.uuid4()),
        created_at=created_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source=source,
        checks=checks,
        conformance=conformance,
    )
    return QualityAuditSession.from_dict(session.to_dict())


def run_quality_audit(
    ctx: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    on_check: Callable[[QualityAuditKind, int, int], None] | None = None,
) -> QualityAuditSession:
    """Run all three independent finders over one frozen direct Context frame."""

    source = QualityAuditSource.from_context(ctx)
    frozen = source.context()
    operations: tuple[
        tuple[
            QualityAuditKind,
            Callable[[Context, Callable[[], FindingsProvider]], QualityAuditReport],
        ],
        ...,
    ] = (
        ("duplicates", find_redundancies),
        ("ambiguities", find_ambiguities),
        ("conflicts", find_conflicts),
    )
    checks: list[QualityAuditCheck] = []
    for index, (kind, finder) in enumerate(operations, start=1):
        if on_check is not None:
            on_check(kind, index, len(operations))
        capture = _CapturingProviderFactory(provider_factory)
        report = finder(frozen, capture)
        checks.append(
            QualityAuditCheck(
                kind=kind,
                ruleset_version=QUALITY_AUDIT_RULESETS[kind],
                report=report,
                provenance=capture.provenance(f"find_{kind}"),
            )
        )
    return create_quality_audit(frozen, tuple(checks))


def quality_audit_record_digest(session: QualityAuditSession) -> str:
    """Fingerprint the complete mutable Audit record for CAS persistence."""

    return _digest(session.to_dict())


def quality_audit_resolution_view(
    session: QualityAuditSession,
) -> ResolutionWorkbenchView:
    """Compose the legacy Resolution-shaped compatibility projection."""

    ctx = session.source.context()
    source_frame = QualityFindSourceFrame.create((ctx,))
    items = []
    counts: dict[str, int] = {}
    summaries: dict[str, str] = {}
    for check in session.checks:
        sub_session = QualityFindWorkbenchSession(
            uid=session.uid,
            kind=check.kind,
            source=source_frame,
            report=check.report,
            responses=session.responses,
        )
        projected = quality_find_resolution_view(sub_session, ctx)
        items.extend(projected.items)
        counts[check.kind] = len(projected.items)
        summaries[check.kind] = quality_find_report_summary_text(
            quality_find_report_view(sub_session, ctx)
        )

    check_lines = [
        f"{quality_find_category_label(kind)} · FINISHED · {summaries[kind]}"
        for kind in QUALITY_AUDIT_KINDS
    ]
    provenance_lines = [
        f"{quality_find_category_label(check.kind)} · {check.ruleset_version} · "
        f"{check.provenance.display_name()}"
        for check in session.checks
    ]
    conformance = session.conformance
    check_total = 3
    if conformance is not None:
        check_total = 4
        check_lines.append(
            "CONFORMANCE · FINISHED · "
            f"{len(conformance.context_judgments)} Rules · "
            f"{conformance.issue_count} issues"
        )
        identity = conformance.provider_identity
        assert identity is not None
        provenance_lines.append(
            f"CONFORMANCE · {conformance.ruleset_version} · {identity.display_name()}"
        )
    checks_text = "\n".join(check_lines)
    provenance_text = "\n".join(provenance_lines)
    sections_list = [
        ResolutionOverviewSection(
            "summary",
            "AUDIT SUMMARY",
            (
                "All quality finders completed over the same saved direct "
                "Context snapshot. Each section retains its own Memory, pair, "
                "group, or absorption unit."
                + (
                    " Conformance evaluated the same Source against "
                    f"{len(conformance.rules)} frozen Rules."
                    if conformance is not None
                    else ""
                )
            ),
        ),
        ResolutionOverviewSection("checks", "CHECKS", checks_text),
        ResolutionOverviewSection(
            "scope",
            "AUDITED SOURCE",
            (
                f"{session.source.context_name} · {len(session.source.memories)} direct "
                "Memories as captured when this Audit ran. Descendants and "
                "embedded Contexts were not analyzed."
            ),
        ),
        ResolutionOverviewSection("provenance", "PROVENANCE", provenance_text),
        ResolutionOverviewSection(
            "boundary",
            "BOUNDARY",
            (
                "This saved Audit is a model-assisted finding record, not proof "
                "that the Source is free of quality problems. Saved historical "
                "review notes do not alter the snapshot, Context, or Memories."
            ),
        ),
    ]
    if conformance is not None:
        rule_by_uid = {rule.uid: rule for rule in conformance.rules}
        sections_list.insert(
            3,
            ResolutionOverviewSection(
                "conformance",
                "CONFORMANCE",
                "\n".join(
                    f"{rule_by_uid[item.rule_uid].alias} · {item.status} · {item.reason}"
                    for item in conformance.context_judgments
                ),
            ),
        )
    sections = tuple(sections_list)
    metrics = [
        ResolutionMetric("SOURCE MEMORIES", str(len(session.source.memories))),
        ResolutionMetric("REDUNDANCIES", str(counts["duplicates"])),
        ResolutionMetric("AMBIGUITIES", str(counts["ambiguities"])),
        ResolutionMetric("CONFLICTS", str(counts["conflicts"])),
    ]
    if conformance is not None:
        metrics.append(
            ResolutionMetric("CONFORMANCE ISSUES", str(conformance.issue_count))
        )
    return ResolutionWorkbenchView(
        operation="AUDIT",
        artifact_uid=session.uid,
        revision=session.snapshot_digest,
        title="MEM AUDIT",
        route=session.source.context_name,
        status=f"SAVED · {check_total}/{check_total} CHECKS · READ-ONLY REPORT",
        metrics=tuple(metrics),
        context_locations=(
            ResolutionContextLocation("AUDITED SOURCE", session.source.context_name),
        ),
        overview=resolution_overview_text(sections),
        overview_sections=sections,
        list_label=(
            "AUDIT CHECKS · REDUNDANCIES → AMBIGUITIES → CONFLICTS"
            + (" · CONFORMANCE IN OVERVIEW" if conformance is not None else "")
        ),
        items=tuple(items),
        empty_message=(
            f"All {check_total} checks completed with no actionable quality findings."
        ),
        results_label="EXACT RESULTS",
        results=(),
        capabilities=frozenset(),
        show_results=False,
    )
