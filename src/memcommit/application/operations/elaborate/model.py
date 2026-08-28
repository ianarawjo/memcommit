"""Exact-count top-down Rule and Case proposal models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Protocol
import uuid

from memcommit.application.operations.conformance.model import (
    CONFORMANCE_TEXT_LIMIT,
)
from memcommit.application.operations.elaborate.config import (
    DEFAULT_ELABORATE_SEMANTIC_CONFIG,
    ElaborateSemanticConfig,
)
from memcommit.application.operations.fit.judgment import (
    FIT_JUDGMENT_TEXT_LIMIT,
)
from memcommit.application.capabilities.semantic.goal_focus import FrozenGoalFocus


ELABORATE_OPERATION = "elaborate"
ELABORATE_PROVIDER_CONTRACT_VERSION = 14
ELABORATE_PAYLOAD_MARKER = "ELABORATE PAYLOAD:\n"


class ElaborateMode(str, Enum):
    GOAL_TO_RULES = "GOAL_TO_RULES"
    RULES_TO_CASES = "RULES_TO_CASES"


class ElaborateQualityPolicy(str, Enum):
    """Whether generated Cases are suggestions or independently gated."""

    BEST_EFFORT = "BEST_EFFORT"
    STRICT = "STRICT"


class ElaborateError(RuntimeError):
    """Safe failure from one bounded Elaborate request."""


class ElaborateProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one strict proposal envelope."""


@dataclass(frozen=True)
class ElaborateTargetContextItem:
    """One bounded Target-side ambient item exposed to Elaborate."""

    alias: str
    kind: str
    context_name: str
    memory_uid: str | None = None
    content: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.alias, str) or not self.alias.startswith("t"):
            raise ElaborateError("Elaborate Target item alias is invalid.")
        if self.kind not in {"MEMORY", "QUERY_ONLY_CONTEXT"}:
            raise ElaborateError("Elaborate Target item kind is invalid.")
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ElaborateError("Elaborate Target item Context is invalid.")
        if self.kind == "MEMORY":
            if not isinstance(self.memory_uid, str) or not self.memory_uid:
                raise ElaborateError("Elaborate Target Memory identity is invalid.")
            if not isinstance(self.content, str) or not self.content.strip():
                raise ElaborateError("Elaborate Target Memory content is invalid.")
        elif self.memory_uid is not None or self.content is not None:
            # A query-only route contributes orientation by public name only.
            # Retaining hidden identity or content here would make a later
            # prompt adapter capable of crossing the query boundary by accident.
            raise ElaborateError(
                "Elaborate query-only Target items must remain name-only."
            )

    def prompt_record(self) -> dict[str, object]:
        if self.kind == "MEMORY":
            return {
                "target_id": self.alias,
                "kind": self.kind,
                "context": self.context_name,
                "content": self.content,
            }
        return {
            "target_id": self.alias,
            "kind": self.kind,
            "context": self.context_name,
        }


