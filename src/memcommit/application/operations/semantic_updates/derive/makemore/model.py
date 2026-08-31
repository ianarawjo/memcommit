"""Exact-count top-down Rule and Case proposal models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Protocol
import uuid

from memcommit.application.operations.quality_resolution.validate.check_conformance.model import (
    CONFORMANCE_TEXT_LIMIT,
)
from memcommit.application.operations.semantic_updates.derive.makemore.config import (
    DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
    MakemoreSemanticConfig,
)
from memcommit.application.operations.quality_resolution.validate.fit.judgment import (
    FIT_JUDGMENT_TEXT_LIMIT,
)
from memcommit.application.capabilities.semantic.goal_focus import FrozenGoalFocus


MAKEMORE_OPERATION = "makemore"
MAKEMORE_PROVIDER_CONTRACT_VERSION = 14
MAKEMORE_PAYLOAD_MARKER = "MAKEMORE PAYLOAD:\n"


class MakemoreMode(str, Enum):
    GOAL_TO_RULES = "GOAL_TO_RULES"
    RULES_TO_CASES = "RULES_TO_CASES"


class MakemoreQualityPolicy(str, Enum):
    """Whether generated Cases are suggestions or independently gated."""

    BEST_EFFORT = "BEST_EFFORT"
    STRICT = "STRICT"


class MakemoreError(RuntimeError):
    """Safe failure from one bounded Makemore request."""


class MakemoreProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one strict proposal envelope."""


