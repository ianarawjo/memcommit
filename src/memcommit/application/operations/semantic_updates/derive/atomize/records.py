"""Durable analysis/application records for one Context-bound Atomize run.

The analysis remains authoritative for issue semantics. The record binds that
immutable issue projection to the exact application checkpoint. Cursor, sort,
response, and Output-plan fields are decoded only for compatibility with the
historical workbench schema and public API; the current Impact and Review
adapters never persist interactive UI state or choose an execution destination.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, Literal

if TYPE_CHECKING:
    from memcommit.application.operations.semantic_updates.derive.atomize.domain import (
        AtomizeAnalysisSession,
        AtomizeChild,
        AtomizeReading,
    )


ATOMIZE_WORKBENCH_SCHEMA_VERSION = 3
ATOMIZE_WORKBENCH_DESTINATION_SCHEMA_VERSION = 2
ATOMIZE_WORKBENCH_LEGACY_SCHEMA_VERSION = 1
ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT = 20_000
ATOMIZE_WORKBENCH_ID_CHAR_LIMIT = 200
ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT = 500

AtomizeReviewSort = Literal["SOURCE", "PRIORITY"]
AtomizeReviewLayout = Literal["SPLIT", "STACKED"]
AtomizeReviewKind = Literal[
    "AMBIGUITY",
    "CONFLICT",
    "ATOMIZE_SPLIT",
    "ATOMIZE_UNCERTAINTY",
]

_SORT_MODES = {"SOURCE", "PRIORITY"}
_LAYOUT_MODES = {"SPLIT", "STACKED"}


class AtomizeRecordError(ValueError):
    """Invalid, corrupt, or analysis-mismatched Atomize record state."""


def _exact_dict(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AtomizeRecordError(f"Invalid {label}.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT,
) -> str:
    if not isinstance(value, str) or (not empty and not value) or len(value) > limit:
        raise AtomizeRecordError(f"Invalid {label}.")
    return value


def _canonical_uuid(value: object, label: str) -> str:
    text = _string(
        value,
        label,
        limit=36,
    )
    try:
        canonical = str(uuid.UUID(text))
    except ValueError as error:
        raise AtomizeRecordError(f"Invalid {label}.") from error
    if text != canonical:
        raise AtomizeRecordError(f"Invalid {label}.")
    return text


def _digest(value: object, label: str) -> str:
    text = _string(value, label, limit=64)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise AtomizeRecordError(f"Invalid {label}.")
    return text


def _identifier(value: object, label: str) -> str:
    return _string(
        value,
        label,
        limit=ATOMIZE_WORKBENCH_ID_CHAR_LIMIT,
    )


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AtomizeRecordError(f"Invalid {label}.")
    return value


@dataclass(frozen=True)
class AtomizeReviewIssue:
    """Immutable UI projection supplied by one analysis revision.

    ``priority`` is intentionally an integer rather than a semantic label.
    The analysis adapter decides how REQUIRED, HELPFUL, conflicts, or
    atomization boundaries map to ordering; this state model only preserves
    and applies that deterministic ordering contract.
    """

    uid: str
    source_order: int
    priority: int
    choice_uids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.uid, "atomize workbench issue uid")
        _integer(self.source_order, "atomize workbench source order")
        _integer(self.priority, "atomize workbench priority")
        if not isinstance(self.choice_uids, tuple):
            raise AtomizeRecordError("Invalid atomize workbench choice uids.")
        parsed = tuple(
            _identifier(value, "atomize workbench choice uid")
            for value in self.choice_uids
        )
        if len(set(parsed)) != len(parsed):
            raise AtomizeRecordError("Duplicate atomize workbench choice uid.")

    def digest_record(self) -> dict[str, object]:
        """Return the exact immutable fields covered by ``issue_digest``."""
        return {
            "uid": self.uid,
            "source_order": self.source_order,
            "priority": self.priority,
            "choice_uids": list(self.choice_uids),
        }


@dataclass(frozen=True)
class AtomizeReviewFinding:
    """Typed read-only view data projected from one saved analysis."""

    uid: str
    kind: AtomizeReviewKind
    source_uids: tuple[str, ...]
    source_order: int
    priority: int
    classification: str
    reason: str
    question: str
    readings: tuple["AtomizeReading", ...] = ()
    children: tuple["AtomizeChild", ...] = ()

    def descriptor(self) -> AtomizeReviewIssue:
        return AtomizeReviewIssue(
            uid=self.uid,
            source_order=self.source_order,
            priority=self.priority,
            choice_uids=tuple(reading.uid for reading in self.readings),
        )


def project_atomize_review_findings(
    analysis: "AtomizeAnalysisSession",
) -> tuple[AtomizeReviewFinding, ...]:
    """Project typed actionable findings without flattening their arity."""
    from memcommit.application.operations.semantic_updates.derive.atomize.domain import AtomizeAnalysisSession

    if not isinstance(analysis, AtomizeAnalysisSession):
        raise AtomizeRecordError("Expected an AtomizeAnalysisSession.")
    position_by_uid = {item.memory_uid: item.position for item in analysis.items}
    findings: list[AtomizeReviewFinding] = []
    clarification_priority = {
        "NONE": 1,
        "HELPFUL": 2,
        "REQUIRED": 4,
    }
    for issue in analysis.quality_issues:
        source_order = min(
            position_by_uid[source_uid] for source_uid in issue.source_uids
        )
        if issue.kind == "AMBIGUITY":
            priority = clarification_priority[issue.clarification or "NONE"]
            # These are independent ambiguity axes. Naming both prevents the
            # clarification requirement from looking like review obligation.
            classification = (
                f"INTERPRETATION · {issue.interpretation}\n"
                f"CLARIFICATION · {issue.clarification}"
            )
        else:
            priority = 4
            # The list and detail heading already carry the issue kind. Keep
            # the classification to the semantic judgment so the UI reads
            # "CONFLICT · MAY", not "CONFLICT · CONFLICT · MAY".
            classification = issue.conflict or "MAY"
        findings.append(
            AtomizeReviewFinding(
                uid=issue.uid,
                kind=issue.kind,
                source_uids=issue.source_uids,
                source_order=source_order,
                priority=priority,
                classification=classification,
                reason=issue.reason,
                question=issue.question,
                readings=issue.readings,
            )
        )
    for item in analysis.items:
        if item.classification not in {"COMPOSITE", "UNCERTAIN"}:
            continue
        uncertain = item.classification == "UNCERTAIN"
        findings.append(
            AtomizeReviewFinding(
                uid=f"atomize:{item.memory_uid}",
                kind=("ATOMIZE_UNCERTAINTY" if uncertain else "ATOMIZE_SPLIT"),
                source_uids=(item.memory_uid,),
                source_order=item.position,
                priority=4 if uncertain else 1,
                classification=(
                    "UNCERTAIN · REQUIRES CONTEXT"
                    if uncertain
                    else (
                        f"COMPOSITE · {len(item.children)} "
                        f"{'CHILD' if len(item.children) == 1 else 'CHILDREN'}"
                    )
                ),
                reason=item.reason,
                question=(
                    "Which local reading or scope should govern this source?"
                    if uncertain
                    else ""
                ),
                children=item.children,
            )
        )
    kind_rank = {
        "AMBIGUITY": 0,
        "CONFLICT": 1,
        "ATOMIZE_UNCERTAINTY": 2,
        "ATOMIZE_SPLIT": 3,
    }
    findings.sort(
        key=lambda finding: (
            finding.source_order,
            kind_rank[finding.kind],
            finding.uid,
        )
    )
    if len({finding.uid for finding in findings}) != len(findings):
        raise AtomizeRecordError("Duplicate projected atomize workbench issue uid.")
    return tuple(findings)


def atomize_review_issue_projection(
    analysis: "AtomizeAnalysisSession",
) -> tuple[AtomizeReviewIssue, ...]:
    """Return the immutable projection covered by a workbench digest."""
    return tuple(
        finding.descriptor() for finding in project_atomize_review_findings(analysis)
    )


def create_atomize_review_record(
    analysis: "AtomizeAnalysisSession",
    *,
    output_context_name: str | None = None,
) -> "AtomizeReviewRecord":
    """Create fresh mutable state pinned to one immutable analysis."""
    return AtomizeReviewRecord.create(
        analysis_uid=analysis.uid,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        output_context_name=output_context_name or analysis.context_name,
        issues=atomize_review_issue_projection(analysis),
    )


def atomize_review_response_digest(
    session: "AtomizeReviewRecord",
) -> str:
    """Content-address semantic answers, excluding cursor and layout state."""
    payload = {
        "workbench_uid": session.uid,
        "analysis_uid": session.analysis_uid,
        "responses": {
            issue.uid: session.responses.get(
                issue.uid,
                AtomizeReviewResponse(),
            ).to_dict()
            for issue in session.issues
        },
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def atomize_review_record_digest(
    session: "AtomizeReviewRecord",
) -> str:
    """Fingerprint the complete mutable record for lifecycle CAS."""

    return hashlib.sha256(
        json.dumps(
            session.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def atomize_review_record_declared_frames(
    session: "AtomizeReviewRecord",
    analysis: "AtomizeAnalysisSession",
):
    """Convert reviewed unary readings/comments into per-Memory frames.

    Pairwise conflict responses remain staged evidence but cannot be smuggled
    into one source Memory's atomization frame. A later reconcile operation
    can consume them with their original two-source arity.  The current
    provenance format also binds one declared frame to exactly one issue, so a
    second answered unary issue for the same Memory must be consolidated or
    cleared before reanalysis instead of being silently misattributed.
    """
    from memcommit.application.operations.semantic_updates.derive.atomize.domain import AtomizeFrameOrigin

    findings = {
        finding.uid: finding for finding in project_atomize_review_findings(analysis)
    }
    if not session.matches_analysis(
        analysis_uid=analysis.uid,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        issues=atomize_review_issue_projection(analysis),
    ):
        raise AtomizeRecordError("The atomize workbench does not match its analysis.")
    entries: dict[str, tuple[AtomizeReviewFinding, str]] = {}
    for issue_uid, response in session.responses.items():
        if not response.answered:
            continue
        finding = findings[issue_uid]
        if len(finding.source_uids) != 1:
            raise AtomizeRecordError(
                "Pairwise conflict responses cannot become single-Memory "
                "atomization frames. They remain staged for a future "
                "reconcile operation; clear them before reviewed reanalysis."
            )
        parts: list[str] = []
        if response.selected_choice_uid is not None:
            reading = next(
                (
                    reading
                    for reading in finding.readings
                    if reading.uid == response.selected_choice_uid
                ),
                None,
            )
            if reading is None:
                raise AtomizeRecordError(
                    "The selected atomize workbench reading is unavailable."
                )
            parts.append(f"Selected ordinary reading: {reading.text}")
        if response.text.strip():
            # A plain free-form answer remains byte-for-byte semantic input.
            # Prefix only when it qualifies a selected proposal, otherwise an
            # older provider contract that expects the exact declared frame
            # would be silently changed by the UI adapter.
            parts.append(
                (
                    "User refinement/comment: "
                    if response.selected_choice_uid is not None
                    else ""
                )
                + response.text.strip()
            )
        if parts:
            memory_uid = finding.source_uids[0]
            if memory_uid in entries:
                raise AtomizeRecordError(
                    "More than one answered unary issue targets the same "
                    "Memory. Consolidate the exact context into one response "
                    "and clear the other before reviewed reanalysis."
                )
            entries[memory_uid] = (finding, "\n".join(parts))

    frames: dict[str, str] = {}
    origins: dict[str, AtomizeFrameOrigin] = {}
    for memory_uid, (finding, text) in entries.items():
        frames[memory_uid] = text
        origins[memory_uid] = AtomizeFrameOrigin(
            review_item_uid=finding.uid,
            source_analysis_uid=analysis.uid,
            uncertainty_reason=finding.reason,
        )
    return frames, origins


def normalize_atomize_review_issues(
    issues: Iterable[AtomizeReviewIssue],
) -> tuple[AtomizeReviewIssue, ...]:
    """Validate and freeze an analysis-provided issue projection."""
    try:
        parsed = tuple(issues)
    except TypeError as error:
        raise AtomizeRecordError("Invalid atomize workbench issues.") from error
    if any(not isinstance(issue, AtomizeReviewIssue) for issue in parsed):
        raise AtomizeRecordError("Invalid atomize workbench issue.")
    if len({issue.uid for issue in parsed}) != len(parsed):
        raise AtomizeRecordError("Duplicate atomize workbench issue uid.")
    return parsed


def atomize_review_issue_digest(
    issues: Iterable[AtomizeReviewIssue],
) -> str:
    """Fingerprint issue identity, order, priority, and selectable readings."""
    parsed = normalize_atomize_review_issues(issues)
    encoded = json.dumps(
        [issue.digest_record() for issue in parsed],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass
class AtomizeReviewResponse:
    """One selected analysis choice plus one deliberately untyped response."""

    selected_choice_uid: str | None = None
    text: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "selected_choice_uid": self.selected_choice_uid,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeReviewResponse":
        data = _exact_dict(
            value,
            {"selected_choice_uid", "text"},
            "atomize workbench response",
        )
        selected = data["selected_choice_uid"]
        if selected is not None:
            selected = _identifier(
                selected,
                "selected atomize workbench choice",
            )
        return cls(
            selected_choice_uid=selected,
            text=_string(
                data["text"],
                "atomize workbench response text",
                empty=True,
            ),
        )

    @property
    def answered(self) -> bool:
        return self.selected_choice_uid is not None or bool(self.text.strip())


@dataclass(frozen=True)
class AtomizeApplicationRecord:
    """Terminal proof that one exact analysis crossed Apply once."""

    output_context_name: str
    checkpoint_uid: str

    def to_dict(self) -> dict[str, str]:
        return {
            "output_context_name": self.output_context_name,
            "checkpoint_uid": self.checkpoint_uid,
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeApplicationRecord":
        data = _exact_dict(
            value,
            {"output_context_name", "checkpoint_uid"},
            "atomize workbench application",
        )
        return cls(
            output_context_name=_string(
                data["output_context_name"],
                "atomize application Output Context name",
                limit=ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT,
            ),
            checkpoint_uid=_canonical_uuid(
                data["checkpoint_uid"],
                "atomize application checkpoint uid",
            ),
        )


@dataclass
class AtomizeReviewRecord:
    """One persisted analysis/application record with legacy UI fields."""

    uid: str
    analysis_uid: str
    context_uid: str
    context_name: str
    context_digest: str
    issue_digest: str
    cursor_uid: str | None
    output_context_name: str | None = None
    sort_mode: AtomizeReviewSort = "SOURCE"
    layout: AtomizeReviewLayout = "SPLIT"
    responses: dict[str, AtomizeReviewResponse] = field(default_factory=dict)
    application: AtomizeApplicationRecord | None = None
    _issues: tuple[AtomizeReviewIssue, ...] = field(
        default=(),
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        # Schema v1 had no destination plan because Atomize was introduced as
        # an in-place operation. Normalize old and directly constructed state
        # to that exact A → A route so every resumed workbench has an Output.
        if self.output_context_name is None:
            self.output_context_name = self.context_name
        _string(
            self.output_context_name,
            "atomize workbench output Context name",
            limit=ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT,
        )
        if self.application is not None:
            if not isinstance(self.application, AtomizeApplicationRecord):
                raise AtomizeRecordError("Invalid atomize workbench application.")
            if self.application.output_context_name != self.output_context_name:
                raise AtomizeRecordError(
                    "Atomize workbench application Output does not match its plan."
                )

    @classmethod
    def create(
        cls,
        *,
        analysis_uid: str,
        context_uid: str,
        context_name: str,
        context_digest: str,
        output_context_name: str | None = None,
        issues: Iterable[AtomizeReviewIssue],
    ) -> "AtomizeReviewRecord":
        """Create a fresh workbench for one exact analysis issue projection."""
        parsed_issues = normalize_atomize_review_issues(issues)
        source_ordered = _ordered_issues(parsed_issues, "SOURCE")
        session = cls(
            uid=str(uuid.uuid4()),
            analysis_uid=_canonical_uuid(
                analysis_uid,
                "atomize analysis uid",
            ),
            context_uid=_canonical_uuid(
                context_uid,
                "atomize workbench Context uid",
            ),
            context_name=_string(
                context_name,
                "atomize workbench Context name",
                limit=ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT,
            ),
            context_digest=_digest(
                context_digest,
                "atomize workbench Context digest",
            ),
            output_context_name=_string(
                output_context_name or context_name,
                "atomize workbench output Context name",
                limit=ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT,
            ),
            issue_digest=atomize_review_issue_digest(parsed_issues),
            cursor_uid=source_ordered[0].uid if source_ordered else None,
            _issues=parsed_issues,
        )
        # Use the same strict loader that protects persisted state so callers
        # cannot create a looser in-memory variant than can later be resumed.
        return cls.from_dict(session.to_dict(), issues=parsed_issues)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": ATOMIZE_WORKBENCH_SCHEMA_VERSION,
            "uid": self.uid,
            "analysis_uid": self.analysis_uid,
            "context": {
                "uid": self.context_uid,
                "name": self.context_name,
                "digest": self.context_digest,
            },
            "output_context_name": self.output_context_name,
            "issue_digest": self.issue_digest,
            "cursor_uid": self.cursor_uid,
            "sort": self.sort_mode,
            "layout": self.layout,
            "responses": {
                issue_uid: response.to_dict()
                for issue_uid, response in self.responses.items()
            },
            "application": (
                None if self.application is None else self.application.to_dict()
            ),
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
        *,
        issues: Iterable[AtomizeReviewIssue],
    ) -> "AtomizeReviewRecord":
        """Restore state only against the exact selected analysis issues."""
        parsed_issues = normalize_atomize_review_issues(issues)
        if not isinstance(value, dict):
            raise AtomizeRecordError("Invalid atomize workbench session.")
        schema_version = value.get("schema_version")
        if isinstance(schema_version, bool):
            raise AtomizeRecordError("Unsupported atomize workbench schema version.")
        common_keys = {
            "schema_version",
            "uid",
            "analysis_uid",
            "context",
            "issue_digest",
            "cursor_uid",
            "sort",
            "layout",
            "responses",
        }
        if schema_version == ATOMIZE_WORKBENCH_LEGACY_SCHEMA_VERSION:
            keys = common_keys
        elif schema_version == ATOMIZE_WORKBENCH_DESTINATION_SCHEMA_VERSION:
            keys = common_keys | {"output_context_name"}
        elif schema_version == ATOMIZE_WORKBENCH_SCHEMA_VERSION:
            keys = common_keys | {"output_context_name", "application"}
        else:
            raise AtomizeRecordError("Unsupported atomize workbench schema version.")
        data = _exact_dict(
            value,
            keys,
            "atomize workbench session",
        )
        context = _exact_dict(
            data["context"],
            {"uid", "name", "digest"},
            "atomize workbench Context",
        )
        expected_issue_digest = atomize_review_issue_digest(parsed_issues)
        stored_issue_digest = _digest(
            data["issue_digest"],
            "atomize workbench issue digest",
        )
        if stored_issue_digest != expected_issue_digest:
            raise AtomizeRecordError(
                "Atomize workbench issues do not match the analysis."
            )

        issue_by_uid = {issue.uid: issue for issue in parsed_issues}
        cursor_uid = data["cursor_uid"]
        if cursor_uid is not None:
            cursor_uid = _identifier(
                cursor_uid,
                "atomize workbench cursor",
            )
        if (not parsed_issues and cursor_uid is not None) or (
            parsed_issues and cursor_uid not in issue_by_uid
        ):
            raise AtomizeRecordError("Invalid atomize workbench cursor.")

        sort_mode = data["sort"]
        layout = data["layout"]
        if not isinstance(sort_mode, str) or sort_mode not in _SORT_MODES:
            raise AtomizeRecordError("Invalid atomize workbench sort mode.")
        if not isinstance(layout, str) or layout not in _LAYOUT_MODES:
            raise AtomizeRecordError("Invalid atomize workbench layout.")

        raw_responses = data["responses"]
        if not isinstance(raw_responses, dict):
            raise AtomizeRecordError("Invalid atomize workbench responses.")
        responses: dict[str, AtomizeReviewResponse] = {}
        for issue_uid, raw_response in raw_responses.items():
            if (
                not isinstance(issue_uid, str)
                or issue_uid not in issue_by_uid
                or issue_uid in responses
            ):
                raise AtomizeRecordError("Invalid atomize workbench response target.")
            response = AtomizeReviewResponse.from_dict(raw_response)
            if (
                response.selected_choice_uid is not None
                and response.selected_choice_uid
                not in issue_by_uid[issue_uid].choice_uids
            ):
                raise AtomizeRecordError(
                    "Atomize workbench response selects an unknown choice."
                )
            responses[issue_uid] = response

        return cls(
            uid=_canonical_uuid(
                data["uid"],
                "atomize workbench session uid",
            ),
            analysis_uid=_canonical_uuid(
                data["analysis_uid"],
                "atomize analysis uid",
            ),
            context_uid=_canonical_uuid(
                context["uid"],
                "atomize workbench Context uid",
            ),
            context_name=_string(
                context["name"],
                "atomize workbench Context name",
                limit=ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT,
            ),
            context_digest=_digest(
                context["digest"],
                "atomize workbench Context digest",
            ),
            issue_digest=stored_issue_digest,
            cursor_uid=cursor_uid,
            output_context_name=_string(
                (
                    context["name"]
                    if schema_version == ATOMIZE_WORKBENCH_LEGACY_SCHEMA_VERSION
                    else data["output_context_name"]
                ),
                "atomize workbench output Context name",
                limit=ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT,
            ),
            application=(
                None
                if schema_version != ATOMIZE_WORKBENCH_SCHEMA_VERSION
                or data["application"] is None
                else AtomizeApplicationRecord.from_dict(data["application"])
            ),
            sort_mode=sort_mode,  # type: ignore[arg-type]
            layout=layout,  # type: ignore[arg-type]
            responses=responses,
            _issues=parsed_issues,
        )

    def record_application(
        self,
        *,
        output_context_name: str,
        checkpoint_uid: str,
    ) -> None:
        """Make Apply terminal without preventing later comment edits."""

        receipt = AtomizeApplicationRecord(
            output_context_name=_string(
                output_context_name,
                "atomize application Output Context name",
                limit=ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT,
            ),
            checkpoint_uid=_canonical_uuid(
                checkpoint_uid,
                "atomize application checkpoint uid",
            ),
        )
        if receipt.output_context_name != self.output_context_name:
            raise AtomizeRecordError(
                "Atomize application Output does not match the workbench plan."
            )
        if self.application is not None and self.application != receipt:
            raise AtomizeRecordError(
                "Atomize workbench already records a different application."
            )
        self.application = receipt

    def clear_application(
        self,
        *,
        output_context_name: str,
        checkpoint_uid: str,
        restore_output_context_name: str,
    ) -> None:
        """Return one exact terminal Save As receipt to its reviewing route."""

        if (
            self.application is None
            or self.application.output_context_name != output_context_name
            or self.application.checkpoint_uid != checkpoint_uid
        ):
            raise AtomizeRecordError(
                "Atomize workbench does not record this application."
            )
        self.output_context_name = _string(
            restore_output_context_name,
            "atomize workbench output Context name",
            limit=ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT,
        )
        self.application = None

    def matches_analysis(
        self,
        *,
        analysis_uid: str,
        context_uid: str,
        context_name: str,
        context_digest: str,
        issues: Iterable[AtomizeReviewIssue],
    ) -> bool:
        """Return whether this state can safely resume one exact revision."""
        try:
            parsed_issues = normalize_atomize_review_issues(issues)
            return (
                self.analysis_uid
                == _canonical_uuid(analysis_uid, "atomize analysis uid")
                and self.context_uid
                == _canonical_uuid(
                    context_uid,
                    "atomize workbench Context uid",
                )
                and self.context_name
                == _string(
                    context_name,
                    "atomize workbench Context name",
                    limit=ATOMIZE_WORKBENCH_CONTEXT_NAME_CHAR_LIMIT,
                )
                and self.context_digest
                == _digest(
                    context_digest,
                    "atomize workbench Context digest",
                )
                and self.issue_digest == atomize_review_issue_digest(parsed_issues)
            )
        except AtomizeRecordError:
            return False

    def ordered_issues(self) -> list[AtomizeReviewIssue]:
        return _ordered_issues(self._issues, self.sort_mode)

    @property
    def issues(self) -> tuple[AtomizeReviewIssue, ...]:
        """Expose the immutable projection without exposing mutable responses."""
        return self._issues

    @property
    def issue_count(self) -> int:
        return len(self._issues)

    def current_issue(self) -> AtomizeReviewIssue | None:
        ordered = self.ordered_issues()
        if not ordered:
            self.cursor_uid = None
            return None
        current = next(
            (issue for issue in ordered if issue.uid == self.cursor_uid),
            ordered[0],
        )
        self.cursor_uid = current.uid
        return current

    def response_for(self, issue_uid: str) -> AtomizeReviewResponse:
        if issue_uid not in {issue.uid for issue in self._issues}:
            raise AtomizeRecordError("Unknown atomize workbench issue.")
        return self.responses.setdefault(
            issue_uid,
            AtomizeReviewResponse(),
        )

    def move(self, delta: int) -> None:
        if isinstance(delta, bool) or not isinstance(delta, int):
            raise AtomizeRecordError("Invalid atomize workbench movement.")
        ordered = self.ordered_issues()
        if not ordered:
            self.cursor_uid = None
            return
        current = self.current_issue()
        assert current is not None
        index = next(
            index for index, issue in enumerate(ordered) if issue.uid == current.uid
        )
        next_index = max(0, min(index + delta, len(ordered) - 1))
        self.cursor_uid = ordered[next_index].uid

    def select_choice(self, choice_index: int | None) -> None:
        issue = self.current_issue()
        if issue is None:
            return
        response = self.response_for(issue.uid)
        if choice_index is None:
            response.selected_choice_uid = None
            return
        if (
            isinstance(choice_index, bool)
            or not isinstance(choice_index, int)
            or choice_index < 0
            or choice_index >= len(issue.choice_uids)
        ):
            raise AtomizeRecordError("Unknown atomize workbench choice.")
        response.selected_choice_uid = issue.choice_uids[choice_index]

    def selected_choice_index(
        self,
        issue: AtomizeReviewIssue | None = None,
    ) -> int | None:
        issue = issue or self.current_issue()
        if issue is None:
            return None
        selected = self.response_for(issue.uid).selected_choice_uid
        if selected is None:
            return None
        try:
            return issue.choice_uids.index(selected)
        except ValueError as error:
            # This indicates post-load mutation outside the public methods.
            raise AtomizeRecordError(
                "Atomize workbench response selects an unknown choice."
            ) from error

    def toggle_sort(self) -> None:
        self.sort_mode = "PRIORITY" if self.sort_mode == "SOURCE" else "SOURCE"
        # Cursor identity is stable across order changes; do not silently jump
        # to whichever issue happens to become first.
        self.current_issue()

    def toggle_layout(self) -> None:
        self.layout = "STACKED" if self.layout == "SPLIT" else "SPLIT"

    @property
    def answered_count(self) -> int:
        return sum(response.answered for response in self.responses.values())


def _ordered_issues(
    issues: tuple[AtomizeReviewIssue, ...],
    sort_mode: AtomizeReviewSort,
) -> list[AtomizeReviewIssue]:
    indexed = list(enumerate(issues))
    if sort_mode == "SOURCE":
        ordered = sorted(
            indexed,
            key=lambda pair: (pair[1].source_order, pair[0]),
        )
    else:
        ordered = sorted(
            indexed,
            key=lambda pair: (
                -pair[1].priority,
                pair[1].source_order,
                pair[0],
            ),
        )
    return [issue for _, issue in ordered]
