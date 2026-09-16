"""Operation-neutral Atomize values, rules, and provider port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.application.capabilities.semantic.prompt_policy import GENERAL_PROMPT_POLICY_ID
from memcommit.application.capabilities.semantic.understanding import UnderstandingSummary
from memcommit.application.capabilities.semantic_execution import (
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
)
from memcommit.core.context import Memory


ATOMIZE_INPUT_CHAR_LIMIT = SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT
ATOMIZE_RESPONSE_CHAR_LIMIT = 1_000_000
ATOMIZE_REASON_CHAR_LIMIT = 1_000
ATOMIZE_CHILD_CHAR_LIMIT = 20_000
ATOMIZE_CHILD_LIMIT = 20
ATOMIZE_SOURCE_SPAN_LIMIT = 20
ATOMIZE_DECLARED_FRAME_CHAR_LIMIT = 20_000
ATOMIZE_OVERVIEW_CHAR_LIMIT = 1_500
ATOMIZE_QUALITY_READING_LIMIT = 5
ATOMIZE_READING_LABEL_CHAR_LIMIT = 160
ATOMIZE_READING_LABEL_WORD_LIMIT = 20


ATOMIZE_RULESET_VERSION = "atomize-v2-reviewed-frame-draft"
# Keep the provider prompt/decoder version separate from the semantic ruleset
# so presentation changes do not redefine the structured response contract.
ATOMIZE_PROVIDER_CONTRACT_VERSION = "atomize-one-shot-quality-v1"
ATOMIZE_LEGACY_RULESET_VERSION = "atomize-v1-draft"
ATOMIZE_SIZE_REVIEW_CHARS = 80
ATOMIZE_SIZE_REVIEW_SEGMENTS = 2
ATOMIZE_SEGMENTER_VERSION = "sentence-like-v1"
ATOMIZE_ANALYSIS_SCHEMA_VERSION = 6
ATOMIZE_FOCUSED_ANALYSIS_SCHEMA_VERSION = 5
ATOMIZE_QUALITY_ANALYSIS_SCHEMA_VERSION = 3
ATOMIZE_REVIEWED_ANALYSIS_SCHEMA_VERSION = 2
ATOMIZE_LEGACY_ANALYSIS_SCHEMA_VERSION = 1

ATOMIZE_RULES = {
    "A01_ONE_FOCUS": (
        "One child owns one focal-commitment occurrence; independently "
        "revisable P and Q become separate children."
    ),
    "A02_SCOPE_ATTACHED": (
        "Subject, audience, place, time, modality, negation, condition, and "
        "exception remain attached to the commitment they scope."
    ),
    "A03_RELATION_PRESERVED": (
        "A focal condition, exception, alternative, transition, comparison, "
        "or causal relation stays intact rather than becoming stronger "
        "stand-alone claims."
    ),
    "A04_SOURCE_GROUNDED": (
        "Every child must cite an explicit original-source occurrence. A "
        "reviewed declared frame may additionally resolve or repeat a "
        "referent or scope, but cannot replace original source evidence."
    ),
    "A05_MINIMAL_EXPANSION": (
        "Repeat an explicit subject or qualifier and repair grammar only as "
        "needed to make a child stand alone; do not normalize style."
    ),
    "A06_NO_HIDDEN_CONTEXT": (
        "Neighboring Memories and undeclared assumptions are not evidence; "
        "unresolved deixis or qualifier scope makes the source UNCERTAIN."
    ),
    "A07_RETAIN_NON_CLAIMS": (
        "Headings, questions, fragments, and process notes remain "
        "addressable and are not fabricated into factual claims."
    ),
    "A08_PRESERVE_OCCURRENCES": (
        "Preserve every explicit source occurrence, including repeated "
        "claims during semantic chunking; only the composed typed Dedun "
        "phase may later absorb an exposed duplicate."
    ),
    "A09_SIZE_IS_LINT": (
        "Length and sentence count only request review and never prove that "
        "a source is composite."
    ),
    "A10_STAGE_BOUNDARY": (
        "This semantic-chunk proposal does not deduplicate, reconcile "
        "ambiguity, normalize, classify audiences, or place Memories."
    ),
}

AtomizeClassification = Literal[
    "ATOMIC",
    "COMPOSITE",
    "UNCERTAIN",
    "NON_PROPOSITIONAL",
]
AtomizeQualityKind = Literal["AMBIGUITY", "CONFLICT"]
AtomizeInterpretation = Literal["SINGLE", "DOMINANT", "COMPETING"]
AtomizeClarification = Literal["NONE", "HELPFUL", "REQUIRED"]
AtomizeConflict = Literal["YES", "MAY"]
AtomizeReadingRole = Literal[
    "SINGLE",
    "DOMINANT",
    "ALTERNATIVE",
    "COMPETING",
]

ATOMIZE_CLASSIFICATIONS = {
    "ATOMIC",
    "COMPOSITE",
    "UNCERTAIN",
    "NON_PROPOSITIONAL",
}
ATOMIZE_RULE_CODES = set(ATOMIZE_RULES)
ATOMIZE_QUALITY_KINDS = {"AMBIGUITY", "CONFLICT"}
ATOMIZE_INTERPRETATIONS = {"SINGLE", "DOMINANT", "COMPETING"}
ATOMIZE_CLARIFICATIONS = {"NONE", "HELPFUL", "REQUIRED"}
ATOMIZE_CONFLICTS = {"YES", "MAY"}
ATOMIZE_READING_ROLES = {
    "SINGLE",
    "DOMINANT",
    "ALTERNATIVE",
    "COMPETING",
}
ATOMIZE_SCOPE_DIMENSIONS = {
    "SUBJECT",
    "PREDICATE",
    "OBJECT",
    "PLACE",
    "AUDIENCE",
    "TIME",
    "MODALITY",
    "ACCESS_METHOD",
    "CONDITION",
    "EXCEPTION",
    "OTHER",
}


class AtomizeImpactError(RuntimeError):
    """Safe, user-facing error from an atomize impact operation."""


class AtomizeProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one structured model completion."""


