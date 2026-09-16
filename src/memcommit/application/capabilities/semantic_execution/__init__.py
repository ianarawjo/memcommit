"""Operation-aware planning for bounded semantic provider work."""

from memcommit.application.capabilities.semantic_execution.budgeting import json_budget
from memcommit.application.capabilities.semantic_execution.coverage import (
    CoverageError,
    InputCoverageLedger,
    decode_exact_source_assignments,
    exact_source_assignment_schema,
)
from memcommit.application.capabilities.semantic_execution.execution import (
    ExecutionProgress,
    run_partitioned,
)
from memcommit.application.capabilities.semantic_execution.model import (
    BudgetLimits,
    BudgetVector,
    ExecutionMode,
    ExecutionPlan,
    ExecutionStrategy,
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
    SemanticExecutionPolicy,
)
from memcommit.application.capabilities.semantic_execution.partitioning import (
    PartitionError,
    pack_grouped_items,
)
from memcommit.application.capabilities.semantic_execution.planning import plan_semantic_execution
from memcommit.application.capabilities.semantic_execution.relations import (
    RelationBlock,
    RelationScheduleError,
    build_relation_block_matrix,
    connected_relation_components,
)

__all__ = [
    "BudgetLimits",
    "BudgetVector",
    "CoverageError",
    "ExecutionMode",
    "ExecutionPlan",
    "ExecutionProgress",
    "ExecutionStrategy",
    "InputCoverageLedger",
    "PartitionError",
    "RelationBlock",
    "RelationScheduleError",
    "SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT",
    "SemanticExecutionPolicy",
    "json_budget",
    "build_relation_block_matrix",
    "connected_relation_components",
    "decode_exact_source_assignments",
    "exact_source_assignment_schema",
    "pack_grouped_items",
    "plan_semantic_execution",
    "run_partitioned",
]
