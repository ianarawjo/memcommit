"""Frozen inputs, identities, and strict Atomize Grounding primitives."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Literal

from memcommit.application.operations.meld.model import (
    MeldProposalOperation as AtomizeGroundingProposalOperation,
    MeldRevision as AtomizeGroundingRevision,
)
from memcommit.core.context import Context

__all__ = (
    "AtomizeGroundingProposalOperation",
    "AtomizeGroundingRevision",
)


ATOMIZE_GROUNDING_SCHEMA_VERSION = 2
ATOMIZE_GROUNDING_LEGACY_SCHEMA_VERSION = 1
ATOMIZE_GROUNDING_TEXT_LIMIT = 20_000
ATOMIZE_GROUNDING_NAME_LIMIT = 500
ATOMIZE_GROUNDING_ID_LIMIT = 240

AtomizeGroundingArity = Literal["UNARY", "PAIR"]
AtomizeGroundingIssueKind = Literal[
    "AMBIGUITY",
    "CONFLICT",
    "ATOMIZE_SPLIT",
    "ATOMIZE_UNCERTAINTY",
]
AtomizeGroundingState = Literal[
    "AWAITING_REPLY",
    "READY_TO_APPLY",
    "KEPT_REVIEW_ONLY",
    "APPLIED",
]
AtomizeGroundingResolution = Literal[
    "RESOLVED",
    "PARTIAL",
    "UNRESOLVED",
]
AtomizeGroundingEffectKind = Literal[
    "RESOLVES",
    "PARTIALLY_RESOLVES",
    "REQUIRES_CHANGE",
    "NEEDS_CONFIRMATION",
    "UNCHANGED",
]
AtomizeGroundingQuestionKind = Literal[
    "REQUIRED_CHANGE",
    "CLARIFICATION",
    "SCOPE_CHECK",
    "CONSISTENCY_CHECK",
]
AtomizeGroundingQuestionPriority = Literal["REQUIRED", "HELPFUL"]
AtomizeGroundingProposalNecessity = Literal["REQUIRED", "OPTIONAL"]
AtomizeGroundingDecisionAction = Literal["ACCEPT", "REJECT", "DEFER"]

_ARITIES = {"UNARY", "PAIR"}
_ISSUE_KINDS = {
    "AMBIGUITY",
    "CONFLICT",
    "ATOMIZE_SPLIT",
    "ATOMIZE_UNCERTAINTY",
}
_STATES = {
    "AWAITING_REPLY",
    "READY_TO_APPLY",
    "KEPT_REVIEW_ONLY",
    "APPLIED",
}
_REVISIONS = {"INITIAL", "CONFIRM", "EXTEND", "CORRECT", "RETRACT"}
_RESOLUTIONS = {"RESOLVED", "PARTIAL", "UNRESOLVED"}
_EFFECT_KINDS = {
    "RESOLVES",
    "PARTIALLY_RESOLVES",
    "REQUIRES_CHANGE",
    "NEEDS_CONFIRMATION",
    "UNCHANGED",
}
_QUESTION_KINDS = {
    "REQUIRED_CHANGE",
    "CLARIFICATION",
    "SCOPE_CHECK",
    "CONSISTENCY_CHECK",
}
_QUESTION_PRIORITIES = {"REQUIRED", "HELPFUL"}
_PROPOSAL_OPERATIONS = {"EDIT", "ADD"}
_PROPOSAL_NECESSITIES = {"REQUIRED", "OPTIONAL"}
_DECISION_ACTIONS = {"ACCEPT", "REJECT", "DEFER"}


class AtomizeGroundingError(ValueError):
    """Invalid, stale, or internally inconsistent grounding state."""


def _exact_dict(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = ATOMIZE_GROUNDING_TEXT_LIMIT,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
    ):
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _identifier(value: object, label: str) -> str:
    return _string(value, label, limit=ATOMIZE_GROUNDING_ID_LIMIT)


def _canonical_uuid(value: object, label: str) -> str:
    text = _string(value, label, limit=36)
    try:
        canonical = str(uuid.UUID(text))
    except ValueError as error:
        raise AtomizeGroundingError(f"Invalid {label}.") from error
    if text != canonical:
        raise AtomizeGroundingError(f"Invalid {label}.")
    return text


def _digest(value: object, label: str) -> str:
    text = _string(value, label, limit=64)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise AtomizeGroundingError(f"Invalid {label}.")
    return text


def _integer(
    value: object,
    label: str,
    *,
    nullable: bool = False,
) -> int | None:
    if nullable and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _literal(
    value: object,
    allowed: set[str],
    label: str,
) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _identifiers(
    value: object,
    label: str,
    *,
    empty: bool = False,
    uuids: bool = False,
) -> tuple[str, ...]:
    values = _list(value, label)
    if not empty and not values:
        raise AtomizeGroundingError(f"Invalid {label}.")
    parser = _canonical_uuid if uuids else _identifier
    parsed = tuple(parser(item, label) for item in values)
    if len(set(parsed)) != len(parsed):
        raise AtomizeGroundingError(f"Duplicate {label}.")
    return parsed


def atomize_grounding_canonical_digest(value: object) -> str:
    """Return the stable SHA-256 digest used for external snapshot bindings."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomize_grounding_context_digest(ctx: Context) -> str:
    """Bind the complete ordered direct Context, including reference slots.

    The semantic turn reads only directly owned Memories, but ADD proposals
    use positions in the Context's complete direct order.  Binding only those
    Memories would let a concurrent reference insertion silently move an ADD.
    Pointer serialization is sufficient here: no referenced or query-only
    content is opened or copied into the digest.
    """
    if not isinstance(ctx, Context):
        raise AtomizeGroundingError(
            "Atomize grounding Context digest requires a Context."
        )
    return atomize_grounding_canonical_digest(ctx.to_dict())