@dataclass(frozen=True)
class AtomizeCandidate:
    candidate_id: str
    position: int
    memory: Memory
    lint: tuple[str, ...]

    @property
    def uid(self) -> str:
        """Expose the source identity to the shared focus resolver."""

        return self.memory.uid


@dataclass(frozen=True)
class AtomizeChild:
    content: str
    source_spans: tuple[str, ...]
    frame_spans: tuple[str, ...] = ()


class AtomizeOverviewSection(UnderstandingSummary):
    """Compatibility name for Atomize-specific outcome report sections."""

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeOverviewSection":
        if (
            not isinstance(value, dict)
            or set(value) != {"text", "source_uids"}
        ):
            raise AtomizeImpactError("Invalid saved atomize overview section.")
        text = value["text"]
        source_uids = value["source_uids"]
        if (
            not isinstance(text, str)
            or len(text) > ATOMIZE_OVERVIEW_CHAR_LIMIT
            or not isinstance(source_uids, list)
            or any(
                not isinstance(source_uid, str) or not source_uid
                for source_uid in source_uids
            )
            or len(set(source_uids)) != len(source_uids)
        ):
            raise AtomizeImpactError("Invalid saved atomize overview section.")
        return cls(text=text, source_uids=tuple(source_uids))


@dataclass(frozen=True)
class AtomizeOverview:
    """The compact comprehension and transformation signal shown first."""

    understood: UnderstandingSummary
    changed: AtomizeOverviewSection
    unresolved: AtomizeOverviewSection

    def to_dict(self) -> dict[str, object]:
        return {
            "understood": self.understood.to_dict(),
            "changed": self.changed.to_dict(),
            "unresolved": self.unresolved.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeOverview":
        if (
            not isinstance(value, dict)
            or set(value) != {"understood", "changed", "unresolved"}
        ):
            raise AtomizeImpactError("Invalid saved atomize overview.")
        return cls(
            understood=AtomizeOverviewSection.from_dict(value["understood"]),
            changed=AtomizeOverviewSection.from_dict(value["changed"]),
            unresolved=AtomizeOverviewSection.from_dict(value["unresolved"]),
        )


@dataclass(frozen=True)
class AtomizeReading:
    """One ordinary reading exposed for user selection or qualification."""

    uid: str
    role: AtomizeReadingRole
    label: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {
            "uid": self.uid,
            "role": self.role,
            "label": self.label,
            "text": self.text,
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
        *,
        legacy_label: bool = False,
    ) -> "AtomizeReading":
        keys = (
            {"uid", "role", "text"}
            if legacy_label
            else {"uid", "role", "label", "text"}
        )
        if (
            not isinstance(value, dict)
            or set(value) != keys
        ):
            raise AtomizeImpactError("Invalid saved atomize issue reading.")
        uid = value["uid"]
        role = value["role"]
        label = value["text"] if legacy_label else value["label"]
        text = value["text"]
        if (
            not isinstance(uid, str)
            or not uid
            or not isinstance(role, str)
            or role not in ATOMIZE_READING_ROLES
            or not isinstance(label, str)
            or not label.strip()
            or len(label) > (
                ATOMIZE_REASON_CHAR_LIMIT
                if legacy_label
                else ATOMIZE_READING_LABEL_CHAR_LIMIT
            )
            or (
                not legacy_label
                and (
                    len(label.splitlines()) != 1
                    or len(label.split()) > ATOMIZE_READING_LABEL_WORD_LIMIT
                )
            )
            or not isinstance(text, str)
            or not text.strip()
            or len(text) > ATOMIZE_REASON_CHAR_LIMIT
        ):
            raise AtomizeImpactError("Invalid saved atomize issue reading.")
        return cls(uid=uid, role=role, label=label, text=text)


@dataclass(frozen=True)
class AtomizeQualityIssue:
    """A typed ambiguity or conflict found in the projected local frame."""

    uid: str
    kind: AtomizeQualityKind
    source_uids: tuple[str, ...]
    reason: str
    question: str
    interpretation: AtomizeInterpretation | None = None
    clarification: AtomizeClarification | None = None
    conflict: AtomizeConflict | None = None
    readings: tuple[AtomizeReading, ...] = ()
    scope_dimensions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "kind": self.kind,
            "source_uids": list(self.source_uids),
            "reason": self.reason,
            "question": self.question,
            "interpretation": self.interpretation,
            "clarification": self.clarification,
            "conflict": self.conflict,
            "readings": [reading.to_dict() for reading in self.readings],
            "scope_dimensions": list(self.scope_dimensions),
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
        *,
        schema_version: int = ATOMIZE_ANALYSIS_SCHEMA_VERSION,
    ) -> "AtomizeQualityIssue":
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "uid",
                "kind",
                "source_uids",
                "reason",
                "question",
                "interpretation",
                "clarification",
                "conflict",
                "readings",
                "scope_dimensions",
            }
        ):
            raise AtomizeImpactError("Invalid saved atomize quality issue.")
        uid = value["uid"]
        kind = value["kind"]
        source_uids = value["source_uids"]
        reason = value["reason"]
        question = value["question"]
        interpretation = value["interpretation"]
        clarification = value["clarification"]
        conflict = value["conflict"]
        readings = value["readings"]
        scope_dimensions = value["scope_dimensions"]
        if (
            not isinstance(uid, str)
            or not uid
            or not isinstance(kind, str)
            or kind not in ATOMIZE_QUALITY_KINDS
            or not isinstance(source_uids, list)
            or any(
                not isinstance(source_uid, str) or not source_uid
                for source_uid in source_uids
            )
            or len(set(source_uids)) != len(source_uids)
            or not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > ATOMIZE_REASON_CHAR_LIMIT
            or not isinstance(question, str)
            or len(question) > 500
            or not isinstance(readings, list)
            or len(readings) > ATOMIZE_QUALITY_READING_LIMIT
            or not isinstance(scope_dimensions, list)
            or any(
                not isinstance(dimension, str)
                or dimension not in ATOMIZE_SCOPE_DIMENSIONS
                for dimension in scope_dimensions
            )
            or len(set(scope_dimensions)) != len(scope_dimensions)
        ):
            raise AtomizeImpactError("Invalid saved atomize quality issue.")
        parsed_readings = tuple(
            AtomizeReading.from_dict(
                reading,
                legacy_label=(
                    schema_version <= ATOMIZE_QUALITY_ANALYSIS_SCHEMA_VERSION
                ),
            )
            for reading in readings
        )
        if (
            len({reading.uid for reading in parsed_readings})
            != len(parsed_readings)
            or (
                schema_version > ATOMIZE_QUALITY_ANALYSIS_SCHEMA_VERSION
                and len({reading.label for reading in parsed_readings})
                != len(parsed_readings)
            )
        ):
            raise AtomizeImpactError("Invalid saved atomize quality issue.")

        if kind == "AMBIGUITY":
            if (
                len(source_uids) != 1
                or not isinstance(interpretation, str)
                or interpretation not in ATOMIZE_INTERPRETATIONS
                or not isinstance(clarification, str)
                or clarification not in ATOMIZE_CLARIFICATIONS
                or conflict is not None
                or scope_dimensions
                or (
                    interpretation == "SINGLE"
                    and len(parsed_readings) != 1
                )
                or (
                    interpretation != "SINGLE"
                    and len(parsed_readings) < 2
                )
                or tuple(
                    reading.role for reading in parsed_readings
                )
                != _reading_roles(
                    interpretation,
                    len(parsed_readings),
                )
                or (
                    clarification == "NONE"
                    and question.strip()
                )
                or (
                    clarification != "NONE"
                    and not question.strip()
                )
            ):
                raise AtomizeImpactError(
                    "Invalid saved atomize ambiguity issue."
                )
        elif (
            len(source_uids) != 2
            or interpretation is not None
            or clarification is not None
            or not isinstance(conflict, str)
            or conflict not in ATOMIZE_CONFLICTS
            or (
                conflict == "MAY"
                and (
                    not scope_dimensions
                    or not question.strip()
                    or len(parsed_readings) < 2
                )
            )
            or any(
                reading.role != "COMPETING"
                for reading in parsed_readings
            )
        ):
            raise AtomizeImpactError("Invalid saved atomize conflict issue.")
        return cls(
            uid=uid,
            kind=kind,
            source_uids=tuple(source_uids),
            reason=reason,
            question=question,
            interpretation=interpretation,
            clarification=clarification,
            conflict=conflict,
            readings=parsed_readings,
            scope_dimensions=tuple(scope_dimensions),
        )


