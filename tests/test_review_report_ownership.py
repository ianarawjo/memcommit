"""Ownership and compatibility paths for shared Review report contracts."""

from __future__ import annotations

import importlib
from pathlib import Path
import pickle
import subprocess
import sys

from tests.legacy_submodule_assertions import (
    assert_legacy_root_submodule_is_centralized,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.review_report"
CANONICAL_MODULE = "memcommit.application.reviewing.report"


def test_review_report_module_identity_is_independent_of_import_order() -> None:
    for first_name, second_name in (
        (LEGACY_MODULE, CANONICAL_MODULE),
        (CANONICAL_MODULE, LEGACY_MODULE),
    ):
        program = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_MODULE!r})
canonical = importlib.import_module({CANONICAL_MODULE!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{CANONICAL_MODULE!r}] is canonical
"""
        subprocess.run(
            [sys.executable, "-c", program],
            cwd=REPOSITORY_ROOT,
            check=True,
        )


def test_review_report_legacy_path_exposes_the_canonical_contract() -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(CANONICAL_MODULE)

    assert legacy is canonical
    assert legacy.ReviewTextFragment is canonical.ReviewTextFragment
    assert legacy.ReviewReport is canonical.ReviewReport
    assert legacy.ReviewReportController is canonical.ReviewReportController


def test_review_report_legacy_facade_defines_no_behavior() -> None:
    assert_legacy_root_submodule_is_centralized(
        LEGACY_MODULE,
        CANONICAL_MODULE,
    )


def test_reviewing_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.reviewing

assert "memcommit.application.reviewing.report" not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_review_report_globals_load_through_alias() -> None:
    canonical = importlib.import_module(CANONICAL_MODULE)

    restored_fragment = pickle.loads(
        b"cmemcommit.review_report\nReviewTextFragment\n."
    )
    restored_report = pickle.loads(b"cmemcommit.review_report\nReviewReport\n.")
    restored_controller = pickle.loads(
        b"cmemcommit.review_report\nReviewReportController\n."
    )

    assert restored_fragment is canonical.ReviewTextFragment
    assert restored_report is canonical.ReviewReport
    assert restored_controller is canonical.ReviewReportController


def test_production_review_report_consumers_use_the_shared_owner() -> None:
    relative_paths = (
        "src/memcommit/application/retained_history/applied_review.py",
        "src/memcommit/commands/review/report.py",
        "src/memcommit/application/operations/review/report_adapters.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.review_report import" not in source
        assert "from memcommit.application.reviewing.report import" in source


def test_shared_review_report_does_not_own_operation_adapters() -> None:
    source = (
        REPOSITORY_ROOT
        / "src"
        / "memcommit"
        / "application"
        / "reviewing"
        / "report.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.commands" not in source
    for operation_module in (
        "memcommit.atomize",
        "memcommit.comparison",
        "memcommit.meld",
        "memcommit.sever",
        "memcommit.update",
    ):
        assert operation_module not in source
