"""Operation-neutral values for semantic execution planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionStrategy(str, Enum):
    """How an operation may preserve meaning after one-shot bounds are crossed."""

    TOP_K_RERANK = "TOP_K_RERANK"
    COVERAGE_MAP = "COVERAGE_MAP"
    BLOCK_RELATIONS = "BLOCK_RELATIONS"
    MAP_PLUS_GLOBAL = "MAP_PLUS_GLOBAL"
    HIERARCHICAL_REDUCE = "HIERARCHICAL_REDUCE"
    WHOLE_FRAME_ONLY = "WHOLE_FRAME_ONLY"


class ExecutionMode(str, Enum):
    """The host-visible shape selected for one frozen workload."""

    ONE_SHOT = "ONE_SHOT"
    STAGED = "STAGED"
    REJECTED = "REJECTED"


_BUDGET_AXES = (
    "input_chars",
    "item_count",
    "schema_chars",
    "expected_output_items",
    "relation_edges",
)


@dataclass(frozen=True)
class BudgetVector:
    """Measured semantic workload across independent capacity axes."""

    input_chars: int = 0
    item_count: int = 0
    schema_chars: int = 0
    expected_output_items: int = 0
    relation_edges: int = 0

    def __post_init__(self) -> None:
        for axis in _BUDGET_AXES:
            value = getattr(self, axis)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"Semantic budget {axis} must be a nonnegative integer.")

    def __add__(self, other: object) -> "BudgetVector":
        if not isinstance(other, BudgetVector):
            return NotImplemented
        return BudgetVector(
            **{
                axis: getattr(self, axis) + getattr(other, axis)
                for axis in _BUDGET_AXES
            }
        )


@dataclass(frozen=True)
class BudgetLimits:
    """One-shot ceilings; ``None`` leaves an axis unbounded by this policy."""

    max_input_chars: int | None = None
    max_items: int | None = None
    max_schema_chars: int | None = None
    max_output_items: int | None = None
    max_relation_edges: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "max_input_chars",
            "max_items",
            "max_schema_chars",
            "max_output_items",
            "max_relation_edges",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(
                    f"Semantic execution limit {field_name} must be nonnegative."
                )

    def exceeded_axes(self, workload: BudgetVector) -> tuple[str, ...]:
        comparisons = (
            ("input_chars", workload.input_chars, self.max_input_chars),
            ("item_count", workload.item_count, self.max_items),
            ("schema_chars", workload.schema_chars, self.max_schema_chars),
            (
                "expected_output_items",
                workload.expected_output_items,
                self.max_output_items,
            ),
            ("relation_edges", workload.relation_edges, self.max_relation_edges),
        )
        return tuple(
            axis
            for axis, measured, limit in comparisons
            if limit is not None and measured > limit
        )


@dataclass(frozen=True)
class SemanticExecutionPolicy:
    """An operation's declared one-shot boundary and staged semantic strategy."""

    operation: str
    strategy: ExecutionStrategy
    one_shot_limits: BudgetLimits
    # A strategy is a semantic declaration, not evidence that its operation
    # reconciler exists. Callers must opt in only after that adapter is tested.
    staged_supported: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise ValueError("Semantic execution policy requires an operation name.")
        if not isinstance(self.strategy, ExecutionStrategy):
            raise ValueError("Semantic execution policy requires a known strategy.")
        if not isinstance(self.one_shot_limits, BudgetLimits):
            raise ValueError("Semantic execution policy requires budget limits.")
        if not isinstance(self.staged_supported, bool):
            raise ValueError("Semantic execution staged support must be boolean.")
        if self.strategy is ExecutionStrategy.WHOLE_FRAME_ONLY and self.staged_supported:
            raise ValueError("Whole-frame-only operations cannot advertise staged support.")


@dataclass(frozen=True)
class ExecutionPlan:
    """Deterministic plan for one already-frozen semantic workload."""

    policy: SemanticExecutionPolicy
    workload: BudgetVector
    mode: ExecutionMode
    exceeded_axes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.policy, SemanticExecutionPolicy):
            raise ValueError("Semantic execution plan requires a policy.")
        if not isinstance(self.workload, BudgetVector):
            raise ValueError("Semantic execution plan requires a workload.")
        if not isinstance(self.mode, ExecutionMode):
            raise ValueError("Semantic execution plan requires a mode.")
        if len(self.exceeded_axes) != len(set(self.exceeded_axes)) or any(
            axis not in _BUDGET_AXES for axis in self.exceeded_axes
        ):
            raise ValueError("Semantic execution plan has invalid exceeded axes.")
        if self.mode is ExecutionMode.ONE_SHOT and self.exceeded_axes:
            raise ValueError("A one-shot plan cannot exceed its declared budget.")
        if self.mode is not ExecutionMode.ONE_SHOT and not self.exceeded_axes:
            raise ValueError("A non-one-shot plan must name an exceeded budget axis.")