@dataclass(frozen=True)
class ElaborateTargetContext:
    """The exact existing destination frame used only as ambient context."""

    context_name: str
    items: tuple[ElaborateTargetContextItem, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ElaborateError("Elaborate Target Context name is invalid.")
        if not isinstance(self.items, tuple):
            raise ElaborateError("Elaborate Target Context items must be a tuple.")
        expected_aliases = tuple(f"t{index}" for index in range(1, len(self.items) + 1))
        if tuple(item.alias for item in self.items) != expected_aliases:
            raise ElaborateError(
                "Elaborate Target Context aliases must be contiguous and ordered."
            )

    def prompt_record(self) -> dict[str, object]:
        return {
            "name": self.context_name,
            "role": "AMBIENT_DESTINATION_CONTEXT",
            "items": [item.prompt_record() for item in self.items],
        }

    @property
    def aliases(self) -> tuple[str, ...]:
        return tuple(item.alias for item in self.items)


def _text(value: object, label: str, *, limit: int, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ElaborateError(f"Elaborate {label} must be text.")
    normalized = value.strip()
    if not normalized and not empty:
        raise ElaborateError(f"Elaborate {label} must be nonempty text.")
    if len(normalized) > limit:
        raise ElaborateError(
            f"Elaborate {label} exceeds its {limit}-character limit."
        )
    return normalized


def normalize_elaborate_inputs(
    *,
    goal: str | None,
    rules: tuple[str, ...],
    config: ElaborateSemanticConfig = DEFAULT_ELABORATE_SEMANTIC_CONFIG,
) -> tuple[ElaborateMode, tuple[str, ...]]:
    """Choose exactly one top-down derivation direction."""

    if not isinstance(config, ElaborateSemanticConfig):
        raise TypeError("Elaborate requires an ElaborateSemanticConfig.")
    if not isinstance(rules, tuple):
        raise ElaborateError("Elaborate Rules must be a tuple.")
    normalized_rules = tuple(
        _text(rule, "Rule", limit=config.text_limit) for rule in rules
    )
    if len({rule.casefold() for rule in normalized_rules}) != len(normalized_rules):
        raise ElaborateError("Elaborate Rules must be distinct.")
    normalized_goal = (
        None
        if goal is None
        else _text(goal, "Goal", limit=config.text_limit)
    )
    if normalized_goal is not None and normalized_rules:
        raise ElaborateError("Elaborate accepts either one Goal or Rules, not both.")
    if normalized_goal is not None:
        return ElaborateMode.GOAL_TO_RULES, (normalized_goal,)
    if normalized_rules:
        return ElaborateMode.RULES_TO_CASES, normalized_rules
    raise ElaborateError("Elaborate requires one Goal or at least one Rule.")


def normalize_elaborate_number(
    *,
    mode: ElaborateMode,
    number: int | None,
    config: ElaborateSemanticConfig = DEFAULT_ELABORATE_SEMANTIC_CONFIG,
) -> int:
    """Resolve the default or explicit positive exact proposal count."""

    if not isinstance(mode, ElaborateMode):
        raise ElaborateError("Elaborate proposal count requires a valid direction.")
    if not isinstance(config, ElaborateSemanticConfig):
        raise TypeError("Elaborate requires an ElaborateSemanticConfig.")
    if number is None:
        number = config.default_proposal_count
    if type(number) is not int or number <= 0:
        raise ElaborateError("Elaborate number must be a positive integer.")
    maximum = (
        config.max_rule_proposals
        if mode is ElaborateMode.GOAL_TO_RULES
        else config.max_case_proposals
    )
    if maximum is not None and number > maximum:
        label = "Rule" if mode is ElaborateMode.GOAL_TO_RULES else "Case"
        raise ElaborateError(
            f"Elaborate {label} number must be between 1 and {maximum}."
        )
    return number


@dataclass(frozen=True)
class ElaboratedRule:
    uid: str
    content: str
    rationale: str
    target_context_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.uid)
        except (AttributeError, TypeError, ValueError) as error:
            raise ElaborateError("Elaborated Rule uid must be a UUID.") from error
        if not isinstance(self.content, str) or not self.content.strip():
            raise ElaborateError("Elaborated Rule content must be nonempty text.")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ElaborateError("Elaborated Rule rationale must be nonempty text.")
        if (
            not isinstance(self.target_context_refs, tuple)
            or len(set(self.target_context_refs)) != len(self.target_context_refs)
            or any(not isinstance(alias, str) or not alias for alias in self.target_context_refs)
        ):
            raise ElaborateError("Elaborated Rule Target references are invalid.")


@dataclass(frozen=True)
class ElaboratedRuleCheck:
    source_rule_index: int
    evidence: str

    def __post_init__(self) -> None:
        if type(self.source_rule_index) is not int or self.source_rule_index < 1:
            raise ElaborateError("Elaborated Rule check index is invalid.")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ElaborateError("Elaborated Rule check evidence must be nonempty text.")


@dataclass(frozen=True)
class ElaboratedCaseValidation:
    """Collection Rule-conformance and Source-Fit retained on one Case."""

    source_fit: str
    source_fit_reason: str
    rule_conformance: str
    conforming_source_rule_indexes: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.source_fit != "YES":
            raise ElaborateError("An accepted Elaborate Case must Fit its Source.")
        if not isinstance(self.source_fit_reason, str) or not self.source_fit_reason.strip():
            raise ElaborateError(
                "Elaborated Case Source-Fit reason must be nonempty text."
            )
        if self.rule_conformance != "CONFORMS":
            raise ElaborateError(
                "An accepted Elaborate Case collection must conform to every "
                "Source Rule."
            )
        indexes = self.conforming_source_rule_indexes
        if (
            not isinstance(indexes, tuple)
            or not indexes
            or len(indexes) != len(set(indexes))
            or any(type(index) is not int or index < 1 for index in indexes)
        ):
            raise ElaborateError(
                "Elaborated Case conforming Source Rule indexes are invalid."
            )


@dataclass(frozen=True)
class ElaboratedCase:
    uid: str
    proposition: str
    expected: str
    rationale: str
    case_role: str
    rule_checks: tuple[ElaboratedRuleCheck, ...]
    target_context_refs: tuple[str, ...] = ()
    validation: ElaboratedCaseValidation | None = None

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.uid)
        except (AttributeError, TypeError, ValueError) as error:
            raise ElaborateError("Elaborated Case uid must be a UUID.") from error
        if not isinstance(self.proposition, str) or not self.proposition.strip():
            raise ElaborateError("Elaborated Case proposition must be nonempty text.")
        if not isinstance(self.expected, str) or not self.expected.strip():
            raise ElaborateError("Elaborated Case expected value must be nonempty text.")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ElaborateError("Elaborated Case rationale must be nonempty text.")
        if self.case_role not in {"FIT", "BOUNDARY", "CONTRAST"}:
            raise ElaborateError("Elaborated Case role is invalid.")
        indexes = tuple(check.source_rule_index for check in self.rule_checks)
        if not indexes or len(indexes) != len(set(indexes)):
            raise ElaborateError(
                "Elaborated Case must check source Rules exactly once."
            )
        if (
            not isinstance(self.target_context_refs, tuple)
            or len(set(self.target_context_refs)) != len(self.target_context_refs)
            or any(not isinstance(alias, str) or not alias for alias in self.target_context_refs)
        ):
            raise ElaborateError("Elaborated Case Target references are invalid.")
        if self.validation is not None and not isinstance(
            self.validation, ElaboratedCaseValidation
        ):
            raise ElaborateError("Elaborated Case validation is invalid.")


