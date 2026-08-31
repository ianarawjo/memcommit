"""Ownership contracts for the public Import operation."""

from __future__ import annotations

import ast
from pathlib import Path

from memcommit.application.operations.create_copy_connect.resource_import.profile import (
    baseline_store_digest,
    import_baseline_profile,
)
from memcommit.application.operations.profiles.profile import model as profile_model


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
        "src/memcommit/adapters/console/commands/create_copy_connect/resource_import/command.py"
    )
    workbench_imports = _imported_modules(
        "src/memcommit/adapters/console/commands/create_copy_connect/resource_import/workbench.py"
    )

    assert "memcommit.application.operations.create_copy_connect.resource_import.model" not in (
        command_imports | workbench_imports
    )
    assert {
        "memcommit.application.operations.create_copy_connect.resource_import.context",
        "memcommit.application.operations.create_copy_connect.resource_import.memory",
    } <= command_imports
    assert "memcommit.application.operations.create_copy_connect.resource_import.profile" in command_imports
    assert "memcommit.application.operations.create_copy_connect.resource_import.contracts" in workbench_imports


def test_import_has_no_parallel_legacy_operation_package() -> None:
    operations = REPOSITORY_ROOT / "src/memcommit/application/operations"
    assert not (operations / "mem_import").exists()
    assert not (operations / "resource_import").exists()


def test_profile_model_baseline_names_remain_compatible() -> None:
    assert profile_model.baseline_store_digest is baseline_store_digest
    assert profile_model.import_baseline_profile is import_baseline_profile
