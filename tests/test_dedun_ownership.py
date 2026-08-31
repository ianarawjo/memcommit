"""Canonical ownership for semantic Dedun contracts and adapters."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_dedup_and_dedun_use_command_aligned_canonical_paths() -> None:
    source_root = REPOSITORY_ROOT / "src/memcommit"

    assert (source_root / "application/operations/dedup/application.py").is_file()
    assert (source_root / "application/operations/dedun/application.py").is_file()
    assert (source_root / "application/operations/dedun/analysis.py").is_file()
    assert (source_root / "application/operations/dedun/runtime.py").is_file()
    assert not (source_root / "application/operations/dedun/planning.py").exists()
    assert not (source_root / "application/operations/dedun/scope.py").exists()
    assert not (source_root / "adapters/console/commands/dedun/presentation.py").exists()
    assert not (source_root / "adapters/console/commands/dedun/workbench.py").exists()
    assert not (
        source_root / "adapters/console/commands/consolidate/command.py"
    ).exists()
    assert not (
        source_root
        / "adapters/console/commands/find_redundancies/dedup_handoff.py"
    ).exists()
    assert (source_root / "adapters/python_api/_operations/dedup.py").is_file()
    assert (source_root / "adapters/python_api/_operations/dedun.py").is_file()

    assert not tuple(
        (source_root / "application/operations/exact_dedup").glob("*.py")
    )
    assert not (
        source_root / "adapters/interfaces/cli/dedup.py"
    ).exists()
    assert not tuple(
        (source_root / "adapters/interfaces/tui/operations/dedup").glob("*.py")
    )
    assert not (
        source_root / "adapters/python_api/_operations/exact_dedup.py"
    ).exists()


def test_legacy_public_result_names_are_thin_dedun_aliases() -> None:
    from memcommit.adapters.python_api import (
        DedupApplyResult,
        DedupPlanResult,
        DedunApplyResult,
        DedunPlanResult,
    )

    assert DedupPlanResult is DedunPlanResult
    assert DedupApplyResult is DedunApplyResult


def test_dedun_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.dedun

assert "memcommit.application.operations.dedun.application" not in sys.modules
assert "memcommit.application.operations.dedun.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_dedun_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/application/operations/atomize/normal_form.py",
        "src/memcommit/adapters/python_api/dedun.py",
        "src/memcommit/adapters/python_api/_operations/dedun.py",
        "src/memcommit/adapters/console/commands/find_duplicates/command.py",
        "src/memcommit/adapters/console/terminal/components/quality_find/workbench.py",
        "src/memcommit/application/operations/dedun/analysis.py",
        "src/memcommit/application/operations/dedun/runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.dedup_application" not in source
        assert "memcommit.dedup_runtime" not in source


def test_dedun_and_exact_dedup_remain_separate_owners() -> None:
    application = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/dedun/application.py"
    ).read_text(encoding="utf-8")
    runtime = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/dedun/runtime.py"
    ).read_text(encoding="utf-8")
    exact = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/dedup/application.py"
    ).read_text(encoding="utf-8")
    analysis = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/dedun/analysis.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.dedun_scope" not in application + runtime
    assert "memcommit.application.operations.dedun" not in exact
    assert "connected_relation_components" in analysis