@dataclass(frozen=True)
class ElaborateAnalysis:
    uid: str
    mode: ElaborateMode
    inputs: tuple[str, ...]
    overview: str
    rules: tuple[ElaboratedRule, ...] = ()
    cases: tuple[ElaboratedCase, ...] = ()
    goal_focus: FrozenGoalFocus | None = None
    target_context: ElaborateTargetContext | None = None
    number: int | None = None
    quality_policy: ElaborateQualityPolicy = ElaborateQualityPolicy.BEST_EFFORT
    semantic_config: ElaborateSemanticConfig = DEFAULT_ELABORATE_SEMANTIC_CONFIG
    provider_contract_version: int = ELABORATE_PROVIDER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.uid)
        except (AttributeError, TypeError, ValueError) as error:
            raise ElaborateError("Elaborate analysis uid must be a UUID.") from error
        if not isinstance(self.mode, ElaborateMode) or not self.inputs:
            raise ElaborateError("Elaborate analysis input is invalid.")
        if not isinstance(self.overview, str) or not self.overview.strip():
            raise ElaborateError("Elaborate overview must be nonempty text.")
        if self.goal_focus is not None and not isinstance(
            self.goal_focus,
            FrozenGoalFocus,
        ):
            raise ElaborateError("Elaborate Goal focus must be a typed frame.")
        if self.mode is ElaborateMode.GOAL_TO_RULES:
            if self.cases:
                raise ElaborateError("Goal elaboration returned an invalid proposal set.")
            if not self.rules:
                raise ElaborateError(
                    "Goal elaboration requires at least one Rule proposal."
                )
        else:
            if self.rules:
                raise ElaborateError("Rule elaboration returned an invalid proposal set.")
            if not self.cases:
                raise ElaborateError(
                    "Rule elaboration requires at least one Case proposal."
                )
        proposals = (*self.rules, *self.cases)
        if len({item.uid for item in proposals}) != len(proposals):
            raise ElaborateError("Elaborate returned duplicate proposal identities.")
        # Proposal identity is positional and UID-backed, not content-backed.
        # Repeated content may be the intended exact-count result, and the Add
        # boundary gives every occurrence its own durable Memory identity.
        required_rule_indexes = tuple(range(1, len(self.inputs) + 1))
        if any(
            tuple(check.source_rule_index for check in item.rule_checks)
            != required_rule_indexes
            for item in self.cases
        ):
            # A Case is one joint model of the Rule frame. A partial citation
            # would restore the former one-Rule-per-Case behavior while looking
            # structurally valid to public adapters.
            raise ElaborateError(
                "Every Elaborate Case must check every source Rule exactly once "
                "in input order."
            )
        if not isinstance(self.quality_policy, ElaborateQualityPolicy):
            raise ElaborateError("Elaborate quality policy is invalid.")
        if self.mode is ElaborateMode.GOAL_TO_RULES and (
            self.quality_policy is ElaborateQualityPolicy.STRICT
        ):
            raise ElaborateError(
                "Strict Elaborate applies only when generating Cases from Rules."
            )
        if self.quality_policy is ElaborateQualityPolicy.STRICT:
            if any(
                item.validation is None
                or item.validation.conforming_source_rule_indexes
                != required_rule_indexes
                for item in self.cases
            ):
                raise ElaborateError(
                    "Every strict Elaborate Case must belong to a collection that "
                    "conforms to every Source Rule and Fits the complete Source frame."
                )
        elif any(item.validation is not None for item in self.cases):
            # Validation is not an incidental annotation: retaining it would
            # falsely imply that the best-effort route paid the strict gate.
            raise ElaborateError(
                "Best-effort Elaborate Cases cannot retain strict validation."
            )
        if self.provider_contract_version != ELABORATE_PROVIDER_CONTRACT_VERSION:
            raise ElaborateError("Unsupported Elaborate provider contract version.")
        if not isinstance(self.semantic_config, ElaborateSemanticConfig):
            raise ElaborateError("Elaborate analysis has an invalid semantic config.")
        number = normalize_elaborate_number(
            mode=self.mode,
            number=self.number,
            config=self.semantic_config,
        )
        proposal_count = (
            len(self.rules)
            if self.mode is ElaborateMode.GOAL_TO_RULES
            else len(self.cases)
        )
        if proposal_count != number:
            raise ElaborateError(
                f"Elaborate analysis requires exactly {number} proposals."
            )
        if self.target_context is not None and not isinstance(
            self.target_context, ElaborateTargetContext
        ):
            raise ElaborateError("Elaborate analysis Target Context is invalid.")
        available_target_aliases = (
            set(self.target_context.aliases) if self.target_context is not None else set()
        )
        proposal_refs = (
            *(rule.target_context_refs for rule in self.rules),
            *(case.target_context_refs for case in self.cases),
        )
        if any(not set(refs).issubset(available_target_aliases) for refs in proposal_refs):
            raise ElaborateError(
                "An Elaborate proposal cited an unavailable Target Context item."
            )

    @property
    def digest(self) -> str:
        payload = {
            "mode": self.mode.value,
            "inputs": list(self.inputs),
            "overview": self.overview,
            "rules": [
                {
                    "content": rule.content,
                    "rationale": rule.rationale,
                    "target_context_refs": list(rule.target_context_refs),
                }
                for rule in self.rules
            ],
            "cases": [
                {
                    "proposition": case.proposition,
                    "expected": case.expected,
                    "rationale": case.rationale,
                    "case_role": case.case_role,
                    "rule_checks": [
                        {
                            "source_rule_index": check.source_rule_index,
                            "evidence": check.evidence,
                        }
                        for check in case.rule_checks
                    ],
                    "target_context_refs": list(case.target_context_refs),
                    "validation": (
                        None
                        if case.validation is None
                        else {
                            "source_fit": case.validation.source_fit,
                            "source_fit_reason": case.validation.source_fit_reason,
                            "rule_conformance": case.validation.rule_conformance,
                            "conforming_source_rule_indexes": list(
                                case.validation.conforming_source_rule_indexes
                            ),
                        }
                    ),
                }
                for case in self.cases
            ],
            "target_context": (
                None
                if self.target_context is None
                else self.target_context.prompt_record()
            ),
            "goal_focus": (
                None if self.goal_focus is None else self.goal_focus.receipt_record()
            ),
            "number": self.number,
            "quality_policy": self.quality_policy.value,
            "semantic_config": {
                "default_proposal_count": self.semantic_config.default_proposal_count,
                "max_rule_proposals": self.semantic_config.max_rule_proposals,
                "max_case_proposals": self.semantic_config.max_case_proposals,
                "text_limit": self.semantic_config.text_limit,
                "rationale_limit": self.semantic_config.rationale_limit,
                "overview_limit": self.semantic_config.overview_limit,
                "response_char_limit": self.semantic_config.response_char_limit,
            },
            "provider_contract_version": self.provider_contract_version,
        }
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()


