"""Operation-owned Ground Fit report plus the public general-Fit exports.

The foundational YES/MAY/NO proposition judge lives in the operation-owned
``judgment`` module and is re-exported here for the historical ``memcommit.application.operations.fit.ground_report``
contract. The versioned Ground report keeps its historical per-Example
judgments and adds an exhaustive Context, vertical, and peer coherence frame
without making Ground the definition of Fit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal, Protocol
import uuid

from memcommit.application.operations.fit.judgment import (
    FIT_JUDGMENT_OPERATION,
    FitAnalysis as FitAnalysis,
    FitAssessment as FitAssessment,
    FitBatchAnalysis as FitBatchAnalysis,
    FitJudgmentError,
    FitProposition,
    FitQuestion,
    FitRole as FitRole,
    FitVerdict,
    judge_fit as judge_fit,
    judge_fit_questions,
)
from memcommit.application.operations.fit.coherence import FitCoherenceReport
from memcommit.providers.types import ProviderIdentity


FIT_SCHEMA_VERSION = 3
FIT_RULESET_VERSION = "ground-fit-v2"
FIT_PROPOSITION_OPERATION = FIT_JUDGMENT_OPERATION
FIT_TEXT_LIMIT = 20_000
FIT_MAX_RULES = 200
FIT_MAX_EXAMPLES = 2_000

FitStatus = Literal[
    "FIT",
    "CONTRADICTS",
    "UNDERDETERMINED",
]

_FIT_STATUSES = {
    "FIT",
    "CONTRADICTS",
    "UNDERDETERMINED",
}


class FitError(ValueError):
    """Safe failure from one bounded Fit execution or receipt."""


class FitProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one structured, exhaustive Fit judgment."""


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FitError(f"Fit {label} must be text.")
    result = value.strip()
    if len(result) > FIT_TEXT_LIMIT:
        raise FitError(f"Fit {label} is too long.")
    return result


