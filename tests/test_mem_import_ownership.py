"""Ownership and compatibility contracts for the mem import operation."""

from __future__ import annotations

import ast
from pathlib import Path

from memcommit.application.operations.mem_import.context import (
    import_context_from_profile,
    plan_context_import,
)
from memcommit.application.operations.mem_import.contracts import (
    ContextImportPlan,
    MemoryImportPlan,
)
from memcommit.application.operations.mem_import.memory import (
    import_memory_from_profile,
    plan_memory_import,
)
from memcommit.application.operations.mem_import.profile import (
    baseline_store_digest,
    import_baseline_profile,
    import_profile_from_profile,
)
from memcommit.application.operations.profile import model as profile_model
from memcommit.application.operations.resource_import import model as legacy_model


REPOSITORY_ROOT = Path(__file__).parents[1]


def _imported_modules(relative_path: str) -> set[str]:
    path = REPOSITORY_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def test_mem_import_callers_use_resource_owning_modules() -> None:
    command_imports = _imported_modules(
        "src/memcommit/adapters/console/commands/import_profile/command.py"
    )
    workbench_imports = _imported_modules(
        "src/memcommit/adapters/console/commands/import_profile/workbench.py"
    )

    assert "memcommit.application.operations.resource_import.model" not in (
        command_imports | workbench_imports
    )
    assert {
        "memcommit.application.operations.mem_import.context",
        "memcommit.application.operations.mem_import.memory",
    } <= command_imports
    assert "memcommit.application.operations.mem_import.profile" in command_imports
    assert "memcommit.application.operations.mem_import.contracts" in workbench_imports


def test_resource_import_model_is_an_identity_preserving_facade() -> None:
    assert legacy_model.ContextImportPlan is ContextImportPlan
    assert legacy_model.MemoryImportPlan is MemoryImportPlan
    assert legacy_model.plan_context_import is plan_context_import
    assert legacy_model.import_context_from_profile is import_context_from_profile
    assert legacy_model.plan_memory_import is plan_memory_import
    assert legacy_model.import_memory_from_profile is import_memory_from_profile
    assert legacy_model.import_profile_from_profile is import_profile_from_profile


def test_profile_model_baseline_names_remain_compatible() -> None:
    assert profile_model.baseline_store_digest is baseline_store_digest
    assert profile_model.import_baseline_profile is import_baseline_profile
