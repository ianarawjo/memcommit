"""Durable common-grounding sessions for Rules and reviewed Ground Memories.

Schema version 1 is the original empty scaffold.  Schema version 2 binds that
scaffold to an immutable task brief and exact Context frames, then permits
small, explicitly reviewed Rule/Memory rounds.  Grounding changes only this
artifact; applying accepted Ground Memories to Contexts remains separate.

The persisted ``CASE`` vocabulary remains a schema-compatibility boundary.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, replace
from typing import Iterable, Literal

from memcommit.core.context import Context, Memory


GROUND_SCHEMA_VERSION = 2
GROUND_PROPOSITION_SCHEMA_VERSION = 3
GROUND_LEGACY_SCHEMA_VERSION = 1
GROUND_TEXT_LIMIT = 20_000
GROUND_GOAL_WORD_LIMIT = 40
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
_CONTRACT_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
_WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}

LEGACY_COMPLETION_MARKER = (
    "Reserved for schema compatibility; Ground agreement is not determined "
    "by a separate completion criterion."
)
# Keep the earlier import name available to code that reads version 1/2 data.
# New CLI and provider contracts do not expose a completion criterion.
DEFAULT_COMPLETION_CRITERION = LEGACY_COMPLETION_MARKER


class GroundError(ValueError):
    """Invalid or unsupported common-grounding state."""


def is_bound_ground_schema(schema_version: int) -> bool:
    """Return whether a Ground has explicit immutable Context frames."""

    return schema_version in {
        GROUND_SCHEMA_VERSION,
        GROUND_PROPOSITION_SCHEMA_VERSION,
    }


def validate_ground_contract_name(value: object) -> str:
    """Return one portable Ground ID that is safe as a local filename."""
    if (
        not isinstance(value, str)
        or _CONTRACT_NAME.fullmatch(value) is None
        or value.endswith(".")
        or value.split(".", 1)[0] in _WINDOWS_RESERVED_NAMES
    ):
        raise GroundError(
            "Ground names must match "
            "[a-z0-9][a-z0-9._-]{0,127} and must not use a reserved "
            "Windows device name."
        )
    return value


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


def validate_ground_goal(
    value: object,
    *,
    empty: bool = False,
    label: str = "grounding goal",
) -> str:
    """Validate one newly authored Goal without rewriting legacy records.

    The word limit is a semantic authoring boundary. Existing version 1/2
    records remain loadable even if an older Goal exceeded it; any new or
    revised Goal must be compact enough to remain an orienting statement.
    """
    goal = _string(value, label, empty=empty)
    if len(goal.split()) > GROUND_GOAL_WORD_LIMIT:
        raise GroundError(
            f"{label.capitalize()} must be "
            f"{GROUND_GOAL_WORD_LIMIT} words or fewer."
        )
    return goal


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


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _digest(value: object, label: str) -> str:
    result = _string(value, label, limit=64)
    if len(result) != 64 or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise GroundError(f"Invalid {label}.")
    return result


def context_frame_digest(ctx: Context) -> str:
    """Fingerprint one complete ordered direct Context record.

    Context and Memory references remain pointers in ``to_dict``.  This means
    a bound frame notices pointer/order changes without reading query-only
    content or recursively copying another Context's Memories.
    """
    return _sha256_json(ctx.to_dict())


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
            "source_refs": [
                source_ref.to_dict() for source_ref in self.source_refs
            ],
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
                not isinstance(item, str) or not item
                for item in target_context_uids
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
                GroundSourceRef.from_dict(source_ref)
                for source_ref in source_refs
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
                (
                    not self.related_uids
                    and self.content != "REFINE GOAL"
                )
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
                "references": [
                    reference.to_dict() for reference in self.references
                ],
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
                requirement.to_dict()
                for requirement in self.requirements
            ],
            "cursor_position": self.cursor_position,
            "references": [
                reference.to_dict() for reference in self.references
            ],
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundSession":
        if not isinstance(value, dict):
            raise GroundError("Invalid grounding session.")
        schema_version = value.get("schema_version")
        if type(schema_version) is not int:
            raise GroundError("Unsupported grounding session schema version.")
        if schema_version == GROUND_LEGACY_SCHEMA_VERSION:
            return cls._from_v1_dict(value)
        if schema_version not in {
            GROUND_SCHEMA_VERSION,
            GROUND_PROPOSITION_SCHEMA_VERSION,
        }:
            raise GroundError("Unsupported grounding session schema version.")

        data = _exact_dict(
            value,
            {
                "schema_version",
                "uid",
                "contract_name",
                "goal",
                "completion_criterion",
                "scope",
                "status",
                "revision",
                "items",
                "brief",
                "frames",
                "requirements",
                "cursor_position",
                "references",
            },
            "grounding session",
        )
        status = _string(
            data["status"],
            "grounding session status",
            limit=20,
        )
        scope = data["scope"]
        items = data["items"]
        frames = data["frames"]
        requirements = data["requirements"]
        references = data["references"]
        if (
            status not in _GROUND_STATUSES
            or not isinstance(scope, list)
            or len(scope) > 100
            or any(
                not isinstance(item, str)
                or not item.strip()
                or len(item) > 500
                for item in scope
            )
            or len(set(scope)) != len(scope)
            or not isinstance(items, list)
            or not isinstance(frames, list)
            or not isinstance(requirements, list)
            or not isinstance(references, list)
        ):
            raise GroundError("Invalid grounding session.")
        parsed_items = tuple(
            GroundItem.from_dict(
                item,
                schema_version=schema_version,
            )
            for item in items
        )
        parsed_frames = tuple(
            GroundFrame.from_dict(frame) for frame in frames
        )
        parsed_requirements = tuple(
            GroundTargetRequirement.from_dict(requirement)
            for requirement in requirements
        )
        parsed_references = tuple(
            GroundReference.from_dict(reference)
            for reference in references
        )
        item_uids = {item.uid for item in parsed_items}
        requirement_uids = {
            requirement.uid for requirement in parsed_requirements
        }
        if len(item_uids) != len(parsed_items):
            raise GroundError("Duplicate grounding item uid.")
        if item_uids & requirement_uids:
            raise GroundError("Grounding item and requirement uids overlap.")
        if any(
            related_uid not in item_uids | requirement_uids
            for item in parsed_items
            for related_uid in item.related_uids
        ):
            raise GroundError(
                "Grounding item references an unknown item or requirement."
            )
        item_by_uid = {item.uid: item for item in parsed_items}
        for item in parsed_items:
            if item.kind == "RULE" and any(
                related_uid not in item_by_uid
                or item_by_uid[related_uid].kind != "CASE"
                for related_uid in item.related_uids
            ):
                raise GroundError(
                    "Grounding Rules may relate only to Ground Memories."
                )
            if item.kind == "CASE":
                valid_rule_links = all(
                    related_uid in item_by_uid
                    and item_by_uid[related_uid].kind == "RULE"
                    and item.uid in item_by_uid[related_uid].related_uids
                    for related_uid in item.related_uids
                )
                required_legacy_link = (
                    schema_version != GROUND_SCHEMA_VERSION
                    or len(item.related_uids) == 1
                )
                if not valid_rule_links or not required_legacy_link:
                    raise GroundError(
                        "Ground Memory Rule links must be valid and reciprocal."
                    )
            if item.kind == "RULE" and any(
                related_uid not in item_by_uid
                or item.uid not in item_by_uid[related_uid].related_uids
                for related_uid in item.related_uids
            ):
                raise GroundError(
                    "Grounding Rule/Memory links must be reciprocal."
                )
            if item.kind == "DECISION" and item.status != "RESOLVED":
                raise GroundError("Grounding decisions must be resolved.")
        for item in parsed_items:
            if item.kind in {"RULE", "CASE"} and item.status == "ACCEPTED":
                if item.origin != "JOINT" or not any(
                    decision.kind == "DECISION"
                    and decision.status == "RESOLVED"
                    and decision.content == f"ACCEPT {item.kind}"
                    and decision.origin == "USER"
                    and decision.related_uids == (item.uid,)
                    and decision.iteration == item.iteration
                    for decision in parsed_items
                ):
                    raise GroundError(
                        "An accepted grounding item requires its recorded "
                        "approval decision."
                    )
        frame_uids = {frame.context_uid for frame in parsed_frames}
        frame_names = {frame.context_name for frame in parsed_frames}
        if (
            len(frame_uids) != len(parsed_frames)
            or len(frame_names) != len(parsed_frames)
            or sum(
                frame.role == "RAW_EVIDENCE"
                for frame in parsed_frames
            )
            != 1
            or sum(
                frame.role == "WORKING_CANDIDATES"
                for frame in parsed_frames
            )
            != 1
            or not any(
                frame.role in _TARGET_FRAME_ROLES
                for frame in parsed_frames
            )
        ):
            raise GroundError("Invalid grounding frame registry.")
        target_uids = {
            frame.context_uid
            for frame in parsed_frames
            if frame.role in _TARGET_FRAME_ROLES
        }
        requirement_targets = {
            requirement.target_context_uid
            for requirement in parsed_requirements
        }
        if (
            len(requirement_uids) != len(parsed_requirements)
            or len(requirement_targets) != len(parsed_requirements)
            or requirement_targets != target_uids
        ):
            raise GroundError("Invalid grounding target requirements.")
        working_candidate_uids = {
            frame.context_uid
            for frame in parsed_frames
            if frame.role == "WORKING_CANDIDATES"
        }
        for item in parsed_items:
            if any(
                source_ref.context_uid not in working_candidate_uids
                for source_ref in item.source_refs
            ):
                raise GroundError(
                    "Ground Memories must reference the bound "
                    "working-candidate Context."
                )
            if any(
                target_uid not in target_uids
                for target_uid in item.target_context_uids
            ):
                raise GroundError(
                    "Ground Memory references an unbound target Context."
                )
        if (
            len({reference.uid for reference in parsed_references})
            != len(parsed_references)
        ):
            raise GroundError("Duplicate grounding reference uid.")
        revision = _integer(data["revision"], "grounding session revision")
        if (
            any(item.iteration < 1 for item in parsed_items)
            or (revision == 0) != (not parsed_items)
            or (
                parsed_items
                and max(item.iteration for item in parsed_items) != revision
            )
        ):
            raise GroundError(
                "Grounding item iterations do not match the session revision."
            )
        if status != "OPEN":
            raise GroundError(
                "Bound Ground schemas support only an OPEN workbench."
            )
        if parsed_references != METHOD_REFERENCES:
            raise GroundError(
                "Bound Ground schema has invalid method references."
            )
        brief = GroundBrief.from_dict(data["brief"])
        cursor_position = _integer(
            data["cursor_position"],
            "grounding cursor position",
        )
        candidate_frame = next(
            frame
            for frame in parsed_frames
            if frame.role == "WORKING_CANDIDATES"
        )
        if (
            candidate_frame.direct_memory_count == 0
            and cursor_position != 0
        ) or (
            candidate_frame.direct_memory_count > 0
            and cursor_position >= candidate_frame.direct_memory_count
        ):
            raise GroundError("Invalid grounding cursor position.")
        return cls(
            uid=_uuid(data["uid"], "grounding session uid"),
            contract_name=validate_ground_contract_name(
                data["contract_name"],
            ),
            goal=_string(
                data["goal"],
                "grounding goal",
                empty=True,
            ),
            completion_criterion=_string(
                data["completion_criterion"],
                "grounding completion criterion",
            ),
            scope=tuple(scope),
            status=status,
            revision=revision,
            items=parsed_items,
            references=parsed_references,
            schema_version=schema_version,
            brief=brief,
            frames=parsed_frames,
            requirements=parsed_requirements,
            cursor_position=cursor_position,
        )

    @classmethod
    def _from_v1_dict(cls, value: object) -> "GroundSession":
        data = _exact_dict(
            value,
            {
                "schema_version",
                "uid",
                "contract_name",
                "goal",
                "completion_criterion",
                "scope",
                "status",
                "revision",
                "items",
                "references",
            },
            "grounding session",
        )
        status = _string(
            data["status"],
            "grounding session status",
            limit=20,
        )
        scope = data["scope"]
        items = data["items"]
        references = data["references"]
        if (
            status not in _GROUND_STATUSES
            or not isinstance(scope, list)
            or len(scope) > 100
            or any(
                not isinstance(item, str)
                or not item.strip()
                or len(item) > 500
                for item in scope
            )
            or len(set(scope)) != len(scope)
            or not isinstance(items, list)
            or not isinstance(references, list)
        ):
            raise GroundError("Invalid grounding session.")
        parsed_items = tuple(
            GroundItem.from_dict(
                item,
                schema_version=GROUND_LEGACY_SCHEMA_VERSION,
            )
            for item in items
        )
        parsed_references = tuple(
            GroundReference.from_dict(reference)
            for reference in references
        )
        item_uids = {item.uid for item in parsed_items}
        if len(item_uids) != len(parsed_items):
            raise GroundError("Duplicate grounding item uid.")
        if any(
            related_uid not in item_uids
            for item in parsed_items
            for related_uid in item.related_uids
        ):
            raise GroundError("Grounding item references an unknown item.")
        revision = _integer(data["revision"], "grounding session revision")
        if any(item.iteration > revision for item in parsed_items):
            raise GroundError("Grounding item exceeds the session revision.")
        # Version 1 deliberately remains empty-only. It can be upgraded only
        # through the explicit frame-binding action.
        if status != "OPEN" or revision != 0 or parsed_items:
            raise GroundError(
                "Grounding schema version 1 supports only an empty OPEN "
                "session."
            )
        if parsed_references != METHOD_REFERENCES:
            raise GroundError(
                "Grounding schema version 1 has invalid method references."
            )
        return cls(
            uid=_uuid(data["uid"], "grounding session uid"),
            contract_name=validate_ground_contract_name(
                data["contract_name"],
            ),
            goal=_string(
                data["goal"],
                "grounding goal",
                empty=True,
            ),
            completion_criterion=_string(
                data["completion_criterion"],
                "grounding completion criterion",
            ),
            scope=tuple(scope),
            status=status,
            revision=revision,
            items=parsed_items,
            references=parsed_references,
            schema_version=GROUND_LEGACY_SCHEMA_VERSION,
        )

    def items_of_kind(self, kind: GroundItemKind) -> tuple[GroundItem, ...]:
        return tuple(item for item in self.items if item.kind == kind)


def create_ground_session(
    contract_name: str,
    *,
    goal: str = "",
    completion_criterion: str = LEGACY_COMPLETION_MARKER,
    scope: tuple[str, ...] = (),
) -> GroundSession:
    """Create a validated scaffold without inferring Rules or Memories."""
    goal = validate_ground_goal(goal, empty=True)
    session = GroundSession(
        uid=str(uuid.uuid4()),
        contract_name=validate_ground_contract_name(contract_name),
        goal=goal,
        completion_criterion=completion_criterion,
        scope=scope,
        status="OPEN",
        revision=0,
        items=(),
        references=METHOD_REFERENCES,
        schema_version=GROUND_LEGACY_SCHEMA_VERSION,
    )
    return GroundSession.from_dict(session.to_dict())


def _frame(role: GroundFrameRole, ctx: Context) -> GroundFrame:
    direct_items = tuple(ctx.iter_items())
    return GroundFrame(
        role=role,
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=context_frame_digest(ctx),
        direct_memory_count=sum(
            isinstance(item, Memory) for item in direct_items
        ),
        direct_item_count=len(direct_items),
    )


def bind_ground_workbench(
    session: GroundSession,
    *,
    description: str,
    raw_context: Context,
    derived_context: Context,
    target_contexts: tuple[Context, ...],
    target_requirements: tuple[GroundTargetSpec, ...],
) -> GroundSession:
    """Upgrade an empty scaffold into an exact, non-mutating workbench."""
    if (
        session.schema_version != GROUND_LEGACY_SCHEMA_VERSION
        or session.status != "OPEN"
        or session.revision != 0
        or session.items
    ):
        raise GroundError(
            "Only an empty schema version 1 grounding session can be bound."
        )
    description = _string(
        description,
        "grounding Task description",
    )
    if not target_contexts or len(target_contexts) != len(target_requirements):
        raise GroundError(
            "Every grounding target requires exactly one target specification."
        )
    target_by_name = {context.name: context for context in target_contexts}
    if len(target_by_name) != len(target_contexts):
        raise GroundError("Grounding target Contexts must be unique.")
    spec_by_name = {
        spec.context_name: spec for spec in target_requirements
    }
    if (
        len(spec_by_name) != len(target_requirements)
        or set(spec_by_name) != set(target_by_name)
    ):
        raise GroundError(
            "Grounding target specifications do not match target Contexts."
        )
    all_contexts = (raw_context, derived_context, *target_contexts)
    if (
        len({context.uid for context in all_contexts}) != len(all_contexts)
        or len({context.name for context in all_contexts}) != len(all_contexts)
    ):
        raise GroundError("Grounding workbench Contexts must be independent.")

    frames = [
        _frame("RAW_EVIDENCE", raw_context),
        _frame("WORKING_CANDIDATES", derived_context),
    ]
    requirements: list[GroundTargetRequirement] = []
    for context in target_contexts:
        spec = spec_by_name[context.name]
        if spec.role not in _TARGET_FRAME_ROLES:
            raise GroundError("Invalid grounding target role.")
        minimum = _integer(
            spec.minimum_accepted_cases,
            "grounding target minimum",
        )
        if minimum < 1:
            raise GroundError("Invalid grounding target minimum.")
        frames.append(_frame(spec.role, context))
        requirements.append(
            GroundTargetRequirement(
                uid=str(uuid.uuid4()),
                target_context_uid=context.uid,
                description=_string(
                    spec.description,
                    "grounding target description",
                    empty=True,
                ),
                minimum_accepted_cases=minimum,
                blocked_reason=_string(
                    spec.blocked_reason,
                    "grounding target blocked reason",
                    empty=True,
                ),
            )
        )

    bound = replace(
        session,
        schema_version=GROUND_SCHEMA_VERSION,
        brief=GroundBrief(
            content=description,
            provenance="USER_PROVIDED_TASK_DESCRIPTION",
            digest=_sha256_text(description),
        ),
        frames=tuple(frames),
        requirements=tuple(requirements),
        cursor_position=0,
    )
    return GroundSession.from_dict(bound.to_dict())


def _contexts_by_uid(
    contexts: Iterable[Context],
) -> dict[str, Context]:
    result: dict[str, Context] = {}
    for context in contexts:
        if context.uid in result:
            raise GroundError("Duplicate current grounding Context uid.")
        result[context.uid] = context
    return result


def upgrade_ground_to_propositions(session: GroundSession) -> GroundSession:
    """Explicitly migrate one bound v2 Ground to proposition-authoritative v3.

    The migration preserves every durable identity, semantic iteration, link,
    source reference, target, and exact-output projection.  It changes the
    record digest, so all earlier Fit receipts become stale even though no
    semantic revision is invented merely for a storage-shape transition.
    """

    if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION:
        return GroundSession.from_dict(session.to_dict())
    if session.schema_version != GROUND_SCHEMA_VERSION:
        raise GroundError("Only a bound version-2 Ground can be upgraded.")
    migrated_items = tuple(
        (
            replace(
                item,
                proposition=(
                    f"{item.content} -> {item.expected}"
                    if item.expected
                    else item.content
                ),
            )
            if item.kind == "CASE"
            else item
        )
        for item in session.items
    )
    upgraded = replace(
        session,
        schema_version=GROUND_PROPOSITION_SCHEMA_VERSION,
        items=migrated_items,
    )
    return GroundSession.from_dict(upgraded.to_dict())


def stale_ground_frames(
    session: GroundSession,
    contexts: Iterable[Context],
) -> tuple[str, ...]:
    """Return bound frame names that no longer match their exact Context."""
    if not is_bound_ground_schema(session.schema_version):
        return ()
    current = _contexts_by_uid(contexts)
    stale: set[str] = set()
    for frame in session.frames:
        context = current.get(frame.context_uid)
        if context is None or _frame(frame.role, context) != frame:
            stale.add(frame.context_name)

    frame_name_by_uid = {
        frame.context_uid: frame.context_name for frame in session.frames
    }
    for item in session.items:
        for source_ref in item.source_refs:
            context = current.get(source_ref.context_uid)
            memory = (
                next(
                    (
                        candidate
                        for candidate in context.iter_items()
                        if isinstance(candidate, Memory)
                        and candidate.uid == source_ref.memory_uid
                    ),
                    None,
                )
                if context is not None
                else None
            )
            if (
                memory is None
                or _sha256_text(memory.content) != source_ref.content_digest
                or (
                    session.schema_version == GROUND_SCHEMA_VERSION
                    and item.kind == "CASE"
                    and item.content != memory.content
                )
            ):
                stale.add(
                    frame_name_by_uid.get(
                        source_ref.context_uid,
                        source_ref.context_uid,
                    )
                )
    return tuple(
        frame.context_name
        for frame in session.frames
        if frame.context_name in stale
    )


def ground_matches_workbench(
    session: GroundSession,
    contexts: Iterable[Context],
) -> bool:
    """Return whether all bound frames still match their recorded bytes."""
    return (
        is_bound_ground_schema(session.schema_version)
        and not stale_ground_frames(session, contexts)
    )


def _find_memory(ctx: Context, selector: str) -> Memory:
    selector = _string(
        selector,
        "grounding candidate selector",
        limit=100,
    )
    memories = [
        item for item in ctx.iter_items() if isinstance(item, Memory)
    ]
    matches = [memory for memory in memories if memory.uid.startswith(selector)]
    if not matches:
        raise GroundError(
            f"No bound candidate Memory starts with '{selector}'."
        )
    if len(matches) > 1:
        raise GroundError(
            f"Candidate prefix '{selector}' is ambiguous."
        )
    return matches[0]


def _find_rule(session: GroundSession, selector: str) -> GroundItem:
    selector = _string(selector, "grounding rule selector", limit=100)
    matches = [
        item
        for item in session.items
        if item.kind == "RULE" and item.uid.startswith(selector)
    ]
    if not matches:
        raise GroundError(f"No grounding rule starts with '{selector}'.")
    if len(matches) > 1:
        raise GroundError(f"Grounding rule prefix '{selector}' is ambiguous.")
    return matches[0]


def _proposal_contexts(
    session: GroundSession,
    current_contexts: Iterable[Context],
) -> tuple[Context, ...]:
    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one."
        )
    if session.status != "OPEN":
        raise GroundError("Grounding workbench is not open.")
    return contexts


def propose_ground_rule(
    session: GroundSession,
    *,
    rule: str,
    rationale: str,
    current_contexts: Iterable[Context],
    rule_provenance: GroundRuleProvenance = "DISTILLED",
    target_context_names: tuple[str, ...] = (),
) -> GroundSession:
    """Propose one reusable Rule without manufacturing a Ground Memory."""
    _proposal_contexts(session, current_contexts)
    rule = _string(rule, "grounding proposed rule")
    if (
        rule_provenance not in _RULE_PROVENANCE
        or rule_provenance == "JOINTLY_REVISED"
    ):
        raise GroundError(
            "A new rule must be USER_STATED or DISTILLED; legacy "
            "DISTILLED_FROM_GOAL and INDUCED_FROM_CASES remain readable; "
            "JOINTLY_REVISED is created by review."
        )
    # A directly stated Rule may be complete in the person's own wording.
    # Derived Rules still need an explicit inference rationale so provenance
    # cannot silently turn a user statement into model-authored reasoning.
    rationale = _string(
        rationale,
        "grounding proposal rationale",
        empty=rule_provenance == "USER_STATED",
    )
    target_frame_by_name = {
        frame.context_name: frame
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    if not target_context_names:
        target_context_names = tuple(
            frame.context_name
            for frame in session.frames
            if frame.role == "PUBLICATION_TARGET"
        )
    if (
        not target_context_names
        or len(set(target_context_names)) != len(target_context_names)
        or any(name not in target_frame_by_name for name in target_context_names)
    ):
        raise GroundError("Grounding Rule names an invalid target Context.")
    iteration = session.revision + 1
    proposed_rule = GroundItem(
        uid=str(uuid.uuid4()),
        kind="RULE",
        content=rule,
        expected="",
        rationale=rationale,
        status="PROPOSED",
        origin=("USER" if rule_provenance == "USER_STATED" else "AGENT"),
        iteration=iteration,
        related_uids=(),
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid
            for name in target_context_names
        ),
        rule_provenance=rule_provenance,
    )
    result = replace(
        session,
        revision=iteration,
        items=(*session.items, proposed_rule),
    )
    return GroundSession.from_dict(result.to_dict())


def propose_ground_case(
    session: GroundSession,
    *,
    rule_selector: str,
    case: str,
    source_context_uid: str,
    source_memory_uid: str,
    target_context_names: tuple[str, ...],
    expected: str,
    rationale: str,
    current_contexts: Iterable[Context],
    case_role: GroundCaseRole = "FIT",
    disposition: GroundDisposition = "INCLUDE",
) -> GroundSession:
    """Attach one traceable fit, boundary, or contrast Memory to a Rule."""
    contexts = _proposal_contexts(session, current_contexts)
    rule = _find_rule(session, rule_selector)
    if rule.status in {"REJECTED", "DEFERRED"}:
        raise GroundError(
            "A Ground Memory cannot attach to a rejected or deferred Rule."
        )
    case = _string(case, "proposed Ground Memory")
    rationale = _string(rationale, "grounding proposal rationale")
    expected = _string(
        expected,
        "grounding proposed expected result",
        empty=disposition != "INCLUDE",
    )
    if case_role not in _CASE_ROLES or disposition not in _DISPOSITIONS:
        raise GroundError("Invalid Ground Memory classification.")

    source_frame = next(
        (
            frame
            for frame in session.frames
            if frame.context_uid == source_context_uid
            and frame.role == "WORKING_CANDIDATES"
        ),
        None,
    )
    contexts_by_uid = _contexts_by_uid(contexts)
    if source_frame is None or source_context_uid not in contexts_by_uid:
        raise GroundError(
            "Ground Memories must use the bound working-candidate Context."
        )
    memory = _find_memory(
        contexts_by_uid[source_context_uid],
        source_memory_uid,
    )
    if case != memory.content:
        raise GroundError(
            "Ground Memory content must exactly match its bound source "
            "Context Memory; put rewritten output in expected."
        )

    target_frame_by_name = {
        frame.context_name: frame
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    if (
        not target_context_names
        or len(set(target_context_names)) != len(target_context_names)
        or any(name not in target_frame_by_name for name in target_context_names)
    ):
        raise GroundError("Grounding proposal names an invalid target Context.")

    iteration = session.revision + 1
    case_uid = str(uuid.uuid4())
    proposed_case = GroundItem(
        uid=case_uid,
        kind="CASE",
        content=case,
        expected=expected,
        rationale=rationale,
        status="PROPOSED",
        origin="AGENT",
        iteration=iteration,
        related_uids=(rule.uid,),
        source_refs=(
            GroundSourceRef(
                context_uid=source_context_uid,
                memory_uid=memory.uid,
                content_digest=_sha256_text(memory.content),
            ),
        ),
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid
            for name in target_context_names
        ),
        case_role=case_role,
        disposition=disposition,
    )
    linked_rule = replace(
        rule,
        related_uids=(*rule.related_uids, case_uid),
    )
    items = tuple(
        linked_rule if item.uid == rule.uid else item
        for item in session.items
    )
    result = replace(
        session,
        revision=iteration,
        items=(*items, proposed_case),
    )
    return GroundSession.from_dict(result.to_dict())


def propose_ground_example(
    session: GroundSession,
    *,
    proposition: str,
    rationale: str,
    current_contexts: Iterable[Context],
    rule_selectors: tuple[str, ...] = (),
    source_context_uid: str | None = None,
    source_memory_uid: str | None = None,
    target_context_names: tuple[str, ...] = (),
    input_text: str = "",
    expected_output: str = "",
    case_role: GroundCaseRole = "FIT",
    disposition: GroundDisposition = "INCLUDE",
    origin: GroundOrigin = "USER",
) -> GroundSession:
    """Propose one native concrete proposition in a version-3 Ground.

    Evidence, materialization targets, exact-output projection, and Rule links
    are independent optional metadata.  A pre-Rule observation therefore
    remains durable without fabricating a Rule or source Memory.
    """

    contexts = _proposal_contexts(session, current_contexts)
    if session.schema_version != GROUND_PROPOSITION_SCHEMA_VERSION:
        raise GroundError(
            "Native Examples require an explicit proposition-schema upgrade."
        )
    proposition = _string(proposition, "Ground Example proposition")
    rationale = _string(rationale, "Ground Example rationale", empty=True)
    input_text = _string(
        input_text,
        "Ground Example exact input",
        empty=True,
    )
    expected_output = _string(
        expected_output,
        "Ground Example expected output",
        empty=True,
    )
    if bool(input_text) != bool(expected_output):
        raise GroundError(
            "An exact-output Example requires both input and expected output."
        )
    if (
        case_role not in _CASE_ROLES
        or disposition not in _DISPOSITIONS
        or origin not in _ORIGINS
    ):
        raise GroundError("Invalid native Ground Example classification.")
    if len(set(rule_selectors)) != len(rule_selectors):
        raise GroundError("A Ground Example Rule was supplied more than once.")
    rules = tuple(_find_rule(session, selector) for selector in rule_selectors)
    if len({rule.uid for rule in rules}) != len(rules):
        raise GroundError("Ground Example Rule selectors are not unique.")
    if any(rule.status in {"REJECTED", "DEFERRED"} for rule in rules):
        raise GroundError("A Ground Example cannot link an inactive Rule.")

    if (source_context_uid is None) != (source_memory_uid is None):
        raise GroundError(
            "Ground Example source Context and Memory must be supplied together."
        )
    source_refs: tuple[GroundSourceRef, ...] = ()
    if source_context_uid is not None and source_memory_uid is not None:
        source_frame = next(
            (
                frame
                for frame in session.frames
                if frame.context_uid == source_context_uid
                and frame.role == "WORKING_CANDIDATES"
            ),
            None,
        )
        contexts_by_uid = _contexts_by_uid(contexts)
        if source_frame is None or source_context_uid not in contexts_by_uid:
            raise GroundError(
                "Ground Example evidence must use the bound candidate Context."
            )
        memory = _find_memory(
            contexts_by_uid[source_context_uid],
            source_memory_uid,
        )
        source_refs = (
            GroundSourceRef(
                context_uid=source_context_uid,
                memory_uid=memory.uid,
                content_digest=_sha256_text(memory.content),
            ),
        )

    target_frame_by_name = {
        frame.context_name: frame
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    if len(set(target_context_names)) != len(target_context_names) or any(
        name not in target_frame_by_name for name in target_context_names
    ):
        raise GroundError("Ground Example names an invalid target Context.")

    iteration = session.revision + 1
    example_uid = str(uuid.uuid4())
    example = GroundItem(
        uid=example_uid,
        kind="CASE",
        content=input_text or proposition,
        expected=expected_output,
        proposition=proposition,
        rationale=rationale,
        status="PROPOSED",
        origin=origin,
        iteration=iteration,
        related_uids=tuple(rule.uid for rule in rules),
        source_refs=source_refs,
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid
            for name in target_context_names
        ),
        case_role=case_role,
        disposition=disposition,
    )
    rule_uids = {rule.uid for rule in rules}
    linked_items = tuple(
        replace(item, related_uids=(*item.related_uids, example_uid))
        if item.uid in rule_uids
        else item
        for item in session.items
    )
    result = replace(
        session,
        revision=iteration,
        items=(*linked_items, example),
    )
    return GroundSession.from_dict(result.to_dict())


def select_ground_candidate(
    session: GroundSession,
    position: int,
    *,
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Move the durable workbench cursor without changing semantic revision."""
    if not ground_matches_workbench(session, current_contexts):
        raise GroundError("Grounding workbench is stale.")
    if isinstance(position, bool) or not isinstance(position, int):
        raise GroundError("Grounding candidate position must be an integer.")
    candidate_frame = next(
        frame
        for frame in session.frames
        if frame.role == "WORKING_CANDIDATES"
    )
    if position < 0 or position >= candidate_frame.direct_memory_count:
        raise GroundError("Grounding candidate position is out of range.")
    selected = replace(session, cursor_position=position)
    return GroundSession.from_dict(selected.to_dict())


