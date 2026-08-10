"""Operation-aware planning for bounded semantic provider work."""

from memcommit.semantic_execution.budgeting import json_budget
from memcommit.semantic_execution.coverage import CoverageError, InputCoverageLedger
from memcommit.semantic_execution.execution import (
    ExecutionProgress,
    run_partitioned,
)
from memcommit.semantic_execution.model import (
    BudgetLimits,
    BudgetVector,
    ExecutionMode,
    ExecutionPlan,
    ExecutionStrategy,
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
    SemanticExecutionPolicy,
)
from memcommit.semantic_execution.partitioning import (
    PartitionError,
    pack_grouped_items,
)
from memcommit.semantic_execution.planning import plan_semantic_execution
from memcommit.semantic_execution.relations import (
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
    "pack_grouped_items",
    "plan_semantic_execution",
    "run_partitioned",
]
