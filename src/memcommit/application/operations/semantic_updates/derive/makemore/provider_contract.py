"""Provider schema, budgeting, and one-shot planning for Makemore."""

from __future__ import annotations

from memcommit.application.operations.quality_resolution.validate.check_conformance.model import (
    CONFORMANCE_MAX_RULES,
    CONFORMANCE_MAX_SUBJECTS,
)
from memcommit.application.operations.semantic_updates.derive.makemore.config import (
    DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
    MakemoreSemanticConfig,
)
from memcommit.application.operations.semantic_updates.derive.makemore.model import (
    MAKEMORE_OPERATION,
    MakemoreError,
    MakemoreMode,
    MakemoreTargetContext,
    _case_validation_text_limit,
    normalize_makemore_number,
)
from memcommit.application.operations.quality_resolution.validate.fit.judgment import FIT_JUDGMENT_MAX_ITEMS
from memcommit.application.capabilities.semantic.generative_reduction_reference import (
    distill_makemore_reference_payload,
)
from memcommit.application.capabilities.semantic.goal_focus import FrozenGoalFocus
from memcommit.application.capabilities.semantic_execution import (
    BudgetLimits,
    ExecutionMode,
    ExecutionStrategy,
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
    SemanticExecutionPolicy,
    json_budget,
    plan_semantic_execution,
)
from memcommit.application.capabilities.semantic.prompt_policy import resolve_semantic_prompt_policy


def makemore_execution_policy(
    *,
    mode: MakemoreMode,
    config: MakemoreSemanticConfig,
) -> SemanticExecutionPolicy:
    maximum = (
        config.max_rule_proposals
        if mode is MakemoreMode.GOAL_TO_RULES
        else config.max_case_proposals
    )
    return SemanticExecutionPolicy(
        operation=MAKEMORE_OPERATION,
        strategy=ExecutionStrategy.WHOLE_FRAME_ONLY,
        one_shot_limits=BudgetLimits(
            max_input_chars=SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
            max_output_items=maximum,
        ),
        staged_supported=False,
    )


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MakemoreError(f"Makemore returned duplicate JSON key {key!r}.")
        result[key] = value
    return result