def propose_ground_round(
    session: GroundSession,
    *,
    rule: str,
    case: str,
    source_context_uid: str,
    source_memory_uid: str,
    target_context_names: tuple[str, ...],
    expected: str,
    rationale: str,
    current_contexts: Iterable[Context],
    case_role: GroundCaseRole = "FIT",
    disposition: GroundDisposition = "INCLUDE",
    rule_provenance: GroundRuleProvenance = "DISTILLED",
) -> GroundSession:
    """Record one related Rule/Memory proposal as a single revision."""
    contexts = _proposal_contexts(session, current_contexts)
    rule = _string(rule, "grounding proposed rule")
    case = _string(case, "proposed Ground Memory")
    rationale = _string(rationale, "grounding proposal rationale")
    expected = _string(
        expected,
        "grounding proposed expected result",
        empty=disposition != "INCLUDE",
    )
    if (
        case_role not in _CASE_ROLES
        or disposition not in _DISPOSITIONS
        or rule_provenance not in _RULE_PROVENANCE
        or rule_provenance == "JOINTLY_REVISED"
    ):
        raise GroundError("Invalid Ground Memory classification.")

    source_frame = next(
        (
            frame
            for frame in session.frames
            if frame.context_uid == source_context_uid
            and frame.role == "WORKING_CANDIDATES"
        ),
        None,
    )
    contexts_by_uid = _contexts_by_uid(contexts)
    if source_frame is None or source_context_uid not in contexts_by_uid:
        raise GroundError(
            "Ground Memories must use the bound working-candidate Context."
        )
    memory = _find_memory(
        contexts_by_uid[source_context_uid],
        source_memory_uid,
    )
    if case != memory.content:
        raise GroundError(
            "Ground Memory content must exactly match its bound source "
            "Context Memory; put rewritten output in expected."
        )

    target_frame_by_name = {
        frame.context_name: frame
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    if (
        not target_context_names
        or len(set(target_context_names)) != len(target_context_names)
        or any(name not in target_frame_by_name for name in target_context_names)
    ):
        raise GroundError("Grounding proposal names an invalid target Context.")

    iteration = session.revision + 1
    rule_uid = str(uuid.uuid4())
    case_uid = str(uuid.uuid4())
    proposed_rule = GroundItem(
        uid=rule_uid,
        kind="RULE",
        content=rule,
        expected="",
        rationale=rationale,
        status="PROPOSED",
        origin=("USER" if rule_provenance == "USER_STATED" else "AGENT"),
        iteration=iteration,
        related_uids=(case_uid,),
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid
            for name in target_context_names
        ),
        rule_provenance=rule_provenance,
    )
    proposed_case = GroundItem(
        uid=case_uid,
        kind="CASE",
        content=case,
        expected=expected,
        rationale=rationale,
        status="PROPOSED",
        origin="AGENT",
        iteration=iteration,
        related_uids=(rule_uid,),
        source_refs=(
            GroundSourceRef(
                context_uid=source_context_uid,
                memory_uid=memory.uid,
                content_digest=_sha256_text(memory.content),
            ),
        ),
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid
            for name in target_context_names
        ),
        case_role=case_role,
        disposition=disposition,
    )
    result = replace(
        session,
        revision=iteration,
        items=(*session.items, proposed_rule, proposed_case),
    )
    return GroundSession.from_dict(result.to_dict())