def _uuid(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise FitError(f"Fit {label} must be a UUID.")
    try:
        canonical = str(uuid.UUID(value))
    except ValueError as error:
        raise FitError(f"Fit {label} must be a UUID.") from error
    if canonical != value:
        raise FitError(f"Fit {label} must be canonical.")
    return canonical


def _digest(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise FitError(f"Fit {label} must be a sha256 digest.")
    return text


def _exact(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise FitError(f"Invalid Fit {label}.")
    return value


def _identity_dict(identity: ProviderIdentity | None) -> object:
    if identity is None:
        return None
    return {
        "provider": identity.provider,
        "model": identity.model,
        "model_digest": identity.model_digest,
        "runtime": identity.runtime,
        "endpoint": identity.endpoint,
        "reasoning_effort": identity.reasoning_effort,
    }


def _identity(value: object) -> ProviderIdentity | None:
    if value is None:
        return None
    data = _exact(
        value,
        {
            "provider",
            "model",
            "model_digest",
            "runtime",
            "endpoint",
            "reasoning_effort",
        },
        "provider identity",
    )
    optional: dict[str, str | None] = {}
    for key in ("model_digest", "runtime", "endpoint", "reasoning_effort"):
        raw = data[key]
        if raw is not None and not isinstance(raw, str):
            raise FitError("Invalid Fit provider identity.")
        optional[key] = raw
    return ProviderIdentity(
        provider=_text(data["provider"], "provider name"),
        model=_text(data["model"], "provider model"),
        **optional,
    )


def _created_at(value: object) -> str:
    text = _text(value, "creation time")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise FitError("Invalid Fit creation time.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FitError("Fit creation time must include a timezone.")
    return text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class FitRule:
    uid: str
    alias: str
    statement: str

    def __post_init__(self) -> None:
        _uuid(self.uid, "Rule uid")
        _text(self.alias, "Rule alias")
        _text(self.statement, "Rule statement")

    def to_dict(self) -> dict[str, str]:
        return {"uid": self.uid, "alias": self.alias, "statement": self.statement}

    @classmethod
    def from_dict(cls, value: object) -> "FitRule":
        data = _exact(value, {"uid", "alias", "statement"}, "Rule")
        return cls(
            uid=_uuid(data["uid"], "Rule uid"),
            alias=_text(data["alias"], "Rule alias"),
            statement=_text(data["statement"], "Rule statement"),
        )


@dataclass(frozen=True)
class FitExample:
    uid: str
    alias: str
    statement: str
    rule_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        _uuid(self.uid, "Example uid")
        _text(self.alias, "Example alias")
        _text(self.statement, "Example proposition")
        if not self.rule_uids or len(self.rule_uids) != len(set(self.rule_uids)):
            raise FitError("A fitted Example needs unique active Rules.")
        for uid in self.rule_uids:
            _uuid(uid, "Example Rule uid")

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "alias": self.alias,
            "statement": self.statement,
            "rule_uids": list(self.rule_uids),
        }

    @classmethod
    def from_dict(cls, value: object) -> "FitExample":
        data = _exact(
            value,
            {"uid", "alias", "statement", "rule_uids"},
            "Example",
        )
        rule_uids = data["rule_uids"]
        if not isinstance(rule_uids, list):
            raise FitError("Invalid Fit Example Rules.")
        return cls(
            uid=_uuid(data["uid"], "Example uid"),
            alias=_text(data["alias"], "Example alias"),
            statement=_text(data["statement"], "Example proposition"),
            rule_uids=tuple(_uuid(uid, "Example Rule uid") for uid in rule_uids),
        )


@dataclass(frozen=True)
class FitJudgment:
    example_uid: str
    status: FitStatus
    rule_uids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        _uuid(self.example_uid, "judgment Example uid")
        if self.status not in _FIT_STATUSES:
            raise FitError("Invalid Fit status.")
        if not self.rule_uids or len(self.rule_uids) != len(set(self.rule_uids)):
            raise FitError("A Fit judgment needs unique Rules.")
        for uid in self.rule_uids:
            _uuid(uid, "judgment Rule uid")
        _text(self.reason, "judgment reason")

    def to_dict(self) -> dict[str, object]:
        return {
            "example_uid": self.example_uid,
            "status": self.status,
            "rule_uids": list(self.rule_uids),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: object) -> "FitJudgment":
        data = _exact(
            value,
            {"example_uid", "status", "rule_uids", "reason"},
            "judgment",
        )
        rule_uids = data["rule_uids"]
        if not isinstance(rule_uids, list):
            raise FitError("Invalid Fit judgment Rules.")
        return cls(
            example_uid=_uuid(data["example_uid"], "judgment Example uid"),
            status=data["status"],  # type: ignore[arg-type]
            rule_uids=tuple(_uuid(uid, "judgment Rule uid") for uid in rule_uids),
            reason=_text(data["reason"], "judgment reason"),
        )


@dataclass(frozen=True)
class FitReport:
    uid: str
    ground_uid: str
    ground_name: str
    ground_revision: int
    ground_digest: str
    rules: tuple[FitRule, ...]
    examples: tuple[FitExample, ...]
    judgments: tuple[FitJudgment, ...]
    overview: str
    created_at: str
    provider_identity: ProviderIdentity | None = None
    coherence: FitCoherenceReport | None = None
    schema_version: int = FIT_SCHEMA_VERSION
    ruleset_version: str = FIT_RULESET_VERSION

    def __post_init__(self) -> None:
        _uuid(self.uid, "report uid")
        _uuid(self.ground_uid, "Ground uid")
        _text(self.ground_name, "Ground name")
        if isinstance(self.ground_revision, bool) or self.ground_revision < 0:
            raise FitError("Invalid Fit Ground revision.")
        _digest(self.ground_digest, "Ground digest")
        _text(self.overview, "overview")
        _created_at(self.created_at)
        if (
            self.schema_version != FIT_SCHEMA_VERSION
            or self.ruleset_version != FIT_RULESET_VERSION
        ):
            raise FitError("Unsupported Fit schema or ruleset.")
        if self.coherence is not None and not isinstance(
            self.coherence, FitCoherenceReport
        ):
            raise FitError("Invalid Fit coherence receipt shape.")
        if not self.rules or not self.examples:
            raise FitError("Fit requires active Rules and Examples.")
        rule_uids = {rule.uid for rule in self.rules}
        example_uids = {example.uid for example in self.examples}
        judged_uids = {judgment.example_uid for judgment in self.judgments}
        if len(rule_uids) != len(self.rules) or len(example_uids) != len(self.examples):
            raise FitError("Fit inputs contain duplicate identities.")
        if len(judged_uids) != len(self.judgments) or judged_uids != example_uids:
            raise FitError("Fit must judge every Example exactly once.")
        example_by_uid = {example.uid: example for example in self.examples}
        if any(set(example.rule_uids) - rule_uids for example in self.examples):
            raise FitError("A Fit Example names an unknown Rule.")
        for judgment in self.judgments:
            if judgment.rule_uids != example_by_uid[judgment.example_uid].rule_uids:
                raise FitError("A Fit judgment changed its frozen Rule set.")
        if self.coherence is not None:
            coherence_goals = tuple(
                (item.uid, item.alias)
                for item in self.coherence.subjects
                if item.layer == "GOAL"
            )
            coherence_rules = tuple(
                (item.uid, item.alias)
                for item in self.coherence.subjects
                if item.layer == "RULE"
            )
            coherence_examples = tuple(
                (item.uid, item.alias)
                for item in self.coherence.subjects
                if item.layer == "EXAMPLE"
            )
            if (
                coherence_goals != ((self.ground_uid, "g1"),)
                or (
                    coherence_rules
                    != tuple((rule.uid, rule.alias) for rule in self.rules)
                )
                or coherence_examples
                != tuple((example.uid, example.alias) for example in self.examples)
            ):
                raise FitError("Fit coherence changed its frozen Ground subject frame.")

    @property
    def issue_count(self) -> int:
        return sum(judgment.status != "FIT" for judgment in self.judgments) + (
            self.coherence.issue_count if self.coherence is not None else 0
        )

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "ruleset_version": self.ruleset_version,
            "uid": self.uid,
            "ground_uid": self.ground_uid,
            "ground_name": self.ground_name,
            "ground_revision": self.ground_revision,
            "ground_digest": self.ground_digest,
            "rules": [rule.to_dict() for rule in self.rules],
            "examples": [example.to_dict() for example in self.examples],
            "judgments": [judgment.to_dict() for judgment in self.judgments],
            "overview": self.overview,
            "created_at": self.created_at,
            "provider_identity": _identity_dict(self.provider_identity),
            "coherence": (
                self.coherence.to_dict() if self.coherence is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "FitReport":
        if not isinstance(value, dict):
            raise FitError("Invalid Fit report.")
        schema_version = value.get("schema_version")
        ruleset_version = value.get("ruleset_version")
        if (
            schema_version != FIT_SCHEMA_VERSION
            or ruleset_version != FIT_RULESET_VERSION
        ):
            raise FitError("Unsupported Fit schema or ruleset.")
        data = _exact(
            value,
            {
                "schema_version",
                "ruleset_version",
                "uid",
                "ground_uid",
                "ground_name",
                "ground_revision",
                "ground_digest",
                "rules",
                "examples",
                "judgments",
                "overview",
                "created_at",
                "provider_identity",
                "coherence",
            },
            "report",
        )
        for key in ("rules", "examples", "judgments"):
            if not isinstance(data[key], list):
                raise FitError(f"Invalid Fit report {key}.")
        revision = data["ground_revision"]
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise FitError("Invalid Fit Ground revision.")
        return cls(
            schema_version=data["schema_version"],  # type: ignore[arg-type]
            ruleset_version=data["ruleset_version"],  # type: ignore[arg-type]
            uid=_uuid(data["uid"], "report uid"),
            ground_uid=_uuid(data["ground_uid"], "Ground uid"),
            ground_name=_text(data["ground_name"], "Ground name"),
            ground_revision=revision,
            ground_digest=_digest(data["ground_digest"], "Ground digest"),
            rules=tuple(FitRule.from_dict(item) for item in data["rules"]),  # type: ignore[union-attr]
            examples=tuple(FitExample.from_dict(item) for item in data["examples"]),  # type: ignore[union-attr]
            judgments=tuple(FitJudgment.from_dict(item) for item in data["judgments"]),  # type: ignore[union-attr]
            overview=_text(data["overview"], "overview"),
            created_at=_created_at(data["created_at"]),
            provider_identity=_identity(data["provider_identity"]),
            coherence=(
                FitCoherenceReport.from_dict(data["coherence"])
                if data["coherence"] is not None
                else None
            ),
        )


def _validate_frame(
    rules: tuple[FitRule, ...],
    examples: tuple[FitExample, ...],
) -> None:
    if not rules or not examples:
        raise FitError("Fit requires active Rules and Examples.")
    if len(rules) > FIT_MAX_RULES or len(examples) > FIT_MAX_EXAMPLES:
        raise FitError("Fit frame is too large.")
    rule_uids = {rule.uid for rule in rules}
    if len(rule_uids) != len(rules) or len({rule.alias for rule in rules}) != len(
        rules
    ):
        raise FitError("Fit Rules need unique identities and aliases.")
    if len({example.uid for example in examples}) != len(examples) or len(
        {example.alias for example in examples}
    ) != len(examples):
        raise FitError("Fit Examples need unique identities and aliases.")
    if any(set(example.rule_uids) - rule_uids for example in examples):
        raise FitError("A Fit Example names an unknown Rule.")


def _proposition_fit(
    *,
    ground_uid: str,
    ground_name: str,
    ground_revision: int,
    ground_digest: str,
    rules: tuple[FitRule, ...],
    examples: tuple[FitExample, ...],
    provider: FitProvider,
) -> FitReport:
    rule_by_uid = {rule.uid: rule for rule in rules}
    questions = tuple(
        FitQuestion(
            question_id=example.alias,
            propositions=(
                *(
                    FitProposition(
                        alias=rule_by_uid[uid].alias,
                        content=rule_by_uid[uid].statement,
                        role="RULE",
                    )
                    for uid in example.rule_uids
                ),
                FitProposition(
                    alias=example.alias,
                    content=example.statement,
                    role="EXAMPLE",
                ),
            ),
        )
        for example in examples
    )
    try:
        analysis = judge_fit_questions(questions, provider=provider)
    except FitJudgmentError as error:
        raise FitError(str(error)) from error
    example_by_alias = {example.alias: example for example in examples}
    status_map: dict[FitVerdict, FitStatus] = {
        "YES": "FIT",
        "NO": "CONTRADICTS",
        "MAY": "UNDERDETERMINED",
    }
    judgments = tuple(
        FitJudgment(
            example_uid=example_by_alias[assessment.question_id].uid,
            status=status_map[assessment.verdict],
            rule_uids=example_by_alias[assessment.question_id].rule_uids,
            reason=assessment.reason,
        )
        for assessment in analysis.assessments
    )
    return FitReport(
        uid=str(uuid.uuid4()),
        ground_uid=ground_uid,
        ground_name=ground_name,
        ground_revision=ground_revision,
        ground_digest=ground_digest,
        rules=rules,
        examples=examples,
        judgments=judgments,
        overview=analysis.overview,
        created_at=_now(),
        provider_identity=analysis.provider_identity,
    )


def fit_ground_examples(
    *,
    ground_uid: str,
    ground_name: str,
    ground_revision: int,
    ground_digest: str,
    rules: tuple[FitRule, ...],
    examples: tuple[FitExample, ...],
    provider: FitProvider,
) -> FitReport:
    """Judge every frozen Example once without changing its Ground."""

    _uuid(ground_uid, "Ground uid")
    _text(ground_name, "Ground name")
    if (
        isinstance(ground_revision, bool)
        or not isinstance(ground_revision, int)
        or ground_revision < 0
    ):
        raise FitError("Invalid Fit Ground revision.")
    _digest(ground_digest, "Ground digest")
    _validate_frame(rules, examples)
    return _proposition_fit(
        ground_uid=ground_uid,
        ground_name=ground_name,
        ground_revision=ground_revision,
        ground_digest=ground_digest,
        rules=rules,
        examples=examples,
        provider=provider,
    )
