"""Ownership and compatibility paths for general and Ground Fit."""

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
        "memcommit.fit",
        "memcommit.operations.fit.ground_report",
    ),
    (
        "memcommit.fit_judgment",
        "memcommit.operations.fit.judgment",
    ),
    (
        "memcommit.fit_coherence",
        "memcommit.operations.fit.coherence",
    ),
    (
        "memcommit.fit_store",
        "memcommit.operations.fit.store",
    ),
    (
        "memcommit.fit_application",
        "memcommit.operations.fit.application",
    ),
    (
        "memcommit.fit_runtime",
        "memcommit.operations.fit.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_fit_module_identity_is_independent_of_import_order(
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


def test_fit_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_report = importlib.import_module("memcommit.fit")
    canonical_report = importlib.import_module(
        "memcommit.operations.fit.ground_report"
    )
    legacy_judgment = importlib.import_module("memcommit.fit_judgment")
    canonical_judgment = importlib.import_module("memcommit.operations.fit.judgment")
    legacy_coherence = importlib.import_module("memcommit.fit_coherence")
    canonical_coherence = importlib.import_module(
        "memcommit.operations.fit.coherence"
    )
    legacy_store = importlib.import_module("memcommit.fit_store")
    canonical_store = importlib.import_module("memcommit.operations.fit.store")
    legacy_application = importlib.import_module("memcommit.fit_application")
    canonical_application = importlib.import_module(
        "memcommit.operations.fit.application"
    )
    legacy_runtime = importlib.import_module("memcommit.fit_runtime")
    canonical_runtime = importlib.import_module("memcommit.operations.fit.runtime")

    assert legacy_report is canonical_report
    assert legacy_report.FitReport is canonical_report.FitReport
    assert legacy_judgment is canonical_judgment
    assert legacy_judgment.FitProposition is canonical_judgment.FitProposition
    assert legacy_coherence is canonical_coherence
    assert (
        legacy_coherence.FitCoherenceReport
        is canonical_coherence.FitCoherenceReport
    )
    assert legacy_store is canonical_store
    assert legacy_store.FitStore is canonical_store.FitStore
    assert legacy_application is canonical_application
    assert (
        legacy_application.FitPropositionsRequest
        is canonical_application.FitPropositionsRequest
    )
    assert legacy_application.FitResult is canonical_application.FitResult
    assert legacy_runtime is canonical_runtime
    assert legacy_runtime.FitSourceError is canonical_runtime.FitSourceError
    assert legacy_runtime.run_proposition_fit is canonical_runtime.run_proposition_fit
    assert (
        legacy_runtime.execute_and_save_ground_fit
        is canonical_runtime.execute_and_save_ground_fit
    )


@pytest.mark.parametrize(
    "relative_path",
    (
        "src/memcommit/fit.py",
        "src/memcommit/fit_judgment.py",
        "src/memcommit/fit_coherence.py",
        "src/memcommit/fit_store.py",
        "src/memcommit/fit_application.py",
        "src/memcommit/fit_runtime.py",
    ),
)
def test_fit_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_fit_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.fit

assert "memcommit.operations.fit.application" not in sys.modules
assert "memcommit.operations.fit.runtime" not in sys.modules
assert "memcommit.operations.fit.ground_report" not in sys.modules
assert "memcommit.operations.fit.judgment" not in sys.modules
assert "memcommit.operations.fit.coherence" not in sys.modules
assert "memcommit.operations.fit.store" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


@pytest.mark.parametrize(
    "legacy_module,canonical_module,global_name",
    (
        ("memcommit.fit", "memcommit.operations.fit.ground_report", "FitReport"),
        (
            "memcommit.fit_judgment",
            "memcommit.operations.fit.judgment",
            "FitProposition",
        ),
        (
            "memcommit.fit_coherence",
            "memcommit.operations.fit.coherence",
            "FitCoherenceReport",
        ),
        ("memcommit.fit_store", "memcommit.operations.fit.store", "FitStore"),
        (
            "memcommit.fit_application",
            "memcommit.operations.fit.application",
            "FitPropositionsRequest",
        ),
    ),
)
def test_pre_relocation_fit_global_loads_through_alias(
    legacy_module: str,
    canonical_module: str,
    global_name: str,
) -> None:
    canonical = importlib.import_module(canonical_module)

    restored = pickle.loads(f"c{legacy_module}\n{global_name}\n.".encode())

    assert restored is getattr(canonical, global_name)


def test_production_fit_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/api/_operations/fit.py",
        "src/memcommit/api/_operations/resolve.py",
        "src/memcommit/interfaces/cli/fit.py",
        "src/memcommit/interfaces/fit.py",
        "src/memcommit/commands/fit/command.py",
        "src/memcommit/commands/find_conflicts/command.py",
        "src/memcommit/commands/ground/command.py",
        "src/memcommit/commands/ground/named_shell.py",
        "src/memcommit/commands/impact/process_local.py",
        "src/memcommit/commands/resolve/command.py",
        "src/memcommit/operations/elaborate/model.py",
        "src/memcommit/operations/ground/workspace_fit.py",
        "src/memcommit/operations/fit/application.py",
        "src/memcommit/operations/fit/runtime.py",
        "src/memcommit/operations/resolve/application.py",
        "src/memcommit/operations/resolve/semantic.py",
    )
    legacy_imports = (
        "from memcommit.fit import",
        "from memcommit.fit_judgment import",
        "from memcommit.fit_coherence import",
        "from memcommit.fit_store import",
        "from memcommit.fit_application import",
        "from memcommit.fit_runtime import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for legacy_import in legacy_imports:
            assert legacy_import not in source