def validate_elaborate_analysis(
    analysis: ElaborateAnalysis,
    *,
    config: ElaborateSemanticConfig = DEFAULT_ELABORATE_SEMANTIC_CONFIG,
) -> None:
    """Revalidate live or prepared proposals against the active contract."""

    if not isinstance(analysis, ElaborateAnalysis):
        raise ElaborateError("Elaborate returned an invalid analysis.")
    if not isinstance(config, ElaborateSemanticConfig):
        raise TypeError("Elaborate requires an ElaborateSemanticConfig.")
    if analysis.semantic_config != config:
        raise ElaborateError(
            "The prepared Elaborate analysis semantic config does not match the request."
        )
    _text(analysis.overview, "overview", limit=config.overview_limit)
    number = normalize_elaborate_number(
        mode=analysis.mode,
        number=analysis.number,
        config=config,
    )
    if analysis.mode is ElaborateMode.GOAL_TO_RULES:
        if not analysis.rules:
            raise ElaborateError(
                "Elaborate requires at least one Rule proposal."
            )
        if (
            config.max_rule_proposals is not None
            and len(analysis.rules) > config.max_rule_proposals
        ):
            raise ElaborateError("Elaborate returned too many Rule proposals.")
        if len(analysis.rules) != number:
            raise ElaborateError(
                f"Elaborate requires exactly {number} Rule proposals."
            )
        for rule in analysis.rules:
            _text(rule.content, "Rule content", limit=config.text_limit)
            _text(rule.rationale, "Rule rationale", limit=config.rationale_limit)
    else:
        if not analysis.cases:
            raise ElaborateError(
                "Elaborate requires at least one Case proposal."
            )
        if (
            config.max_case_proposals is not None
            and len(analysis.cases) > config.max_case_proposals
        ):
            raise ElaborateError("Elaborate returned too many Case proposals.")
        if len(analysis.cases) != number:
            raise ElaborateError(
                f"Elaborate requires exactly {number} Case proposals."
            )
        for case in analysis.cases:
            _text(
                case.proposition,
                "Case proposition",
                limit=_case_validation_text_limit(config),
            )
            _text(
                case.expected,
                "Case expected value",
                limit=config.text_limit,
            )
            _text(case.rationale, "Case rationale", limit=config.rationale_limit)
            for check in case.rule_checks:
                _text(
                    check.evidence,
                    "Case Rule-check evidence",
                    limit=config.rationale_limit,
                )




