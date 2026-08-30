"""Typed, adapter-neutral handoff from quality findings to repair operations.

Finders remain read-only observations.  A handoff names the next operation and
binds it to the exact frozen direct-Memory source, but carries no mutation
authority.  The receiving operation must freeze authority and capabilities
again before semantic execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from collections.abc import Mapping
from typing import Literal

from memcommit.application.capabilities.reviewing.memory_issue_finding.findings import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.workbench import (
    QualityFindResponse,
    QualityFindSourceFrame,
    QualityFindWorkbenchError,
    QualityFindWorkbenchSession,
)
from memcommit.application.operations.resolve.application import (
    ResolveFitTarget,
    ResolveRequest,
    ResolveSourcePrecondition,
)
from memcommit.application.operations.review.model import REVIEW_RESPONSE_CHAR_LIMIT


QUALITY_FINDING_HANDOFF_CONTRACT_VERSION = "quality-finding-handoff-v1"
QualityFindingKind = Literal["DUPLICATE", "AMBIGUITY", "CONFLICT"]
QualityFindingRoute = Literal["DEDUP", "CLARIFY", "RESOLVE"]


class QualityFindingHandoffError(ValueError):
    """A finder result cannot safely enter its receiving operation."""


@dataclass(frozen=True)
class QualityFindingSource:
    """One frozen readable Context contributing to a quality finding frame."""

    context_uid: str
    display_name: str
    direct_memory_digest: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.context_uid, self.display_name)
        ):
            raise QualityFindingHandoffError(
                "Quality finding source requires a Context identity."
            )
        if (
            not isinstance(self.direct_memory_digest, str)
            or len(self.direct_memory_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.direct_memory_digest
            )
        ):
            raise QualityFindingHandoffError(
                "Quality finding source requires a SHA-256 Memory digest."
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "context_uid": self.context_uid,
            "display_name": self.display_name,
            "direct_memory_digest": self.direct_memory_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> "QualityFindingSource":
        data = _exact_dict(
            value,
            {"context_uid", "display_name", "direct_memory_digest"},
            "quality finding source",
        )
        return cls(
            context_uid=_text(data["context_uid"], "source Context uid"),
            display_name=_text(data["display_name"], "source display name"),
            direct_memory_digest=_text(
                data["direct_memory_digest"],
                "source direct-Memory digest",
            ),
        )


@dataclass(frozen=True)
class QualityFindingReviewDraft:
    """Process-local reviewer state that is not executable guidance."""

    selected_option_uid: str | None = None
    text: str = ""

    def __post_init__(self) -> None:
        if self.selected_option_uid is not None and (
            not isinstance(self.selected_option_uid, str)
            or not self.selected_option_uid
        ):
            raise QualityFindingHandoffError(
                "Quality finding draft option identity is invalid."
            )
        if (
            not isinstance(self.text, str)
            or len(self.text) > REVIEW_RESPONSE_CHAR_LIMIT
        ):
            raise QualityFindingHandoffError(
                "Quality finding draft response is invalid."
            )

    @property
    def answered(self) -> bool:
        return self.selected_option_uid is not None or bool(self.text.strip())

    def to_dict(self) -> dict[str, str | None]:
        return {
            "selected_option_uid": self.selected_option_uid,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, value: object) -> "QualityFindingReviewDraft":
        data = _exact_dict(
            value,
            {"selected_option_uid", "text"},
            "quality finding review draft",
        )
        option_uid = data["selected_option_uid"]
        if option_uid is not None:
            option_uid = _text(option_uid, "review draft option uid")
        return cls(
            selected_option_uid=option_uid,
            text=_text(data["text"], "review draft text", empty=True),
        )


@dataclass(frozen=True)
class QualityFindingHandoff:
    """One immutable finding identity plus its intended next operation."""

    uid: str
    finding_uid: str
    kind: QualityFindingKind
    route: QualityFindingRoute
    source_frame_digest: str
    sources: tuple[QualityFindingSource, ...]
    memory_uids: tuple[str, ...]
    memory_context_names: tuple[str, ...]
    classification: str
    qualifiers: tuple[str, ...]
    reason: str
    question: str
    proposed_readings: tuple[str, ...]
    review_draft: QualityFindingReviewDraft

    def __post_init__(self) -> None:
        expected_route = {
            "DUPLICATE": "DEDUP",
            "AMBIGUITY": "CLARIFY",
            "CONFLICT": "RESOLVE",
        }.get(self.kind)
        if expected_route is None or self.route != expected_route:
            raise QualityFindingHandoffError(
                "Quality finding kind and next-operation route do not match."
            )
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.uid,
                self.finding_uid,
                self.source_frame_digest,
                self.classification,
                self.reason,
            )
        ):
            raise QualityFindingHandoffError(
                "Quality finding handoff identity and explanation are incomplete."
            )
        if len(self.source_frame_digest) != 64 or any(
            character not in "0123456789abcdef"
            for character in self.source_frame_digest
        ):
            raise QualityFindingHandoffError("Quality finding frame digest is invalid.")
        if (
            not self.sources
            or any(
                not isinstance(source, QualityFindingSource) for source in self.sources
            )
            or len({source.context_uid for source in self.sources}) != len(self.sources)
            or len({source.display_name for source in self.sources})
            != len(self.sources)
        ):
            raise QualityFindingHandoffError(
                "Quality finding handoff requires distinct source Contexts."
            )
        if (
            not self.memory_uids
            or len(self.memory_uids) != len(self.memory_context_names)
            or len(set(self.memory_uids)) != len(self.memory_uids)
            or any(
                not isinstance(value, str) or not value for value in self.memory_uids
            )
            or any(
                not isinstance(value, str) or not value
                for value in self.memory_context_names
            )
            or any(
                name not in {source.display_name for source in self.sources}
                for name in self.memory_context_names
            )
        ):
            raise QualityFindingHandoffError(
                "Quality finding Memory ownership is invalid."
            )
        if any(
            not isinstance(value, str) or not value
            for value in (*self.qualifiers, *self.proposed_readings)
        ):
            raise QualityFindingHandoffError(
                "Quality finding qualifiers and readings must be nonempty text."
            )
        if not isinstance(self.question, str) or not isinstance(
            self.review_draft,
            QualityFindingReviewDraft,
        ):
            raise QualityFindingHandoffError(
                "Quality finding question or review draft is invalid."
            )

    def to_dict(self) -> dict[str, object]:
        """Return the strict JSON-safe cross-adapter receipt."""

        return {
            "contract": QUALITY_FINDING_HANDOFF_CONTRACT_VERSION,
            "uid": self.uid,
            "finding_uid": self.finding_uid,
            "kind": self.kind,
            "route": self.route,
            "source_frame_digest": self.source_frame_digest,
            "sources": [source.to_dict() for source in self.sources],
            "memory_uids": list(self.memory_uids),
            "memory_context_names": list(self.memory_context_names),
            "classification": self.classification,
            "qualifiers": list(self.qualifiers),
            "reason": self.reason,
            "question": self.question,
            "proposed_readings": list(self.proposed_readings),
            "review_draft": self.review_draft.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> "QualityFindingHandoff":
        """Decode one receipt and verify its deterministic finding identity."""

        data = _exact_dict(
            value,
            {
                "contract",
                "uid",
                "finding_uid",
                "kind",
                "route",
                "source_frame_digest",
                "sources",
                "memory_uids",
                "memory_context_names",
                "classification",
                "qualifiers",
                "reason",
                "question",
                "proposed_readings",
                "review_draft",
            },
            "quality finding handoff",
        )
        if data["contract"] != QUALITY_FINDING_HANDOFF_CONTRACT_VERSION:
            raise QualityFindingHandoffError(
                "Unsupported quality finding handoff contract."
            )
        kind = _text(data["kind"], "finding kind")
        route = _text(data["route"], "finding route")
        if kind not in {"DUPLICATE", "AMBIGUITY", "CONFLICT"} or route not in {
            "DEDUP",
            "CLARIFY",
            "RESOLVE",
        }:
            raise QualityFindingHandoffError(
                "Quality finding handoff kind or route is invalid."
            )
        sources = _objects(data["sources"], "quality finding sources")
        result = cls(
            uid=_text(data["uid"], "handoff uid"),
            finding_uid=_text(data["finding_uid"], "finding uid"),
            kind=kind,  # type: ignore[arg-type]
            route=route,  # type: ignore[arg-type]
            source_frame_digest=_text(
                data["source_frame_digest"],
                "source frame digest",
            ),
            sources=tuple(QualityFindingSource.from_dict(item) for item in sources),
            memory_uids=_strings(data["memory_uids"], "finding Memory uids"),
            memory_context_names=_strings(
                data["memory_context_names"],
                "finding Memory owner names",
            ),
            classification=_text(data["classification"], "classification"),
            qualifiers=_strings(data["qualifiers"], "finding qualifiers"),
            reason=_text(data["reason"], "finding reason"),
            question=_text(data["question"], "finding question", empty=True),
            proposed_readings=_strings(
                data["proposed_readings"],
                "proposed readings",
            ),
            review_draft=QualityFindingReviewDraft.from_dict(data["review_draft"]),
        )
        if result.uid != _handoff_uid(_identity_payload(result)):
            raise QualityFindingHandoffError(
                "Quality finding handoff identity does not match its contents."
            )
        return result


def _exact_dict(
    value: object,
    keys: set[str],
    label: str,
) -> Mapping[str, object]:
    if (
        not isinstance(value, Mapping)
        or set(value) != keys
        or any(not isinstance(key, str) for key in value)
    ):
        raise QualityFindingHandoffError(f"Invalid {label}.")
    return value


def _text(value: object, label: str, *, empty: bool = False) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value)
        or len(value) > REVIEW_RESPONSE_CHAR_LIMIT
    ):
        raise QualityFindingHandoffError(f"Invalid {label}.")
    return value


def _objects(value: object, label: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise QualityFindingHandoffError(f"Invalid {label}.")
    return tuple(value)


def _strings(value: object, label: str) -> tuple[str, ...]:
    values = _objects(value, label)
    if any(not isinstance(item, str) or not item for item in values):
        raise QualityFindingHandoffError(f"Invalid {label}.")
    return tuple(values)  # type: ignore[return-value]


def _require_current_source(source: QualityFindSourceFrame) -> None:
    try:
        current = QualityFindSourceFrame.create(
            source.contexts,
            context_names=source.context_names,
            target_names=source.target_names,
            selection_mode=source.selection_mode,
            include_descendants=source.include_descendants,
            profile_selected=source.profile_selected,
        )
    except QualityFindWorkbenchError as error:
        raise QualityFindingHandoffError(str(error)) from error
    if current.digest != source.digest:
        raise QualityFindingHandoffError(
            "Quality finding source changed after analysis. Run the finder again."
        )


def _source_bindings(
    source: QualityFindSourceFrame,
) -> tuple[QualityFindingSource, ...]:
    return tuple(
        QualityFindingSource(
            context_uid=context.uid,
            display_name=name,
            direct_memory_digest=digest,
        )
        for context, name, digest in zip(
            source.contexts,
            source.context_names,
            source.context_digests,
        )
    )


def _review_draft(response: QualityFindResponse | None) -> QualityFindingReviewDraft:
    if response is None:
        return QualityFindingReviewDraft()
    return QualityFindingReviewDraft(
        selected_option_uid=response.selected_option_uid,
        text=response.text,
    )


def _handoff_uid(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "finding-" + hashlib.sha256(encoded).hexdigest()


def _identity_payload(handoff: QualityFindingHandoff) -> dict[str, object]:
    return {
        "contract": QUALITY_FINDING_HANDOFF_CONTRACT_VERSION,
        "source_frame_digest": handoff.source_frame_digest,
        "sources": [source.to_dict() for source in handoff.sources],
        "finding_uid": handoff.finding_uid,
        "kind": handoff.kind,
        "route": handoff.route,
        "memory_uids": list(handoff.memory_uids),
        "memory_context_names": list(handoff.memory_context_names),
        "classification": handoff.classification,
        "qualifiers": list(handoff.qualifiers),
        "reason": handoff.reason,
        "question": handoff.question,
        "proposed_readings": list(handoff.proposed_readings),
    }


def _build_handoff(
    session: QualityFindWorkbenchSession,
    *,
    finding_uid: str,
    kind: QualityFindingKind,
    route: QualityFindingRoute,
    memory_uids: tuple[str, ...],
    classification: str,
    qualifiers: tuple[str, ...] = (),
    reason: str,
    question: str = "",
    proposed_readings: tuple[str, ...] = (),
) -> QualityFindingHandoff:
    owner_by_uid = session.source.memory_context_names
    memory_context_names = tuple(owner_by_uid[uid] for uid in memory_uids)
    result = QualityFindingHandoff(
        uid="pending",
        finding_uid=finding_uid,
        kind=kind,
        route=route,
        source_frame_digest=session.source.digest,
        sources=_source_bindings(session.source),
        memory_uids=memory_uids,
        memory_context_names=memory_context_names,
        classification=classification,
        qualifiers=qualifiers,
        reason=reason,
        question=question,
        proposed_readings=proposed_readings,
        review_draft=_review_draft(session.responses.get(finding_uid)),
    )
    return replace(result, uid=_handoff_uid(_identity_payload(result)))


def quality_finding_handoffs(
    session: QualityFindWorkbenchSession,
) -> tuple[QualityFindingHandoff, ...]:
    """Normalize every emitted finding without changing its read-only source."""

    if not isinstance(session, QualityFindWorkbenchSession):
        raise TypeError("Quality finding handoff requires a workbench session.")
    _require_current_source(session.source)
    if session.kind == "duplicates":
        if not isinstance(session.report, DuplicateReport):
            raise QualityFindingHandoffError(
                "Duplicate handoff requires a duplicate report."
            )
        if any(
            not isinstance(finding, DuplicateFinding)
            for finding in session.report.findings
        ):
            raise QualityFindingHandoffError(
                "Duplicate report contains an invalid finding."
            )
        return tuple(
            _build_handoff(
                session,
                finding_uid=f"duplicate:{finding.left.uid}:{finding.right.uid}",
                kind="DUPLICATE",
                route="DEDUP",
                memory_uids=(finding.left.uid, finding.right.uid),
                classification=finding.relation,
                reason=finding.reason,
            )
            for finding in session.report.findings
        )
    if session.kind == "ambiguities":
        if not isinstance(session.report, AmbiguityReport):
            raise QualityFindingHandoffError(
                "Ambiguity handoff requires an ambiguity report."
            )
        if any(
            not isinstance(finding, AmbiguityFinding)
            for finding in session.report.findings
        ):
            raise QualityFindingHandoffError(
                "Ambiguity report contains an invalid finding."
            )
        return tuple(
            _build_handoff(
                session,
                finding_uid=f"ambiguity:{finding.memory.uid}",
                kind="AMBIGUITY",
                route="CLARIFY",
                memory_uids=(finding.memory.uid,),
                classification=finding.interpretation,
                qualifiers=(finding.clarification,),
                reason=finding.reason,
                question=finding.question,
                proposed_readings=finding.ordinary_readings,
            )
            for finding in session.report.findings
        )
    if session.kind == "conflicts":
        if not isinstance(session.report, ConflictReport):
            raise QualityFindingHandoffError(
                "Conflict handoff requires a conflict report."
            )
        if any(
            not isinstance(finding, ConflictFinding)
            for finding in session.report.findings
        ):
            raise QualityFindingHandoffError(
                "Conflict report contains an invalid finding."
            )
        return tuple(
            _build_handoff(
                session,
                finding_uid=f"conflict:{finding.left.uid}:{finding.right.uid}",
                kind="CONFLICT",
                route="RESOLVE",
                memory_uids=(finding.left.uid, finding.right.uid),
                classification=finding.conflict,
                reason=finding.reason,
                question=finding.question,
            )
            for finding in session.report.findings
        )
    raise QualityFindingHandoffError(
        f"Unsupported quality finder kind '{session.kind}'."
    )


def quality_finding_handoff(
    session: QualityFindWorkbenchSession,
    finding_uid: str,
) -> QualityFindingHandoff:
    """Select one exact handoff by the shared Resolution item identity."""

    matches = tuple(
        handoff
        for handoff in quality_finding_handoffs(session)
        if handoff.finding_uid == finding_uid
    )
    if len(matches) != 1:
        raise QualityFindingHandoffError(
            f"Quality finding '{finding_uid}' is unavailable."
        )
    return matches[0]


def conflict_handoff_to_resolve_request(
    handoff: QualityFindingHandoff,
    *,
    allow_create: bool = True,
    allow_delete: bool = False,
    guidance: str = "",
    target_fit: ResolveFitTarget = "MAY",
) -> ResolveRequest:
    """Enter Resolve only for one conflict from one exact direct Context.

    ``review_draft`` is deliberately ignored. A caller may pass separately
    submitted guidance, but merely typing or selecting inside the finder review
    cannot expand Resolve semantics or authorize DELETE.
    """

    if not isinstance(handoff, QualityFindingHandoff):
        raise TypeError("Conflict-to-Resolve conversion requires a typed handoff.")
    if handoff.kind != "CONFLICT" or handoff.route != "RESOLVE":
        raise QualityFindingHandoffError("Only a conflict finding can enter Resolve.")
    if len(handoff.sources) != 1:
        raise QualityFindingHandoffError(
            "Resolve v1 requires a conflict found in one exact Context; "
            "cross-Context findings need a separate reconciliation operation."
        )
    source = handoff.sources[0]
    if len(handoff.memory_uids) != 2 or any(
        name != source.display_name for name in handoff.memory_context_names
    ):
        raise QualityFindingHandoffError(
            "Resolve v1 requires both conflicting Memories to be directly owned "
            "by the same Context."
        )
    return ResolveRequest(
        context_name=source.display_name,
        memory_selectors=handoff.memory_uids,
        allow_create=allow_create,
        allow_delete=allow_delete,
        guidance=guidance,
        target_fit=target_fit,
        source_precondition=ResolveSourcePrecondition(
            context_uid=source.context_uid,
            display_name=source.display_name,
            direct_memory_digest=source.direct_memory_digest,
        ),
    )


def quality_finding_handoff_json(handoff: QualityFindingHandoff) -> str:
    """Serialize one receipt canonically for an explicit CLI boundary."""

    if not isinstance(handoff, QualityFindingHandoff):
        raise TypeError("Quality finding JSON requires a typed handoff.")
    return json.dumps(
        handoff.to_dict(),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def quality_finding_handoff_from_json(value: str) -> QualityFindingHandoff:
    """Decode one strict receipt, rejecting duplicate JSON keys."""

    if not isinstance(value, str) or not value.strip():
        raise QualityFindingHandoffError(
            "Quality finding handoff JSON must be nonblank text."
        )

    def exact_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise QualityFindingHandoffError(
                    f"Duplicate quality finding handoff JSON key '{key}'."
                )
            result[key] = item
        return result

    try:
        decoded = json.loads(value, object_pairs_hook=exact_pairs)
    except (json.JSONDecodeError, ValueError) as error:
        if isinstance(error, QualityFindingHandoffError):
            raise
        raise QualityFindingHandoffError(
            "Quality finding handoff JSON is invalid."
        ) from error
    return QualityFindingHandoff.from_dict(decoded)


__all__ = [
    "QUALITY_FINDING_HANDOFF_CONTRACT_VERSION",
    "QualityFindingHandoff",
    "QualityFindingHandoffError",
    "QualityFindingKind",
    "QualityFindingReviewDraft",
    "QualityFindingRoute",
    "QualityFindingSource",
    "conflict_handoff_to_resolve_request",
    "quality_finding_handoff_from_json",
    "quality_finding_handoff_json",
    "quality_finding_handoff",
    "quality_finding_handoffs",
]