@dataclass(frozen=True)
class AtomizeGroundingBindings:
    """Immutable snapshots against which one conversation was opened."""

    context_uid: str
    context_name: str
    context_digest: str
    analysis_uid: str
    analysis_digest: str
    workbench_uid: str
    workbench_digest: str
    response_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "context": {
                "uid": self.context_uid,
                "name": self.context_name,
                "digest": self.context_digest,
            },
            "analysis": {
                "uid": self.analysis_uid,
                "digest": self.analysis_digest,
            },
            "workbench": {
                "uid": self.workbench_uid,
                "digest": self.workbench_digest,
                "response_digest": self.response_digest,
            },
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingBindings":
        data = _exact_dict(
            value,
            {"context", "analysis", "workbench"},
            "atomize grounding bindings",
        )
        context = _exact_dict(
            data["context"],
            {"uid", "name", "digest"},
            "atomize grounding Context binding",
        )
        analysis = _exact_dict(
            data["analysis"],
            {"uid", "digest"},
            "atomize grounding analysis binding",
        )
        workbench = _exact_dict(
            data["workbench"],
            {"uid", "digest", "response_digest"},
            "atomize grounding workbench binding",
        )
        return cls(
            context_uid=_canonical_uuid(
                context["uid"],
                "atomize grounding Context uid",
            ),
            context_name=_string(
                context["name"],
                "atomize grounding Context name",
                limit=ATOMIZE_GROUNDING_NAME_LIMIT,
            ),
            context_digest=_digest(
                context["digest"],
                "atomize grounding Context digest",
            ),
            analysis_uid=_canonical_uuid(
                analysis["uid"],
                "atomize grounding analysis uid",
            ),
            analysis_digest=_digest(
                analysis["digest"],
                "atomize grounding analysis digest",
            ),
            workbench_uid=_canonical_uuid(
                workbench["uid"],
                "atomize grounding workbench uid",
            ),
            workbench_digest=_digest(
                workbench["digest"],
                "atomize grounding workbench digest",
            ),
            response_digest=_digest(
                workbench["response_digest"],
                "atomize grounding response digest",
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingAnchor:
    """The selected issue, including its irreducible unary or pair shape."""

    issue_uid: str
    kind: AtomizeGroundingIssueKind
    arity: AtomizeGroundingArity
    source_uids: tuple[str, ...]
    issue_digest: str
    selected_reading_uid: str | None = None
    selected_reading_text: str = ""
    workbench_response: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "issue_uid": self.issue_uid,
            "kind": self.kind,
            "arity": self.arity,
            "source_uids": list(self.source_uids),
            "issue_digest": self.issue_digest,
            "selected_reading_uid": self.selected_reading_uid,
            "selected_reading_text": self.selected_reading_text,
            "workbench_response": self.workbench_response,
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingAnchor":
        data = _exact_dict(
            value,
            {
                "issue_uid",
                "kind",
                "arity",
                "source_uids",
                "issue_digest",
                "selected_reading_uid",
                "selected_reading_text",
                "workbench_response",
            },
            "atomize grounding anchor",
        )
        arity = _literal(
            data["arity"],
            _ARITIES,
            "atomize grounding anchor arity",
        )
        sources = _identifiers(
            data["source_uids"],
            "atomize grounding anchor source uid",
            uuids=True,
        )
        expected_count = 1 if arity == "UNARY" else 2
        if len(sources) != expected_count:
            raise AtomizeGroundingError(
                "Atomize grounding anchor arity does not match its sources."
            )
        selected = data["selected_reading_uid"]
        if selected is not None and not isinstance(selected, str):
            raise AtomizeGroundingError(
                "Invalid atomize grounding selected reading uid."
            )
        selected_text = _string(
            data["selected_reading_text"],
            "atomize grounding selected reading text",
            empty=True,
        )
        if (selected is None) != (selected_text == ""):
            raise AtomizeGroundingError(
                "A selected atomize grounding reading requires its exact "
                "text, and unselected anchors cannot carry reading text."
            )
        return cls(
            issue_uid=_identifier(
                data["issue_uid"],
                "atomize grounding anchor issue uid",
            ),
            kind=_literal(
                data["kind"],
                _ISSUE_KINDS,
                "atomize grounding anchor issue kind",
            ),  # type: ignore[arg-type]
            arity=arity,  # type: ignore[arg-type]
            source_uids=sources,
            issue_digest=_digest(
                data["issue_digest"],
                "atomize grounding anchor issue digest",
            ),
            selected_reading_uid=(
                None
                if selected is None
                else _identifier(
                    selected,
                    "atomize grounding selected reading uid",
                )
            ),
            selected_reading_text=selected_text,
            workbench_response=_string(
                data["workbench_response"],
                "atomize grounding workbench response",
                empty=True,
            ),
        )