def _case_validation_text_limit(config: ElaborateSemanticConfig) -> int:
    return min(
        config.text_limit,
        CONFORMANCE_TEXT_LIMIT,
        FIT_JUDGMENT_TEXT_LIMIT,
    )


def __getattr__(name: str):
    """Preserve historical provider entry points without reversing ownership."""

    if name == "analyze_elaborate":
        from memcommit.application.operations.elaborate.generation import (
            analyze_elaborate,
        )

        globals()[name] = analyze_elaborate
        return analyze_elaborate
    if name == "validate_elaborate_provider_plan":
        from memcommit.application.operations.elaborate.provider_contract import (
            validate_elaborate_provider_plan,
        )

        globals()[name] = validate_elaborate_provider_plan
        return validate_elaborate_provider_plan
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ELABORATE_OPERATION",
    "ELABORATE_PAYLOAD_MARKER",
    "ElaborateAnalysis",
    "ElaborateError",
    "ElaborateMode",
    "ElaborateProvider",
    "ElaborateQualityPolicy",
    "ElaboratedCase",
    "ElaboratedCaseValidation",
    "ElaboratedRuleCheck",
    "ElaboratedRule",
    "ElaborateTargetContext",
    "ElaborateTargetContextItem",
    "analyze_elaborate",  # noqa: F822 - resolved by the compatibility __getattr__
    "normalize_elaborate_inputs",
    "normalize_elaborate_number",
    "validate_elaborate_provider_plan",  # noqa: F822 - lazy compatibility export
    "validate_elaborate_analysis",
]