@dataclass(frozen=True)
class MakemoreTargetContextItem:
    """One bounded Target-side ambient item exposed to Makemore."""

    alias: str
    kind: str
    context_name: str
    memory_uid: str | None = None
    content: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.alias, str) or not self.alias.startswith("t"):
            raise MakemoreError("Makemore Target item alias is invalid.")
        if self.kind not in {"MEMORY", "QUERY_ONLY_CONTEXT"}:
            raise MakemoreError("Makemore Target item kind is invalid.")
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise MakemoreError("Makemore Target item Context is invalid.")
        if self.kind == "MEMORY":
            if not isinstance(self.memory_uid, str) or not self.memory_uid:
                raise MakemoreError("Makemore Target Memory identity is invalid.")
            if not isinstance(self.content, str) or not self.content.strip():
                raise MakemoreError("Makemore Target Memory content is invalid.")
        elif self.memory_uid is not None or self.content is not None:
            # A query-only route contributes orientation by public name only.
            # Retaining hidden identity or content here would make a later
            # prompt adapter capable of crossing the query boundary by accident.
            raise MakemoreError(
                "Makemore query-only Target items must remain name-only."
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
class MakemoreTargetContext:
    """The exact existing destination frame used only as ambient context."""

    context_name: str
    items: tuple[MakemoreTargetContextItem, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise MakemoreError("Makemore Target Context name is invalid.")
        if not isinstance(self.items, tuple):
            raise MakemoreError("Makemore Target Context items must be a tuple.")
        expected_aliases = tuple(f"t{index}" for index in range(1, len(self.items) + 1))
        if tuple(item.alias for item in self.items) != expected_aliases:
            raise MakemoreError(
                "Makemore Target Context aliases must be contiguous and ordered."
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
        raise MakemoreError(f"Makemore {label} must be text.")
    normalized = value.strip()
    if not normalized and not empty:
        raise MakemoreError(f"Makemore {label} must be nonempty text.")
    if len(normalized) > limit:
        raise MakemoreError(
            f"Makemore {label} exceeds its {limit}-character limit."
        )
    return normalized


def normalize_makemore_inputs(
    *,
    goal: str | None,
    rules: tuple[str, ...],
    config: MakemoreSemanticConfig = DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
) -> tuple[MakemoreMode, tuple[str, ...]]:
    """Choose exactly one top-down derivation direction."""

    if not isinstance(config, MakemoreSemanticConfig):
        raise TypeError("Makemore requires a MakemoreSemanticConfig.")
    if not isinstance(rules, tuple):
        raise MakemoreError("Makemore Rules must be a tuple.")
    normalized_rules = tuple(
        _text(rule, "Rule", limit=config.text_limit) for rule in rules
    )
    if len({rule.casefold() for rule in normalized_rules}) != len(normalized_rules):
        raise MakemoreError("Makemore Rules must be distinct.")
    normalized_goal = (
        None
        if goal is None
        else _text(goal, "Goal", limit=config.text_limit)
    )
    if normalized_goal is not None and normalized_rules:
        raise MakemoreError("Makemore accepts either one Goal or Rules, not both.")
    if normalized_goal is not None:
        return MakemoreMode.GOAL_TO_RULES, (normalized_goal,)
    if normalized_rules:
        return MakemoreMode.RULES_TO_CASES, normalized_rules
    raise MakemoreError("Makemore requires one Goal or at least one Rule.")


def normalize_makemore_number(
    *,
    mode: MakemoreMode,
    number: int | None,
    config: MakemoreSemanticConfig = DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
) -> int:
    """Resolve the default or explicit positive exact proposal count."""

    if not isinstance(mode, MakemoreMode):
        raise MakemoreError("Makemore proposal count requires a valid direction.")
    if not isinstance(config, MakemoreSemanticConfig):
        raise TypeError("Makemore requires a MakemoreSemanticConfig.")
    if number is None:
        number = config.default_proposal_count
    if type(number) is not int or number <= 0:
        raise MakemoreError("Makemore number must be a positive integer.")
    maximum = (
        config.max_rule_proposals
        if mode is MakemoreMode.GOAL_TO_RULES
        else config.max_case_proposals
    )
    if maximum is not None and number > maximum:
        label = "Rule" if mode is MakemoreMode.GOAL_TO_RULES else "Case"
        raise MakemoreError(
            f"Makemore {label} number must be between 1 and {maximum}."
        )
    return number


@dataclass(frozen=True)
class MakemoreRule:
    uid: str
    content: str
    rationale: str
    target_context_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.uid)
        except (AttributeError, TypeError, ValueError) as error:
            raise MakemoreError("Makemore Rule uid must be a UUID.") from error
        if not isinstance(self.content, str) or not self.content.strip():
            raise MakemoreError("Makemore Rule content must be nonempty text.")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise MakemoreError("Makemore Rule rationale must be nonempty text.")
        if (
            not isinstance(self.target_context_refs, tuple)
            or len(set(self.target_context_refs)) != len(self.target_context_refs)
            or any(not isinstance(alias, str) or not alias for alias in self.target_context_refs)
        ):
            raise MakemoreError("Makemore Rule Target references are invalid.")


@dataclass(frozen=True)
class MakemoreRuleCheck:
    source_rule_index: int
    evidence: str

    def __post_init__(self) -> None:
        if type(self.source_rule_index) is not int or self.source_rule_index < 1:
            raise MakemoreError("Makemore Rule check index is invalid.")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise MakemoreError("Makemore Rule check evidence must be nonempty text.")


@dataclass(frozen=True)
class MakemoreCaseValidation:
    """Collection Rule-conformance and Source-Fit retained on one Case."""

    source_fit: str
    source_fit_reason: str
    rule_conformance: str
    conforming_source_rule_indexes: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.source_fit != "YES":
            raise MakemoreError("An accepted Makemore Case must Fit its Source.")
        if not isinstance(self.source_fit_reason, str) or not self.source_fit_reason.strip():
            raise MakemoreError(
                "Makemore Case Source-Fit reason must be nonempty text."
            )
        if self.rule_conformance != "CONFORMS":
            raise MakemoreError(
                "An accepted Makemore Case collection must conform to every "
                "Source Rule."
            )
        indexes = self.conforming_source_rule_indexes
        if (
            not isinstance(indexes, tuple)
            or not indexes
            or len(indexes) != len(set(indexes))
            or any(type(index) is not int or index < 1 for index in indexes)
        ):
            raise MakemoreError(
                "Makemore Case conforming Source Rule indexes are invalid."
            )


@dataclass(frozen=True)
class MakemoreCase:
    uid: str
    proposition: str
    expected: str
    rationale: str
    case_role: str
    rule_checks: tuple[MakemoreRuleCheck, ...]
    target_context_refs: tuple[str, ...] = ()
    validation: MakemoreCaseValidation | None = None

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.uid)
        except (AttributeError, TypeError, ValueError) as error:
            raise MakemoreError("Makemore Case uid must be a UUID.") from error
        if not isinstance(self.proposition, str) or not self.proposition.strip():
            raise MakemoreError("Makemore Case proposition must be nonempty text.")
        if not isinstance(self.expected, str) or not self.expected.strip():
            raise MakemoreError("Makemore Case expected value must be nonempty text.")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise MakemoreError("Makemore Case rationale must be nonempty text.")
        if self.case_role not in {"FIT", "BOUNDARY", "CONTRAST"}:
            raise MakemoreError("Makemore Case role is invalid.")
        indexes = tuple(check.source_rule_index for check in self.rule_checks)
        if not indexes or len(indexes) != len(set(indexes)):
            raise MakemoreError(
                "Makemore Case must check source Rules exactly once."
            )
        if (
            not isinstance(self.target_context_refs, tuple)
            or len(set(self.target_context_refs)) != len(self.target_context_refs)
            or any(not isinstance(alias, str) or not alias for alias in self.target_context_refs)
        ):
            raise MakemoreError("Makemore Case Target references are invalid.")
        if self.validation is not None and not isinstance(
            self.validation, MakemoreCaseValidation
        ):
            raise MakemoreError("Makemore Case validation is invalid.")


@dataclass(frozen=True)
class MakemoreAnalysis:
    uid: str
    mode: MakemoreMode
    inputs: tuple[str, ...]
    overview: str
    rules: tuple[MakemoreRule, ...] = ()
    cases: tuple[MakemoreCase, ...] = ()
    goal_focus: FrozenGoalFocus | None = None
    target_context: MakemoreTargetContext | None = None
    number: int | None = None
    quality_policy: MakemoreQualityPolicy = MakemoreQualityPolicy.BEST_EFFORT
    semantic_config: MakemoreSemanticConfig = DEFAULT_MAKEMORE_SEMANTIC_CONFIG
    provider_contract_version: int = MAKEMORE_PROVIDER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.uid)
        except (AttributeError, TypeError, ValueError) as error:
            raise MakemoreError("Makemore analysis uid must be a UUID.") from error
        if not isinstance(self.mode, MakemoreMode) or not self.inputs:
            raise MakemoreError("Makemore analysis input is invalid.")
        if not isinstance(self.overview, str) or not self.overview.strip():
            raise MakemoreError("Makemore overview must be nonempty text.")
        if self.goal_focus is not None and not isinstance(
            self.goal_focus,
            FrozenGoalFocus,
        ):
            raise MakemoreError("Makemore Goal focus must be a typed frame.")
        if self.mode is MakemoreMode.GOAL_TO_RULES:
            if self.cases:
                raise MakemoreError("Goal elaboration returned an invalid proposal set.")
            if not self.rules:
                raise MakemoreError(
                    "Goal elaboration requires at least one Rule proposal."
                )
        else:
            if self.rules:
                raise MakemoreError("Rule elaboration returned an invalid proposal set.")
            if not self.cases:
                raise MakemoreError(
                    "Rule elaboration requires at least one Case proposal."
                )
        proposals = (*self.rules, *self.cases)
        if len({item.uid for item in proposals}) != len(proposals):
            raise MakemoreError("Makemore returned duplicate proposal identities.")
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
            raise MakemoreError(
                "Every Makemore Case must check every source Rule exactly once "
                "in input order."
            )
        if not isinstance(self.quality_policy, MakemoreQualityPolicy):
            raise MakemoreError("Makemore quality policy is invalid.")
        if self.mode is MakemoreMode.GOAL_TO_RULES and (
            self.quality_policy is MakemoreQualityPolicy.STRICT
        ):
            raise MakemoreError(
                "Strict Makemore applies only when generating Cases from Rules."
            )
        if self.quality_policy is MakemoreQualityPolicy.STRICT:
            if any(
                item.validation is None
                or item.validation.conforming_source_rule_indexes
                != required_rule_indexes
                for item in self.cases
            ):
                raise MakemoreError(
                    "Every strict Makemore Case must belong to a collection that "
                    "conforms to every Source Rule and Fits the complete Source frame."
                )
        elif any(item.validation is not None for item in self.cases):
            # Validation is not an incidental annotation: retaining it would
            # falsely imply that the best-effort route paid the strict gate.
            raise MakemoreError(
                "Best-effort Makemore Cases cannot retain strict validation."
            )
        if self.provider_contract_version != MAKEMORE_PROVIDER_CONTRACT_VERSION:
            raise MakemoreError("Unsupported Makemore provider contract version.")
        if not isinstance(self.semantic_config, MakemoreSemanticConfig):
            raise MakemoreError("Makemore analysis has an invalid semantic config.")
        number = normalize_makemore_number(
            mode=self.mode,
            number=self.number,
            config=self.semantic_config,
        )
        proposal_count = (
            len(self.rules)
            if self.mode is MakemoreMode.GOAL_TO_RULES
            else len(self.cases)
        )
        if proposal_count != number:
            raise MakemoreError(
                f"Makemore analysis requires exactly {number} proposals."
            )
        if self.target_context is not None and not isinstance(
            self.target_context, MakemoreTargetContext
        ):
            raise MakemoreError("Makemore analysis Target Context is invalid.")
        available_target_aliases = (
            set(self.target_context.aliases) if self.target_context is not None else set()
        )
        proposal_refs = (
            *(rule.target_context_refs for rule in self.rules),
            *(case.target_context_refs for case in self.cases),
        )
        if any(not set(refs).issubset(available_target_aliases) for refs in proposal_refs):
            raise MakemoreError(
                "A Makemore proposal cited an unavailable Target Context item."
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


def validate_makemore_analysis(
    analysis: MakemoreAnalysis,
    *,
    config: MakemoreSemanticConfig = DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
) -> None:
    """Revalidate live or prepared proposals against the active contract."""

    if not isinstance(analysis, MakemoreAnalysis):
        raise MakemoreError("Makemore returned an invalid analysis.")
    if not isinstance(config, MakemoreSemanticConfig):
        raise TypeError("Makemore requires a MakemoreSemanticConfig.")
    if analysis.semantic_config != config:
        raise MakemoreError(
            "The prepared Makemore analysis semantic config does not match the request."
        )
    _text(analysis.overview, "overview", limit=config.overview_limit)
    number = normalize_makemore_number(
        mode=analysis.mode,
        number=analysis.number,
        config=config,
    )
    if analysis.mode is MakemoreMode.GOAL_TO_RULES:
        if not analysis.rules:
            raise MakemoreError(
                "Makemore requires at least one Rule proposal."
            )
        if (
            config.max_rule_proposals is not None
            and len(analysis.rules) > config.max_rule_proposals
        ):
            raise MakemoreError("Makemore returned too many Rule proposals.")
        if len(analysis.rules) != number:
            raise MakemoreError(
                f"Makemore requires exactly {number} Rule proposals."
            )
        for rule in analysis.rules:
            _text(rule.content, "Rule content", limit=config.text_limit)
            _text(rule.rationale, "Rule rationale", limit=config.rationale_limit)
    else:
        if not analysis.cases:
            raise MakemoreError(
                "Makemore requires at least one Case proposal."
            )
        if (
            config.max_case_proposals is not None
            and len(analysis.cases) > config.max_case_proposals
        ):
            raise MakemoreError("Makemore returned too many Case proposals.")
        if len(analysis.cases) != number:
            raise MakemoreError(
                f"Makemore requires exactly {number} Case proposals."
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




def _case_validation_text_limit(config: MakemoreSemanticConfig) -> int:
    return min(
        config.text_limit,
        CONFORMANCE_TEXT_LIMIT,
        FIT_JUDGMENT_TEXT_LIMIT,
    )


def __getattr__(name: str):
    """Preserve historical provider entry points without reversing ownership."""

    if name == "analyze_makemore":
        from memcommit.application.operations.semantic_updates.derive.makemore.generation import (
            analyze_makemore,
        )

        globals()[name] = analyze_makemore
        return analyze_makemore
    if name == "validate_makemore_provider_plan":
        from memcommit.application.operations.semantic_updates.derive.makemore.provider_contract import (
            validate_makemore_provider_plan,
        )

        globals()[name] = validate_makemore_provider_plan
        return validate_makemore_provider_plan
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MAKEMORE_OPERATION",
    "MAKEMORE_PAYLOAD_MARKER",
    "MakemoreAnalysis",
    "MakemoreError",
    "MakemoreMode",
    "MakemoreProvider",
    "MakemoreQualityPolicy",
    "MakemoreCase",
    "MakemoreCaseValidation",
    "MakemoreRuleCheck",
    "MakemoreRule",
    "MakemoreTargetContext",
    "MakemoreTargetContextItem",
    "analyze_makemore",  # noqa: F822 - resolved by the compatibility __getattr__
    "normalize_makemore_inputs",
    "normalize_makemore_number",
    "validate_makemore_provider_plan",  # noqa: F822 - lazy compatibility export
    "validate_makemore_analysis",
]