def review_ground_item(
    session: GroundSession,
    item_uid: str,
    *,
    action: str,
    response: str = "",
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Accept, refine, defer, or reject one proposal in one saved revision."""
    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one before deciding."
        )
    action = _string(action, "grounding review action", limit=20).upper()
    if action not in _REVIEW_ACTIONS:
        raise GroundError("Invalid grounding review action.")
    item_uid = _string(item_uid, "grounding decision selector", limit=100)
    candidates = [
        item for item in session.items if item.uid.startswith(item_uid)
    ]
    if len(candidates) != 1:
        raise GroundError("Grounding decision target is missing or ambiguous.")
    target = candidates[0]
    if target.kind not in {"RULE", "CASE"} or (
        target.status != "PROPOSED"
        and not (action == "REFINE" and target.status == "ACCEPTED")
    ):
        raise GroundError(
            "Only a proposed Rule/Ground Memory, or an accepted item being "
            "reopened with REFINE, can be reviewed."
        )
    if action == "REFINE" and not response.strip():
        raise GroundError("REFINE requires replacement text.")

    iteration = session.revision + 1
    replacement = target
    if action == "ACCEPT":
        replacement = replace(
            target,
            status="ACCEPTED",
            origin="JOINT",
            iteration=iteration,
        )
    elif action == "DEFER":
        replacement = replace(target, status="DEFERRED", origin="JOINT")
    elif action == "REJECT":
        replacement = replace(target, status="REJECTED", origin="JOINT")
    elif target.kind == "RULE":
        replacement = replace(
            target,
            content=_string(response, "refined grounding rule"),
            status="PROPOSED",
            origin="JOINT",
            iteration=iteration,
            rule_provenance="JOINTLY_REVISED",
        )
    elif session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION:
        replacement = replace(
            target,
            proposition=_string(response, "refined Ground Example proposition"),
            status="PROPOSED",
            origin="JOINT",
            iteration=iteration,
        )
    else:
        replacement = replace(
            target,
            expected=_string(response, "refined Ground Memory output"),
            status="PROPOSED",
            origin="JOINT",
            iteration=iteration,
        )

    decision = GroundItem(
        uid=str(uuid.uuid4()),
        kind="DECISION",
        content=f"{action} {target.kind}",
        expected=response,
        rationale=(
            response
            if action != "REFINE"
            else (
                "The user refined and reopened the judgment. Previous value: "
                + (
                    target.content
                    if target.kind == "RULE"
                    else (
                        target.proposition
                        if session.schema_version
                        == GROUND_PROPOSITION_SCHEMA_VERSION
                        else target.expected
                    )
                )
            )
        ),
        status="RESOLVED",
        origin="USER",
        iteration=iteration,
        related_uids=(target.uid,),
    )
    items = tuple(
        replacement if item.uid == target.uid else item
        for item in session.items
    )
    reviewed = replace(
        session,
        revision=iteration,
        items=(*items, decision),
    )
    return GroundSession.from_dict(reviewed.to_dict())


def set_ground_example_use(
    session: GroundSession,
    item_uid: str,
    *,
    use: str,
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Set whether one active Example participates in semantic evaluation.

    USE is a durable semantic-input decision, not a presentation preference.
    Keep it on the same revisioned/CAS-protected Ground boundary as review so
    Fit and Ground Distill can freeze one unambiguous Example set.
    """

    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one before changing Example USE."
        )
    use = _string(use, "Ground Example USE", limit=20).upper()
    if use not in {"INCLUDE", "EXCLUDE"}:
        raise GroundError("Ground Example USE must be INCLUDE or EXCLUDE.")
    selector = _string(item_uid, "Ground Example selector", limit=100)
    candidates = [
        item
        for item in session.items
        if item.kind == "CASE" and item.uid.startswith(selector)
    ]
    if len(candidates) != 1:
        raise GroundError("Ground Example USE target is missing or ambiguous.")
    target = candidates[0]
    if target.status not in {"PROPOSED", "ACCEPTED"}:
        raise GroundError(
            "Only a PROPOSED or ACCEPTED Ground Example can change USE."
        )
    if target.disposition == use:
        raise GroundError("Ground Example USE is already set to that value.")

    iteration = session.revision + 1
    replacement = replace(
        target,
        disposition=use,
        origin="JOINT",
        iteration=iteration,
    )
    decision = GroundItem(
        uid=str(uuid.uuid4()),
        kind="DECISION",
        content=f"SET EXAMPLE USE {use}",
        expected=use,
        rationale=(
            "The user explicitly changed whether this Example participates "
            "in Fit and Ground Distill."
        ),
        status="RESOLVED",
        origin="USER",
        iteration=iteration,
        related_uids=(target.uid,),
    )
    result = replace(
        session,
        revision=iteration,
        items=tuple(
            replacement if item.uid == target.uid else item
            for item in session.items
        )
        + (decision,),
    )
    return GroundSession.from_dict(result.to_dict())


