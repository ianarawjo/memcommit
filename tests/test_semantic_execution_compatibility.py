"""Compatibility coverage for the application-owned semantic executor."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "memcommit"


def _run_isolated(program: str) -> None:
    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_semantic_execution_has_one_physical_application_owner() -> None:
    canonical = PACKAGE_ROOT / "application" / "semantic_execution"
    assert canonical.is_dir()
    legacy = PACKAGE_ROOT / "semantic_execution"
    assert not (legacy / "__init__.py").exists()
    assert tuple(legacy.glob("*.py")) == ()

    stale_imports = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        if path == PACKAGE_ROOT / "compatibility" / "legacy_submodules.py":
            continue
        if "memcommit.semantic_execution" in path.read_text(encoding="utf-8"):
            stale_imports.append(path.relative_to(REPOSITORY_ROOT).as_posix())
    assert stale_imports == []


def test_legacy_semantic_execution_package_is_the_canonical_package() -> None:
    _run_isolated(
        """
from importlib import import_module

legacy = import_module("memcommit.semantic_execution")
canonical = import_module("memcommit.application.semantic_execution")

assert legacy is canonical
assert legacy.__name__ == "memcommit.application.semantic_execution"
assert legacy.__spec__.name == "memcommit.application.semantic_execution"
assert legacy.BudgetVector is canonical.BudgetVector
"""
    )


def test_legacy_semantic_execution_children_keep_module_identity() -> None:
    _run_isolated(
        """
from importlib import import_module

for child in (
    "budgeting",
    "coverage",
    "execution",
    "model",
    "partitioning",
    "planning",
    "relations",
):
    legacy = import_module(f"memcommit.semantic_execution.{child}")
    canonical = import_module(
        f"memcommit.application.semantic_execution.{child}"
    )
    assert legacy is canonical
    assert legacy.__name__ == canonical.__name__
    assert legacy.__spec__.name == canonical.__spec__.name
"""
    )


def test_canonical_first_import_keeps_legacy_identity() -> None:
    _run_isolated(
        """
from importlib import import_module

canonical = import_module("memcommit.application.semantic_execution.model")
legacy = import_module("memcommit.semantic_execution.model")

assert legacy is canonical
assert legacy.ExecutionPlan is canonical.ExecutionPlan
"""
    )
