"""Memory provenance generation."""

from __future__ import annotations

from typing import Callable

from memcommit.application.capabilities.history.query.memory_history_slicing import (
    MemoryHistory,
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
from memcommit.application.operations.rationale.skills.memory_rationale.prompt import (
    RATIONALE_PROVENANCE_OPERATION,
    _preferred_length_target,
    _prompt,
    rationale_provenance_payload,
)
from memcommit.application.operations.rationale.skills.memory_rationale.response import (
    RationaleNarrativeProjection,
    _output_schema,
    _parse_projection,
    _RationaleLimitExceeded,
)

RATIONALE_PROVENANCE_REPAIR_OPERATION = "rationale provenance repair"


RATIONALE_EXECUTION_POLICY = SemanticExecutionPolicy(
    operation=RATIONALE_PROVENANCE_OPERATION,
    strategy=ExecutionStrategy.WHOLE_FRAME_ONLY,
    one_shot_limits=BudgetLimits(max_input_chars=SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT),
    # Process the full history in one call.
    staged_supported=False,
)


def generate_memory_rationale(
    trace: MemoryHistory,
    *,
    provider_factory: Callable[[], RationaleSemanticProvider],
    history_available: bool = True,
    limit: int = DEFAULT_RATIONALE_PROVENANCE_LIMIT,
    unit: RationaleLimitUnit = RationaleLimitUnit.WORDS,
) -> RationaleNarrativeProjection:
    """Generate a Memory explanation, with one retry for excess length."""

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
        )
    # Return EMPTY when there are no retained records.
    if not trace.records:
        return RationaleNarrativeProjection(
            status=RationaleNarrativeStatus.EMPTY,
            text="",
            limit=limit,
            unit=unit,
            length=0,
        )
    # Build the model input.
    payload = rationale_provenance_payload(trace, limit=limit, unit=unit)
    # Define the response format.
    schema = _output_schema(limit=limit, unit=unit)
    # Calculate the input budget and execution plan.
    plan = plan_semantic_execution(
        RATIONALE_EXECUTION_POLICY,
        json_budget(
            payload,
            item_count=len(trace.records) + len(trace.component_uids),
            output_schema=schema,
            expected_output_items=1,
        ),
    )
    # Reject input that cannot fit in one call.
    if plan.mode is not ExecutionMode.ONE_SHOT:
        raise RationaleSynthesisError(
            "The complete Rationale Trace exceeds its whole-frame semantic plan "
            f"({', '.join(plan.exceeded_axes)})."
        )
    # Create the model provider.
    provider = provider_factory()
    # Request the explanation.
    raw = provider.complete(
        _prompt(payload),
        operation=RATIONALE_PROVENANCE_OPERATION,
        output_schema=schema,
    )
    # Check the response format and length.
    try:
        return _parse_projection(raw, limit=limit, unit=unit)
    except _RationaleLimitExceeded as overflow:
        # Add the rejected draft and length target to the original input.
        repair_payload = {
            **payload,
            "repair": {
                "reason": "OVER_LIMIT",
                "rejected_provenance": overflow.text,
                "measured_length": overflow.length,
                "target": _preferred_length_target(limit),
                "limit": limit,
                "unit": unit.value,
            },
        }
        # Check the size of the repair request.
        repair_plan = plan_semantic_execution(
            RATIONALE_EXECUTION_POLICY,
            json_budget(
                repair_payload,
                item_count=len(trace.records) + len(trace.component_uids) + 1,
                output_schema=schema,
                expected_output_items=1,
            ),
        )
        # Reject a repair request that exceeds the input budget.
        if repair_plan.mode is not ExecutionMode.ONE_SHOT:
            raise RationaleSynthesisError(
                "The complete Rationale length-repair frame exceeds its whole-frame "
                f"semantic plan ({', '.join(repair_plan.exceeded_axes)})."
            ) from overflow
        # Request a shorter explanation once.
        repaired_raw = provider.complete(
            _prompt(repair_payload),
            operation=RATIONALE_PROVENANCE_REPAIR_OPERATION,
            output_schema=schema,
        )
        # Validate the revised explanation.
        try:
            return _parse_projection(repaired_raw, limit=limit, unit=unit)
        # Fail if the revised explanation still exceeds the length limit.
        except _RationaleLimitExceeded as repair_overflow:
            raise RationaleSynthesisError(
                "The Rationale provider exceeded the requested complete-narrative "
                f"limit of {limit} {unit.value} after one whole-Trace length repair."
            ) from repair_overflow
