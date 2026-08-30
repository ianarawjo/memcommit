"""Ownership and compatibility paths for lightweight Compare Summary."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_compare_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.compare

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.application.operations.compare.")
]
assert "memcommit.comparison" not in sys.modules
assert "memcommit.comparison_store" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_summary_consumers_use_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/compare/command.py",
        "src/memcommit/application/operations/compare/compare_summary.py",
        "src/memcommit/application/operations/compare/provider_contract.py",
        "src/memcommit/application/operations/compare/application.py",
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


def test_compare_owner_does_not_absorb_deep_compare_or_presentation() -> None:
    package_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(
            (REPOSITORY_ROOT / "src/memcommit/application/operations/compare").glob("*.py")
        )
    )

    assert "memcommit.adapters.console.commands" not in package_source
    assert "memcommit.adapters.interfaces" not in package_source
    assert "render_comparison" not in package_source
    assert "from memcommit.comparison import ComparisonAnalysis" not in package_source
    assert "ensure_comparison_analysis" not in package_source
    assert "save_comparison_analysis" not in package_source
    assert "open_comparison_session" not in package_source