def resolve_ground_requirement(
    session: GroundSession,
    requirement_selector: str,
) -> GroundTargetRequirement:
    """Resolve one target requirement by exact Context name or UID prefix."""
    requirement_selector = _string(
        requirement_selector,
        "grounding requirement selector",
        limit=500,
    )
    frame_name_by_uid = {
        frame.context_uid: frame.context_name
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    exact_matches = [
        requirement
        for requirement in session.requirements
        if requirement.target_context_uid in frame_name_by_uid
        and frame_name_by_uid[requirement.target_context_uid]
        == requirement_selector
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise GroundError(
            "Grounding requirement target is missing or ambiguous."
        )
    prefix_matches = [
        requirement
        for requirement in session.requirements
        if requirement.target_context_uid in frame_name_by_uid
        and requirement.uid.startswith(requirement_selector)
    ]
    if len(prefix_matches) != 1:
        raise GroundError(
            "Grounding requirement target is missing or ambiguous."
        )
    return prefix_matches[0]


def revise_ground_requirement(
    session: GroundSession,
    requirement_selector: str,
    *,
    description: str | None = None,
    minimum_accepted_cases: int | None = None,
    blocked_reason: str | None = None,
    reason: str,
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Revise the negotiable Goal layer and record why it changed.

    The copied task brief and evidence frames stay fixed.  Requirements are
    working hypotheses: awkward lower cases may reveal that a category,
    minimum, or blocking assumption should change.  Such changes are explicit
    revisions so accepted cases can be regression-checked against them later.
    """
    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one before revising it."
        )
    current = resolve_ground_requirement(session, requirement_selector)
    if (
        description is None
        and minimum_accepted_cases is None
        and blocked_reason is None
    ):
        raise GroundError("A requirement revision must change a field.")

    revised_description = (
        current.description
        if description is None
        else _string(description, "revised grounding target description")
    )
    revised_minimum = (
        current.minimum_accepted_cases
        if minimum_accepted_cases is None
        else _integer(
            minimum_accepted_cases,
            "revised grounding target minimum",
        )
    )
    if revised_minimum < 1:
        raise GroundError("Invalid revised grounding target minimum.")
    revised_blocked_reason = (
        current.blocked_reason
        if blocked_reason is None
        else _string(
            blocked_reason,
            "revised grounding blocked reason",
            empty=True,
        )
    )
    revised = replace(
        current,
        description=revised_description,
        minimum_accepted_cases=revised_minimum,
        blocked_reason=revised_blocked_reason,
    )
    if revised == current:
        raise GroundError("Grounding requirement revision is a no-op.")

    iteration = session.revision + 1
    decision = GroundItem(
        uid=str(uuid.uuid4()),
        kind="DECISION",
        content="REFINE TARGET REQUIREMENT",
        expected=(
            f"{revised.description} | minimum="
            f"{revised.minimum_accepted_cases} | blocked="
            f"{revised.blocked_reason or 'no'}"
        ),
        rationale=_string(reason, "grounding requirement revision reason"),
        status="RESOLVED",
        origin="JOINT",
        iteration=iteration,
        related_uids=(current.uid,),
    )
    result = replace(
        session,
        revision=iteration,
        requirements=tuple(
            revised if requirement.uid == current.uid else requirement
            for requirement in session.requirements
        ),
        items=(*session.items, decision),
    )
    return GroundSession.from_dict(result.to_dict())


def revise_ground_goal(
    session: GroundSession,
    goal: str,
    *,
    reason: str,
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Revise the top-level working goal while retaining the source brief."""
    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one before revising its goal."
        )
    goal = validate_ground_goal(goal, label="revised grounding goal")
    if goal == session.goal:
        raise GroundError("Grounding goal revision is a no-op.")
    iteration = session.revision + 1
    decision = GroundItem(
        uid=str(uuid.uuid4()),
        kind="DECISION",
        content="REFINE GOAL",
        expected=goal,
        rationale=_string(reason, "grounding goal revision reason"),
        status="RESOLVED",
        origin="JOINT",
        iteration=iteration,
        related_uids=(),
    )
    result = replace(
        session,
        goal=goal,
        revision=iteration,
        items=(*session.items, decision),
    )
    return GroundSession.from_dict(result.to_dict())


def accepted_ground_case_count(
    session: GroundSession,
    target_context_uid: str,
) -> int:
    """Count accepted INCLUDE Ground Memories backed by an accepted Rule."""
    accepted_rule_uids = {
        item.uid
        for item in session.items
        if item.kind == "RULE" and item.status == "ACCEPTED"
    }
    evidence = {
        (
            item.source_refs[0].context_uid,
            item.source_refs[0].memory_uid,
        )
        for item in session.items
        if item.kind == "CASE"
        and item.status == "ACCEPTED"
        and item.disposition == "INCLUDE"
        and target_context_uid in item.target_context_uids
        and any(uid in accepted_rule_uids for uid in item.related_uids)
    }
    return len(evidence)


def target_requirement_status(
    session: GroundSession,
    requirement: GroundTargetRequirement,
) -> GroundTargetStatus:
    """Derive one target state from accepted reviewed Ground Memories."""
    if requirement.blocked_reason:
        return "BLOCKED"
    accepted = accepted_ground_case_count(
        session,
        requirement.target_context_uid,
    )
    if accepted >= requirement.minimum_accepted_cases:
        return "COVERED"
    if accepted:
        return "PARTIAL"
    return "EMPTY"
