"""Ownership and compatibility paths for shared Review report contracts."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_MODULE = "memcommit.application.capabilities.reviewing.report"


def test_reviewing_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.capabilities.reviewing

assert "memcommit.application.capabilities.reviewing.report" not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_review_report_consumers_use_the_shared_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/operation_lifecycle/review/applied_checkpoint_report.py",
        "src/memcommit/adapters/console/commands/operation_lifecycle/review/report.py",
        "src/memcommit/adapters/console/commands/semantic_updates/derive/atomize/review.py",
        "src/memcommit/adapters/console/commands/search_explain/synthesize/compare/review.py",
        "src/memcommit/adapters/console/commands/semantic_updates/curate_integrate/meld/review.py",
        "src/memcommit/adapters/console/commands/semantic_updates/curate_integrate/sever/review.py",
        "src/memcommit/adapters/console/commands/semantic_updates/foundation/update/review.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.review_report import" not in source
        assert "from memcommit.application.capabilities.reviewing.report import" in source

    application_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/operation_lifecycle/review/applied_checkpoint.py"
    ).read_text(encoding="utf-8")
    assert "memcommit.adapters.console" not in application_source
    assert "memcommit.application.capabilities.reviewing.report" not in application_source


def test_shared_review_report_does_not_own_operation_adapters() -> None:
    source = (
        REPOSITORY_ROOT
        / "src"
        / "memcommit"
        / "application"
        / "capabilities"
        / "reviewing"
        / "report.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.adapters.console.commands" not in source
    for operation_module in (
        "memcommit.atomize",
        "memcommit.comparison",
        "memcommit.meld",
        "memcommit.sever",
        "memcommit.update",
    ):
        assert operation_module not in source


def test_operation_review_projections_are_not_centralized_under_review() -> None:
    assert not (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/operation_lifecycle/review/report_adapters.py"
    ).exists()
