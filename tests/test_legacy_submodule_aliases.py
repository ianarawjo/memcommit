"""Contracts for intentionally removed historical Python import paths."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "memcommit"
ROOT_BOUNDARIES = {
    "__init__.py",
    "bootstrap.py",
    "context.py",
    "context_locator.py",
}


def test_package_root_contains_only_real_implementation_boundaries() -> None:
    assert {path.name for path in PACKAGE_ROOT.glob("*.py")} == ROOT_BOUNDARIES
    assert not (PACKAGE_ROOT / "compatibility").exists()


def test_representative_historical_imports_are_unavailable() -> None:
    program = """
from importlib import import_module

removed = (
    "memcommit.store",
    "memcommit.atomize_analysis_runtime",
    "memcommit.semantic_execution",
)
for module in removed:
    try:
        import_module(module)
    except ModuleNotFoundError:
        pass
    else:
        raise AssertionError(f"{module} unexpectedly remains importable")
"""
    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_canonical_owners_remain_importable_without_a_runtime_finder() -> None:
    program = """
from importlib import import_module
import sys

owners = (
    "memcommit.persistence.store",
    "memcommit.application.operations.atomize.analysis_runtime",
    "memcommit.application.semantic_execution",
)
for module in owners:
    import_module(module)

assert not any(
    getattr(finder, "marker", None) == "memcommit-legacy-submodule-aliases-v1"
    for finder in sys.meta_path
)
"""
    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
