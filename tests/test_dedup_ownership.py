"""Ownership and compatibility paths for reviewed redundancy contracts."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_dedup_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.dedup

assert "memcommit.application.operations.dedup.application" not in sys.modules
assert "memcommit.application.operations.dedup.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_dedup_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/application/operations/atomize/normal_form.py",
        "src/memcommit/adapters/python_api/dedup.py",
        "src/memcommit/adapters/python_api/_operations/dedup.py",
        "src/memcommit/commands/consolidate/command.py",
        "src/memcommit/commands/find_duplicates/dedup_handoff.py",
        "src/memcommit/commands/find_duplicates/command.py",
        "src/memcommit/commands/shared/quality_find_workbench.py",
        "src/memcommit/application/operations/dedup/planning.py",
        "src/memcommit/application/operations/dedun/scope.py",
        "src/memcommit/adapters/interfaces/cli/dedup.py",
        "src/memcommit/adapters/interfaces/tui/operations/dedup/screen.py",
        "src/memcommit/application/operations/dedup/runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.dedup_application" not in source
        assert "memcommit.dedup_runtime" not in source


def test_exact_dedup_and_dedun_scope_remain_separate_owners() -> None:
    application = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/dedup/application.py"
    ).read_text(encoding="utf-8")
    runtime = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/dedup/runtime.py"
    ).read_text(encoding="utf-8")
    exact = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/exact_dedup/application.py"
    ).read_text(encoding="utf-8")
    dedun_scope = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/dedun/scope.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.dedun_scope" not in application + runtime
    assert "memcommit.application.operations.dedup" not in exact
    assert "memcommit.application.operations.dedup" in dedun_scope
