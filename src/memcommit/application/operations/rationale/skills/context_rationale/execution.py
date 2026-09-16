"""Context provenance generation."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.application.capabilities.history.query.context_history_slicing import (
    ContextHistorySlice,
)
from memcommit.application.capabilities.semantic_execution import (
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
    BudgetLimits,
    ExecutionMode,
    ExecutionStrategy,
    SemanticExecutionPolicy,
    json_budget,
    plan_semantic_execution,
)
from memcommit.application.operations.rationale.narrative_length_validation import (
    validate_rationale_limit,
)
from memcommit.application.operations.rationale.model import (
    DEFAULT_RATIONALE_PROVENANCE_LIMIT,
    RationaleLimitUnit,
    RationaleNarrativeStatus,
    RationaleSemanticProvider,
    RationaleSynthesisError,
)
from memcommit.application.operations.rationale.skills.context_rationale.prompt import (
    CONTEXT_RATIONALE_OPERATION,
    _prompt,
    context_rationale_payload,
)
from memcommit.application.operations.rationale.skills.context_rationale.rules import (
    CONTEXT_RATIONALE_RULESET_VERSION,
)
from memcommit.application.operations.rationale.skills.memory_rationale.response import (
    RationaleNarrativeProjection,
    parse_rationale_projection,
    rationale_output_schema,
)

CONTEXT_RATIONALE_POLICY = SemanticExecutionPolicy(
    operation=CONTEXT_RATIONALE_OPERATION,
    strategy=ExecutionStrategy.WHOLE_FRAME_ONLY,
    one_shot_limits=BudgetLimits(max_input_chars=SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT),
    # Process the full history in one call.
    staged_supported=False,
)


def generate_context_rationale(
    report: ContextHistorySlice,
    *,
    provider_factory: Callable[[], RationaleSemanticProvider],
    history_available: bool = True,
    limit: int = DEFAULT_RATIONALE_PROVENANCE_LIMIT,
    unit: RationaleLimitUnit = RationaleLimitUnit.WORDS,
) -> RationaleNarrativeProjection:
    """Generate a Context explanation with at most one model call."""

    # Validate the requested length and unit.
    unit = validate_rationale_limit(limit, unit)
    # Return HIDDEN when history is unavailable.
    if not history_available:
        return RationaleNarrativeProjection(
            status=RationaleNarrativeStatus.HIDDEN,
            text="",
            limit=limit,
            unit=unit,
            length=0,
            ruleset_version=CONTEXT_RATIONALE_RULESET_VERSION,
        )
    # Return EMPTY when there are no retained records.
    if not report.events:
        return RationaleNarrativeProjection(
            status=RationaleNarrativeStatus.EMPTY,
            text="",
            limit=limit,
            unit=unit,
            length=0,
            ruleset_version=CONTEXT_RATIONALE_RULESET_VERSION,
        )
    # Build the model input.
    payload = context_rationale_payload(report, limit=limit, unit=unit)
    # Define the response format.
    schema = rationale_output_schema(limit=limit, unit=unit)
    # Calculate the input budget and execution plan.
    plan = plan_semantic_execution(
        CONTEXT_RATIONALE_POLICY,
        json_budget(
            payload,
            item_count=len(report.events)
            + sum(len(event.changes) for event in report.events),
            output_schema=schema,
            expected_output_items=1,
        ),
    )
    # Reject input that cannot fit in one call.
    if plan.mode is not ExecutionMode.ONE_SHOT:
        raise RationaleSynthesisError(
            "The complete Context Rationale exceeds its whole-frame semantic "
            f"plan ({', '.join(plan.exceeded_axes)})."
        )
    # Create the model provider.
    provider = provider_factory()
    # Request the explanation.
    raw = provider.complete(
        _prompt(payload),
        operation=CONTEXT_RATIONALE_OPERATION,
        output_schema=schema,
    )
    # Validate the explanation and attach the Context ruleset version.
    return parse_rationale_projection(
        raw,
        limit=limit,
        unit=unit,
        ruleset_version=CONTEXT_RATIONALE_RULESET_VERSION,
    )
