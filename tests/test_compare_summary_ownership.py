"""Ownership and compatibility paths for lightweight Compare Summary."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import pickle
import subprocess
import sys

import pytest

from tests.legacy_submodule_assertions import (
    assert_legacy_root_submodule_is_centralized,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    ("memcommit.comparison_summary", "memcommit.operations.compare.summary"),
    (
        "memcommit.comparison_summary_rules",
        "memcommit.operations.compare.summary_rules",
    ),
    (
        "memcommit.comparison_summary_provider",
        "memcommit.operations.compare.summary_provider",
    ),
    (
        "memcommit.comparison_summary_application",
        "memcommit.operations.compare.summary_application",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_summary_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name)
        if legacy_first
        else (canonical_name, legacy_name)
    )
    program = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({legacy_name!r})
canonical = importlib.import_module({canonical_name!r})

assert first is second
assert legacy is canonical
assert sys.modules[{legacy_name!r}] is canonical
assert sys.modules[{canonical_name!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


@pytest.mark.parametrize(
    "relative_path",
    (
        "memcommit/comparison_summary.py",
        "memcommit/comparison_summary_rules.py",
        "memcommit/comparison_summary_provider.py",
        "memcommit/comparison_summary_application.py",
    ),
)
def test_summary_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_compare_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.compare

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.operations.compare.")
]
assert "memcommit.comparison" not in sys.modules
assert "memcommit.comparison_store" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_summary_global_loads_through_alias() -> None:
    canonical = importlib.import_module("memcommit.operations.compare.summary")

    restored = pickle.loads(
        b"cmemcommit.comparison_summary\nComparisonSummary\n."
    )

    assert restored is canonical.ComparisonSummary
    assert restored.__module__ == "memcommit.operations.compare.summary"


def test_production_summary_consumers_use_operation_owner() -> None:
    relative_paths = (
        "memcommit/commands/compare/command.py",
        "memcommit/operations/compare/summary.py",
        "memcommit/operations/compare/summary_provider.py",
        "memcommit/operations/compare/summary_application.py",
    )
    legacy_imports = (
        "from memcommit.comparison_summary import",
        "from memcommit.comparison_summary_rules import",
        "from memcommit.comparison_summary_provider import",
        "from memcommit.comparison_summary_application import",
        "import memcommit.comparison_summary",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_summary_owner_does_not_absorb_deep_compare_or_presentation() -> None:
    package_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(
            (REPOSITORY_ROOT / "memcommit/operations/compare").glob("*.py")
        )
    )

    assert "memcommit.commands" not in package_source
    assert "memcommit.interfaces" not in package_source
    assert "render_comparison" not in package_source
    assert "from memcommit.comparison import ComparisonAnalysis" not in package_source
    assert "ensure_comparison_analysis" not in package_source
    assert "save_comparison_analysis" not in package_source
    assert "open_comparison_session" not in package_source