def _schema(
    mode: MakemoreMode,
    *,
    input_count: int,
    target_context: MakemoreTargetContext | None,
    number: int,
    strict: bool,
    config: MakemoreSemanticConfig,
) -> dict[str, object]:
    text = {"type": "string", "minLength": 1, "maxLength": config.text_limit}
    rationale = {
        "type": "string",
        "minLength": 1,
        "maxLength": config.rationale_limit,
    }
    properties: dict[str, object] = {
        "overview": {
            "type": "string",
            "minLength": 1,
            "maxLength": config.overview_limit,
        }
    }
    target_aliases = () if target_context is None else target_context.aliases
    target_ref_item: dict[str, object] = {"type": "string"}
    if target_aliases:
        target_ref_item["enum"] = list(target_aliases)
    target_refs = {
        "type": "array",
        "minItems": 0,
        "maxItems": len(target_aliases),
        # Codex strict output does not accept JSON-Schema uniqueItems. The
        # local decoder independently rejects duplicate Target aliases.
        "items": target_ref_item,
    }
    if mode is MakemoreMode.GOAL_TO_RULES:
        rule_required = ["content", "rationale"]
        rule_properties: dict[str, object] = {
            "content": text,
            "rationale": rationale,
        }
        if target_context is not None:
            rule_required.append("target_context_refs")
            rule_properties["target_context_refs"] = target_refs
        properties["rules"] = {
            "type": "array",
            "minItems": number,
            "maxItems": number,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": rule_required,
                "properties": rule_properties,
            },
        }
        required = ["overview", "rules"]
    else:
        case_text = {
            "type": "string",
            "minLength": 1,
            "maxLength": (
                _case_validation_text_limit(config) if strict else config.text_limit
            ),
        }
        case_required = [
            "proposition",
            "expected",
            "rationale",
            "case_role",
            "rule_checks",
        ]
        case_properties: dict[str, object] = {
            "proposition": case_text,
            "expected": {
                "type": "string",
                "minLength": 1,
                "maxLength": config.text_limit,
            },
            "rationale": rationale,
            "case_role": {
                "type": "string",
                "enum": ["FIT", "BOUNDARY", "CONTRAST"],
            },
            "rule_checks": {
                "type": "array",
                "minItems": input_count,
                "maxItems": input_count,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["source_rule_index", "evidence"],
                    "properties": {
                        "source_rule_index": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": input_count,
                        },
                        "evidence": rationale,
                    },
                },
            },
        }
        if target_context is not None:
            case_required.append("target_context_refs")
            case_properties["target_context_refs"] = target_refs
        properties["cases"] = {
            "type": "array",
            "minItems": number,
            "maxItems": number,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": case_required,
                "properties": case_properties,
            },
        }
        required = ["overview", "cases"]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def validate_makemore_provider_plan(
    *,
    mode: MakemoreMode,
    inputs: tuple[str, ...],
    goal_focus: FrozenGoalFocus | None = None,
    target_context: MakemoreTargetContext | None = None,
    number: int | None = None,
    strict: bool = False,
    config: MakemoreSemanticConfig = DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
) -> None:
    """Reject an oversized live request before provider construction."""

    if not isinstance(mode, MakemoreMode) or not inputs:
        raise MakemoreError("Makemore provider planning requires normalized input.")
    if not isinstance(config, MakemoreSemanticConfig):
        raise TypeError("Makemore requires an MakemoreSemanticConfig.")
    number = normalize_makemore_number(mode=mode, number=number, config=config)
    if type(strict) is not bool:
        raise MakemoreError("Makemore strict mode must be boolean.")
    if strict and mode is not MakemoreMode.RULES_TO_CASES:
        raise MakemoreError(
            "Strict Makemore applies only when generating Cases from Rules."
        )
    if strict and mode is MakemoreMode.RULES_TO_CASES:
        target_memories = tuple(
            item
            for item in (() if target_context is None else target_context.items)
            if item.kind == "MEMORY"
        )
        target_memory_count = len(target_memories)
        validation_subjects = number + target_memory_count
        validation_items = len(inputs) + validation_subjects
        if (
            len(inputs) > CONFORMANCE_MAX_RULES
            or validation_subjects > CONFORMANCE_MAX_SUBJECTS
            or validation_items > FIT_JUDGMENT_MAX_ITEMS
        ):
            raise MakemoreError(
                "The complete Makemore Case validation frame exceeds its "
                "bounded whole-frame plan."
            )
        validation_text_limit = _case_validation_text_limit(config)
        if any(len(value) > validation_text_limit for value in inputs):
            raise MakemoreError(
                "An Makemore Source Rule exceeds the shared Conformance/Fit "
                f"{validation_text_limit}-character limit."
            )
        if any(
            item.content is None or len(item.content) > validation_text_limit
            for item in target_memories
        ):
            raise MakemoreError(
                "An Makemore Target Memory exceeds the shared Conformance/Fit "
                f"{validation_text_limit}-character limit."
            )
    payload: dict[str, object] = {"mode": mode.value, "inputs": list(inputs)}
    payload["number"] = number
    if goal_focus is not None:
        payload["goal_focus"] = goal_focus.prompt_record()
    if target_context is not None:
        payload["target_context"] = target_context.prompt_record()
    schema = _schema(
        mode,
        input_count=len(inputs),
        target_context=target_context,
        number=number,
        strict=strict,
        config=config,
    )
    expected = number
    prompt_policy = resolve_semantic_prompt_policy()
    plan_payload: dict[str, object] = {
        "reference_examples": distill_makemore_reference_payload(
            include_examples=prompt_policy.include_authored_examples,
        ),
        "request": payload,
    }
    if not prompt_policy.include_authored_examples:
        plan_payload["prompt_policy"] = prompt_policy.to_prompt_record()
    plan = plan_semantic_execution(
        makemore_execution_policy(mode=mode, config=config),
        json_budget(
            plan_payload,
            item_count=len(inputs) + (0 if goal_focus is None else len(goal_focus.items)),
            output_schema=schema,
            expected_output_items=expected,
        ),
    )
    if plan.mode is not ExecutionMode.ONE_SHOT:
        raise MakemoreError(
            "The complete Makemore request exceeds its bounded one-turn plan "
            f"({', '.join(plan.exceeded_axes)})."
        )


__all__ = ["makemore_execution_policy", "validate_makemore_provider_plan"]