@dataclass(frozen=True)
class AtomizeItem:
    memory: Memory
    position: int
    classification: AtomizeClassification
    reason_codes: tuple[str, ...]
    children: tuple[AtomizeChild, ...]
    reason: str
    lint: tuple[str, ...]

    @property
    def action(self) -> str:
        """Return the locally derived preview action for this classification."""
        return {
            "ATOMIC": "KEEP",
            "COMPOSITE": "SPLIT",
            "UNCERTAIN": "RECONCILE",
            "NON_PROPOSITIONAL": "KEEP_CLASSIFIED",
        }[self.classification]


@dataclass(frozen=True)
class AtomizeImpactReport:
    context_uid: str
    context_name: str
    memory_count: int
    projected_memory_count: int
    items: tuple[AtomizeItem, ...]
    overview: AtomizeOverview | None = None
    quality_issues: tuple[AtomizeQualityIssue, ...] = ()
    prompt_policy_id: str = GENERAL_PROMPT_POLICY_ID

    def count(self, classification: AtomizeClassification) -> int:
        return sum(
            item.classification == classification
            for item in self.items
        )


def _reading_roles(
    interpretation: str,
    count: int,
) -> tuple[AtomizeReadingRole, ...]:
    if interpretation == "SINGLE":
        return ("SINGLE",)
    if interpretation == "DOMINANT":
        return (
            "DOMINANT",
            *(("ALTERNATIVE",) * (count - 1)),
        )
    return ("COMPETING",) * count
