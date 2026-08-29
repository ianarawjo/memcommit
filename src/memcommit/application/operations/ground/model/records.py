"""Validated records for durable common-grounding sessions.

Schema version 1 is the original empty scaffold.  Schema version 2 binds that
scaffold to an immutable task brief and exact Context frames, then permits
small, explicitly reviewed Rule/Memory rounds.  Grounding changes only this
artifact; applying accepted Ground Memories to Contexts remains separate.

The persisted ``CASE`` vocabulary remains a schema-compatibility boundary.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Literal

from memcommit.application.operations.ground.contracts import (
    GROUND_TEXT_LIMIT,
    GroundError,
)


GROUND_SCHEMA_VERSION = 2
GROUND_PROPOSITION_SCHEMA_VERSION = 3
GROUND_LEGACY_SCHEMA_VERSION = 1
GroundStatus = Literal["OPEN", "GROUNDED", "DEFERRED"]
GroundItemKind = Literal["RULE", "CASE", "ISSUE", "DECISION"]
GroundItemStatus = Literal[
    "PROPOSED",
    "ACCEPTED",
    "REJECTED",
    "DEFERRED",
    "RESOLVED",
]
GroundOrigin = Literal["USER", "AGENT", "JOINT"]
GroundFrameRole = Literal[
    "RAW_EVIDENCE",
    "WORKING_CANDIDATES",
    "PUBLICATION_TARGET",
    "PLACEMENT_TARGET",
]
GroundCaseRole = Literal["FIT", "BOUNDARY", "CONTRAST"]
GroundDisposition = Literal["INCLUDE", "EXCLUDE", "UNRESOLVED"]
GroundTargetStatus = Literal["EMPTY", "PARTIAL", "COVERED", "BLOCKED"]
GroundRuleProvenance = Literal[
    "USER_STATED",
    "DISTILLED",
    "DISTILLED_FROM_GOAL",
    "INDUCED_FROM_CASES",
    "JOINTLY_REVISED",
]

_GROUND_STATUSES = {"OPEN", "GROUNDED", "DEFERRED"}
_ITEM_KINDS = {"RULE", "CASE", "ISSUE", "DECISION"}
_ITEM_STATUSES = {
    "PROPOSED",
    "ACCEPTED",
    "REJECTED",
    "DEFERRED",
    "RESOLVED",
}
_ORIGINS = {"USER", "AGENT", "JOINT"}
_READING_STATUSES = {"UNREAD", "READ"}
_FRAME_ROLES = {
    "RAW_EVIDENCE",
    "WORKING_CANDIDATES",
    "PUBLICATION_TARGET",
    "PLACEMENT_TARGET",
}
_TARGET_FRAME_ROLES = {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
_CASE_ROLES = {"FIT", "BOUNDARY", "CONTRAST"}
_LEGACY_CASE_ROLE = {"REPRESENTATIVE": "FIT"}
_DISPOSITIONS = {"INCLUDE", "EXCLUDE", "UNRESOLVED"}
_RULE_PROVENANCE = {
    "USER_STATED",
    "DISTILLED",
    "DISTILLED_FROM_GOAL",
    "INDUCED_FROM_CASES",
    "JOINTLY_REVISED",
}
_REVIEW_ACTIONS = {"ACCEPT", "REFINE", "DEFER", "REJECT"}
LEGACY_COMPLETION_MARKER = (
    "Reserved for schema compatibility; Ground agreement is not determined "
    "by a separate completion criterion."
)
# Keep the earlier import name available to code that reads version 1/2 data.
# New CLI and provider contracts do not expose a completion criterion.
DEFAULT_COMPLETION_CRITERION = LEGACY_COMPLETION_MARKER


def is_bound_ground_schema(schema_version: int) -> bool:
    """Return whether a Ground has explicit immutable Context frames."""

    return schema_version in {
        GROUND_SCHEMA_VERSION,
        GROUND_PROPOSITION_SCHEMA_VERSION,
    }


def _exact_dict(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise GroundError(f"Invalid {label}.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = GROUND_TEXT_LIMIT,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
    ):
        raise GroundError(f"Invalid {label}.")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GroundError(f"Invalid {label}.")
    return value


def _uuid(value: object, label: str) -> str:
    parsed = _string(value, label, limit=100)
    try:
        canonical = str(uuid.UUID(parsed))
    except ValueError as error:
        raise GroundError(f"Invalid {label}.") from error
    if canonical != parsed:
        raise GroundError(f"Invalid {label}.")
    return parsed


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest(value: object, label: str) -> str:
    result = _string(value, label, limit=64)
    if len(result) != 64 or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise GroundError(f"Invalid {label}.")
    return result


@dataclass(frozen=True)
class GroundBrief:
    """Immutable task description copied into a grounding workbench."""

    content: str
    provenance: str
    digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            "content": self.content,
            "provenance": self.provenance,
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundBrief":
        data = _exact_dict(
            value,
            {"content", "provenance", "digest"},
            "grounding brief",
        )
        content = _string(data["content"], "grounding brief content")
        provenance = _string(
            data["provenance"],
            "grounding brief provenance",
            limit=100,
        )
        if provenance != "USER_PROVIDED_TASK_DESCRIPTION":
            raise GroundError("Invalid grounding brief provenance.")
        digest = _digest(data["digest"], "grounding brief digest")
        if digest != _sha256_text(content):
            raise GroundError("Grounding brief digest does not match content.")
        return cls(
            content=content,
            provenance=provenance,
            digest=digest,
        )


@dataclass(frozen=True)
class GroundFrame:
    """One exact raw, derived, or target Context bound to a workbench."""

    role: GroundFrameRole
    context_uid: str
    context_name: str
    context_digest: str
    direct_memory_count: int
    direct_item_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
            "direct_memory_count": self.direct_memory_count,
            "direct_item_count": self.direct_item_count,
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundFrame":
        data = _exact_dict(
            value,
            {
                "role",
                "context_uid",
                "context_name",
                "context_digest",
                "direct_memory_count",
                "direct_item_count",
            },
            "grounding frame",
        )
        role = _string(data["role"], "grounding frame role", limit=40)
        if role not in _FRAME_ROLES:
            raise GroundError("Invalid grounding frame role.")
        memory_count = _integer(
            data["direct_memory_count"],
            "grounding frame Memory count",
        )
        item_count = _integer(
            data["direct_item_count"],
            "grounding frame item count",
        )
        if memory_count > item_count:
            raise GroundError("Invalid grounding frame counts.")
        return cls(
            role=role,
            context_uid=_uuid(
                data["context_uid"],
                "grounding frame Context uid",
            ),
            context_name=_string(
                data["context_name"],
                "grounding frame Context name",
                limit=500,
            ),
            context_digest=_digest(
                data["context_digest"],
                "grounding frame digest",
            ),
            direct_memory_count=memory_count,
            direct_item_count=item_count,
        )


@dataclass(frozen=True)
class GroundTargetSpec:
    """Input requirement for one target slot when binding a workbench."""

    context_name: str
    description: str
    role: GroundFrameRole = "PLACEMENT_TARGET"
    minimum_accepted_cases: int = 1
    blocked_reason: str = ""


@dataclass(frozen=True)
class GroundTargetRequirement:
    """Coverage requirement for one target Context."""

    uid: str
    target_context_uid: str
    description: str
    minimum_accepted_cases: int
    blocked_reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "target_context_uid": self.target_context_uid,
            "description": self.description,
            "minimum_accepted_cases": self.minimum_accepted_cases,
            "blocked_reason": self.blocked_reason,
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundTargetRequirement":
        data = _exact_dict(
            value,
            {
                "uid",
                "target_context_uid",
                "description",
                "minimum_accepted_cases",
                "blocked_reason",
            },
            "grounding target requirement",
        )
        minimum = _integer(
            data["minimum_accepted_cases"],
            "grounding target minimum",
        )
        if minimum < 1:
            raise GroundError("Invalid grounding target minimum.")
        return cls(
            uid=_uuid(data["uid"], "grounding target requirement uid"),
            target_context_uid=_uuid(
                data["target_context_uid"],
                "grounding target Context uid",
            ),
            description=_string(
                data["description"],
                "grounding target description",
                empty=True,
            ),
            minimum_accepted_cases=minimum,
            blocked_reason=_string(
                data["blocked_reason"],
                "grounding target blocked reason",
                empty=True,
            ),
        )


@dataclass(frozen=True)
class GroundSourceRef:
    """Content-addressed link from a Ground Memory to one Context Memory."""

    context_uid: str
    memory_uid: str
    content_digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            "context_uid": self.context_uid,
            "memory_uid": self.memory_uid,
            "content_digest": self.content_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundSourceRef":
        data = _exact_dict(
            value,
            {"context_uid", "memory_uid", "content_digest"},
            "grounding source reference",
        )
        return cls(
            context_uid=_uuid(
                data["context_uid"],
                "grounding source Context uid",
            ),
            memory_uid=_uuid(
                data["memory_uid"],
                "grounding source Memory uid",
            ),
            content_digest=_digest(
                data["content_digest"],
                "grounding source content digest",
            ),
        )


@dataclass(frozen=True)
class GroundReference:
    """One explicitly attributed methodological reading."""

    uid: str
    title: str
    url: str
    provenance: str
    reading_status: str
    note: str

    def to_dict(self) -> dict[str, str]:
        return {
            "uid": self.uid,
            "title": self.title,
            "url": self.url,
            "provenance": self.provenance,
            "reading_status": self.reading_status,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundReference":
        data = _exact_dict(
            value,
            {
                "uid",
                "title",
                "url",
                "provenance",
                "reading_status",
                "note",
            },
            "grounding reference",
        )
        url = _string(data["url"], "grounding reference URL", limit=2_000)
        if not url.startswith("https://"):
            raise GroundError("Invalid grounding reference URL.")
        provenance = _string(
            data["provenance"],
            "grounding reference provenance",
            limit=100,
        )
        if provenance != "AGENT_SUGGESTED_EXTERNAL_PRECEDENT":
            raise GroundError("Invalid grounding reference provenance.")
        reading_status = _string(
            data["reading_status"],
            "grounding reference status",
            limit=20,
        )
        if reading_status not in _READING_STATUSES:
            raise GroundError("Invalid grounding reference status.")
        return cls(
            uid=_string(data["uid"], "grounding reference uid", limit=100),
            title=_string(
                data["title"],
                "grounding reference title",
                limit=500,
            ),
            url=url,
            provenance=provenance,
            reading_status=reading_status,
            note=_string(
                data["note"],
                "grounding reference note",
                limit=2_000,
            ),
        )


METHOD_REFERENCES = (
    GroundReference(
        uid="interactive-machine-teaching-ramos-2020",
        title=(
            "Interactive machine teaching: a human-centered approach to "
            "building machine-learned models"
        ),
        url=(
            "https://www.microsoft.com/en-us/research/publication/"
            "interactive-machine-teaching-a-human-centered-approach-to-"
            "building-machine-learned-models/"
        ),
        provenance="AGENT_SUGGESTED_EXTERNAL_PRECEDENT",
        reading_status="UNREAD",
        note=(
            "Saved for later reading as an external precedent for iterative "
            "human-guided construction of inspectable task behavior. It is "
            "not an adopted dependency or a claim that grounding is model "
            "training."
        ),
    ),
    GroundReference(
        uid="ripple-down-rules-richards-2009",
        title="Two decades of Ripple Down Rules research",
        url="https://doi.org/10.1017/S0269888909000241",
        provenance="AGENT_SUGGESTED_EXTERNAL_PRECEDENT",
        reading_status="UNREAD",
        note=(
            "Saved for later reading as an external precedent for refining "
            "rules from concrete cases while preserving previously accepted "
            "case judgments. Memcommit does not adopt the RDR tree format."
        ),
    ),
)


@dataclass(frozen=True)
class GroundItem:
    """One Rule, traceable Ground Memory, issue, or review decision."""

    uid: str
    kind: GroundItemKind
    content: str
    expected: str
    rationale: str
    status: GroundItemStatus
    origin: GroundOrigin
    iteration: int
    related_uids: tuple[str, ...]
    source_refs: tuple[GroundSourceRef, ...] = ()
    target_context_uids: tuple[str, ...] = ()
    case_role: str = ""
    disposition: str = ""
    rule_provenance: str = ""
    proposition: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "kind": self.kind,
            "content": self.content,
            "expected": self.expected,
            "rationale": self.rationale,
            "status": self.status,
            "origin": self.origin,
            "iteration": self.iteration,
            "related_uids": list(self.related_uids),
            "source_refs": [source_ref.to_dict() for source_ref in self.source_refs],
            "target_context_uids": list(self.target_context_uids),
            "case_role": self.case_role,
            "disposition": self.disposition,
            "rule_provenance": self.rule_provenance,
        }

    def to_v3_dict(self) -> dict[str, object]:
        """Serialize the proposition-authoritative Ground item shape."""

        return {**self.to_dict(), "proposition": self.proposition}

    def to_v1_dict(self) -> dict[str, object]:
        """Serialize the exact legacy empty-scaffold item shape."""
        return {
            "uid": self.uid,
            "kind": self.kind,
            "content": self.content,
            "expected": self.expected,
            "rationale": self.rationale,
            "status": self.status,
            "origin": self.origin,
            "iteration": self.iteration,
            "related_uids": list(self.related_uids),
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
        *,
        schema_version: int = GROUND_SCHEMA_VERSION,
    ) -> "GroundItem":
        if schema_version == GROUND_LEGACY_SCHEMA_VERSION:
            return cls._from_v1_dict(value)
        keys = {
            "uid",
            "kind",
            "content",
            "expected",
            "rationale",
            "status",
            "origin",
            "iteration",
            "related_uids",
            "source_refs",
            "target_context_uids",
            "case_role",
            "disposition",
            "rule_provenance",
        }
        if schema_version == GROUND_PROPOSITION_SCHEMA_VERSION:
            keys.add("proposition")
        elif schema_version != GROUND_SCHEMA_VERSION:
            raise GroundError("Unsupported grounding item schema version.")
        data = _exact_dict(
            value,
            keys,
            "grounding item",
        )
        kind = _string(data["kind"], "grounding item kind", limit=20)
        status = _string(data["status"], "grounding item status", limit=20)
        origin = _string(data["origin"], "grounding item origin", limit=20)
        related_uids = data["related_uids"]
        source_refs = data["source_refs"]
        target_context_uids = data["target_context_uids"]
        case_role = _string(
            data["case_role"],
            "Ground Memory role",
            empty=True,
            limit=30,
        )
        # Version-2 prototype sessions briefly called an ordinary fitting
        # example REPRESENTATIVE. Preserve those local sessions while exposing
        # the clearer Goal → Rules → FIT/BOUNDARY/CONTRAST vocabulary.
        case_role = _LEGACY_CASE_ROLE.get(case_role, case_role)
        disposition = _string(
            data["disposition"],
            "Ground Memory disposition",
            empty=True,
            limit=30,
        )
        rule_provenance = _string(
            data["rule_provenance"],
            "grounding rule provenance",
            empty=True,
            limit=40,
        )
        if (
            kind not in _ITEM_KINDS
            or status not in _ITEM_STATUSES
            or origin not in _ORIGINS
            or not isinstance(related_uids, list)
            or any(not isinstance(item, str) or not item for item in related_uids)
            or len(set(related_uids)) != len(related_uids)
            or not isinstance(source_refs, list)
            or not isinstance(target_context_uids, list)
            or any(
                not isinstance(item, str) or not item for item in target_context_uids
            )
            or len(set(target_context_uids)) != len(target_context_uids)
        ):
            raise GroundError("Invalid grounding item.")
        parsed = cls(
            uid=_uuid(data["uid"], "grounding item uid"),
            kind=kind,
            content=_string(data["content"], "grounding item content"),
            expected=_string(
                data["expected"],
                "grounding item expected result",
                empty=True,
            ),
            rationale=_string(
                data["rationale"],
                "grounding item rationale",
                empty=True,
            ),
            status=status,
            origin=origin,
            iteration=_integer(
                data["iteration"],
                "grounding item iteration",
            ),
            related_uids=tuple(related_uids),
            source_refs=tuple(
                GroundSourceRef.from_dict(source_ref) for source_ref in source_refs
            ),
            target_context_uids=tuple(
                _uuid(uid, "grounding item target Context uid")
                for uid in target_context_uids
            ),
            case_role=case_role,
            disposition=disposition,
            rule_provenance=rule_provenance,
            proposition=(
                _string(
                    data["proposition"],
                    "grounding Example proposition",
                    empty=True,
                )
                if schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                else ""
            ),
        )
        parsed._validate_kind_shape(schema_version=schema_version)
        return parsed

    @classmethod
    def _from_v1_dict(cls, value: object) -> "GroundItem":
        data = _exact_dict(
            value,
            {
                "uid",
                "kind",
                "content",
                "expected",
                "rationale",
                "status",
                "origin",
                "iteration",
                "related_uids",
            },
            "grounding item",
        )
        kind = _string(data["kind"], "grounding item kind", limit=20)
        status = _string(data["status"], "grounding item status", limit=20)
        origin = _string(data["origin"], "grounding item origin", limit=20)
        related_uids = data["related_uids"]
        if (
            kind not in _ITEM_KINDS
            or status not in _ITEM_STATUSES
            or origin not in _ORIGINS
            or not isinstance(related_uids, list)
            or any(not isinstance(item, str) or not item for item in related_uids)
            or len(set(related_uids)) != len(related_uids)
        ):
            raise GroundError("Invalid grounding item.")
        return cls(
            uid=_uuid(data["uid"], "grounding item uid"),
            kind=kind,
            content=_string(data["content"], "grounding item content"),
            expected=_string(
                data["expected"],
                "grounding item expected result",
                empty=True,
            ),
            rationale=_string(
                data["rationale"],
                "grounding item rationale",
                empty=True,
            ),
            status=status,
            origin=origin,
            iteration=_integer(
                data["iteration"],
                "grounding item iteration",
            ),
            related_uids=tuple(related_uids),
        )

    def _validate_kind_shape(self, *, schema_version: int) -> None:
        allowed_statuses = {
            "RULE": {"PROPOSED", "ACCEPTED", "REJECTED", "DEFERRED"},
            "CASE": {"PROPOSED", "ACCEPTED", "REJECTED", "DEFERRED"},
            "ISSUE": {"PROPOSED", "DEFERRED", "RESOLVED"},
            "DECISION": {"RESOLVED"},
        }
        if self.status not in allowed_statuses[self.kind]:
            raise GroundError("Invalid grounding item kind/status combination.")
        if self.kind == "RULE":
            if (
                self.source_refs
                or self.case_role
                or self.disposition
                or self.expected
                or self.proposition
                or self.rule_provenance not in _RULE_PROVENANCE
            ):
                raise GroundError("Invalid grounding rule shape.")
        elif self.kind == "CASE":
            common_invalid = (
                self.case_role not in _CASE_ROLES
                or self.disposition not in _DISPOSITIONS
                or self.rule_provenance
            )
            legacy_invalid = schema_version == GROUND_SCHEMA_VERSION and (
                len(self.source_refs) != 1
                or not self.target_context_uids
                or self.proposition
                or (self.disposition == "INCLUDE" and not self.expected.strip())
            )
            proposition_invalid = (
                schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                and not self.proposition.strip()
            )
            if common_invalid or legacy_invalid or proposition_invalid:
                raise GroundError("Invalid Ground Memory shape.")
        elif self.kind == "DECISION":
            if (
                (not self.related_uids and self.content != "REFINE GOAL")
                or self.source_refs
                or self.target_context_uids
                or self.case_role
                or self.disposition
                or self.rule_provenance
                or self.proposition
            ):
                raise GroundError("Invalid grounding decision shape.")
        elif (
            self.source_refs
            or self.target_context_uids
            or self.case_role
            or self.disposition
            or self.rule_provenance
            or self.proposition
        ):
            raise GroundError("Invalid grounding issue shape.")


@dataclass(frozen=True)
class GroundSession:
    """One resumable, operation-independent common Ground."""

    uid: str
    contract_name: str
    goal: str
    # Version 1/2 records require this serialized key and include it in their
    # CAS digest. New behavior neither displays nor reasons over it; removing
    # it awaits a schema migration that can preserve old record identity.
    completion_criterion: str
    scope: tuple[str, ...]
    status: GroundStatus
    revision: int
    items: tuple[GroundItem, ...]
    references: tuple[GroundReference, ...]
    schema_version: int = GROUND_LEGACY_SCHEMA_VERSION
    brief: GroundBrief | None = None
    frames: tuple[GroundFrame, ...] = ()
    requirements: tuple[GroundTargetRequirement, ...] = ()
    cursor_position: int = 0

    def to_dict(self) -> dict[str, object]:
        if type(self.schema_version) is not int or self.schema_version not in {
            GROUND_LEGACY_SCHEMA_VERSION,
            GROUND_SCHEMA_VERSION,
            GROUND_PROPOSITION_SCHEMA_VERSION,
        }:
            raise GroundError("Unsupported grounding session schema version.")
        if self.schema_version == GROUND_LEGACY_SCHEMA_VERSION:
            return {
                "schema_version": GROUND_LEGACY_SCHEMA_VERSION,
                "uid": self.uid,
                "contract_name": self.contract_name,
                "goal": self.goal,
                "completion_criterion": self.completion_criterion,
                "scope": list(self.scope),
                "status": self.status,
                "revision": self.revision,
                "items": [item.to_v1_dict() for item in self.items],
                "references": [reference.to_dict() for reference in self.references],
            }
        return {
            "schema_version": self.schema_version,
            "uid": self.uid,
            "contract_name": self.contract_name,
            "goal": self.goal,
            "completion_criterion": self.completion_criterion,
            "scope": list(self.scope),
            "status": self.status,
            "revision": self.revision,
            "items": [
                (
                    item.to_v3_dict()
                    if self.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                    else item.to_dict()
                )
                for item in self.items
            ],
            "brief": self.brief.to_dict() if self.brief is not None else None,
            "frames": [frame.to_dict() for frame in self.frames],
            "requirements": [
                requirement.to_dict() for requirement in self.requirements
            ],
            "cursor_position": self.cursor_position,
            "references": [reference.to_dict() for reference in self.references],
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundSession":
        """Restore and validate one persisted Ground session."""

        from .validation import ground_session_from_dict

        return ground_session_from_dict(cls, value)

    @classmethod
    def _from_v1_dict(cls, value: object) -> "GroundSession":
        """Restore the legacy empty-session schema."""

        from .validation import legacy_ground_session_from_dict

        return legacy_ground_session_from_dict(cls, value)

    def items_of_kind(self, kind: GroundItemKind) -> tuple[GroundItem, ...]:
        return tuple(item for item in self.items if item.kind == kind)
