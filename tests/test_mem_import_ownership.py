"""Ownership contracts for the public Import operation."""

from __future__ import annotations

import ast
from pathlib import Path

from memcommit.application.operations.resource_import.profile import (
    baseline_store_digest,
    import_baseline_profile,
)
from memcommit.application.operations.profile import model as profile_model


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
        "src/memcommit/adapters/console/commands/resource_import/command.py"
    )
    workbench_imports = _imported_modules(
        "src/memcommit/adapters/console/commands/resource_import/workbench.py"
    )

    assert "memcommit.application.operations.resource_import.model" not in (
        command_imports | workbench_imports
    )
    assert {
        "memcommit.application.operations.resource_import.context",
        "memcommit.application.operations.resource_import.memory",
    } <= command_imports
    assert "memcommit.application.operations.resource_import.profile" in command_imports
    assert "memcommit.application.operations.resource_import.contracts" in workbench_imports


def test_import_has_one_canonical_flat_operation_package() -> None:
    operations = REPOSITORY_ROOT / "src/memcommit/application/operations"
    assert not (operations / "mem_import").exists()
    package = operations / "resource_import"
    assert (package / "__init__.py").is_file()
    assert not (package / "model.py").exists()


def test_profile_model_baseline_names_remain_compatible() -> None:
    assert profile_model.baseline_store_digest is baseline_store_digest
    assert profile_model.import_baseline_profile is import_baseline_profile
