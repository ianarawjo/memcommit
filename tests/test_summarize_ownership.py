"""Ownership and compatibility paths for read-only Summarize."""

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
    (
        "memcommit.summarize_application",
        "memcommit.application.operations.summarize.application",
    ),
    (
        "memcommit.summarize_runtime",
        "memcommit.application.operations.summarize.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_summarize_module_identity_is_independent_of_import_order(
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


def test_summarize_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.summarize_application")
    canonical_application = importlib.import_module(
        "memcommit.application.operations.summarize.application"
    )
    legacy_runtime = importlib.import_module("memcommit.summarize_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.application.operations.summarize.runtime"
    )

    assert legacy_application is canonical_application
    assert (
        legacy_application.SummarizeRequest
        is canonical_application.SummarizeRequest
    )
    assert legacy_application.run_summarize is canonical_application.run_summarize
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreSummarySourcePort
        is canonical_runtime.MemoryStoreSummarySourcePort
    )
    assert (
        legacy_runtime.run_summarize_with_store
        is canonical_runtime.run_summarize_with_store
    )


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/summarize_application.py", "src/memcommit/summarize_runtime.py"),
)
def test_summarize_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_summarize_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.summarize

assert "memcommit.application.operations.summarize.application" not in sys.modules
assert "memcommit.application.operations.summarize.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_summarize_globals_load_through_aliases() -> None:
    canonical_application = importlib.import_module(
        "memcommit.application.operations.summarize.application"
    )
    canonical_runtime = importlib.import_module(
        "memcommit.application.operations.summarize.runtime"
    )

    restored_request = pickle.loads(
        b"cmemcommit.summarize_application\nSummarizeRequest\n."
    )
    restored_runtime_port = pickle.loads(
        b"cmemcommit.summarize_runtime\nMemoryStoreSummarySourcePort\n."
    )

    assert restored_request is canonical_application.SummarizeRequest
    assert restored_runtime_port is canonical_runtime.MemoryStoreSummarySourcePort


def test_production_summarize_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/bootstrap.py",
        "src/memcommit/commands/summarize/command.py",
        "src/memcommit/application/operations/distill/application.py",
        "src/memcommit/application/operations/distill/runtime.py",
        "src/memcommit/eval/study_summarize_exact_matrix.py",
        "src/memcommit/application/operations/ground/distill.py",
        "src/memcommit/adapters/interfaces/summarize.py",
        "src/memcommit/adapters/interfaces/cli/summarize.py",
        "src/memcommit/adapters/interfaces/tui/operations/summarize/adapter.py",
        "src/memcommit/adapters/interfaces/tui/operations/summarize/model.py",
        "src/memcommit/adapters/interfaces/tui/operations/summarize/screen.py",
        "src/memcommit/application/operations/summarize/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.summarize_application import" not in source
        assert "from memcommit.summarize_runtime import" not in source
