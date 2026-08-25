"""Ownership and compatibility paths for Atomize semantic support modules."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import pickle
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    ("memcommit.atomize", "memcommit.operations.atomize.domain"),
    ("memcommit.atomize_workbench", "memcommit.operations.atomize.workbench"),
    ("memcommit.atomize_grounding", "memcommit.operations.atomize.grounding"),
    (
        "memcommit.atomize_grounding_provider",
        "memcommit.operations.atomize.grounding_provider",
    ),
    (
        "memcommit.atomize_meld_adapter",
        "memcommit.operations.atomize.grounding_meld_adapter",
    ),
    (
        "memcommit.atomize_normal_form",
        "memcommit.operations.atomize.normal_form",
    ),
    (
        "memcommit.atomize_result_adapter",
        "memcommit.operations.atomize.result_adapter",
    ),
    (
        "memcommit.atomize_resolution_adapter",
        "memcommit.operations.atomize.resolution_adapter",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_atomize_support_module_identity_is_import_order_independent(
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


@pytest.mark.parametrize("legacy_name,_canonical_name", MODULE_PAIRS)
def test_atomize_support_legacy_facades_define_no_behavior(
    legacy_name: str,
    _canonical_name: str,
) -> None:
    relative_path = Path(*legacy_name.split(".")).with_suffix(".py")
    path = REPOSITORY_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_atomize_package_keeps_support_modules_lazy() -> None:
    canonical_names = tuple(canonical for _legacy, canonical in MODULE_PAIRS)
    program = f"""
import sys
import memcommit.operations.atomize

for name in {canonical_names!r}:
    assert name not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


@pytest.mark.parametrize(
    "legacy_name,canonical_name,global_name",
    (
        (
            "memcommit.atomize",
            "memcommit.operations.atomize.domain",
            "AtomizeAnalysisSession",
        ),
        (
            "memcommit.atomize_workbench",
            "memcommit.operations.atomize.workbench",
            "AtomizeWorkbenchSession",
        ),
        (
            "memcommit.atomize_grounding",
            "memcommit.operations.atomize.grounding",
            "AtomizeGroundingSession",
        ),
        (
            "memcommit.atomize_grounding_provider",
            "memcommit.operations.atomize.grounding_provider",
            "AtomizeGroundingProviderError",
        ),
        (
            "memcommit.atomize_meld_adapter",
            "memcommit.operations.atomize.grounding_meld_adapter",
            "AtomizeMeldView",
        ),
        (
            "memcommit.atomize_normal_form",
            "memcommit.operations.atomize.normal_form",
            "AtomizeNormalFormProjection",
        ),
        (
            "memcommit.atomize_result_adapter",
            "memcommit.operations.atomize.result_adapter",
            "AtomizeResultWorkbenchAdapter",
        ),
        (
            "memcommit.atomize_resolution_adapter",
            "memcommit.operations.atomize.resolution_adapter",
            "AtomizeResolutionWorkbenchAdapter",
        ),
    ),
)
def test_pre_relocation_atomize_support_globals_load_through_aliases(
    legacy_name: str,
    canonical_name: str,
    global_name: str,
) -> None:
    canonical = importlib.import_module(canonical_name)
    payload = f"c{legacy_name}\n{global_name}\n.".encode()

    restored = pickle.loads(payload)

    assert restored is getattr(canonical, global_name)


def test_atomize_support_imports_follow_the_canonical_dependency_direction() -> None:
    canonical_paths = tuple(
        Path(*canonical_name.split(".")).with_suffix(".py")
        for _legacy_name, canonical_name in MODULE_PAIRS
    )
    legacy_names = tuple(legacy_name for legacy_name, _canonical in MODULE_PAIRS)

    for relative_path in canonical_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.commands" not in source
        assert "memcommit.interfaces" not in source
        for legacy_name in legacy_names:
            assert legacy_name not in source


def test_atomize_production_consumers_use_canonical_support_modules() -> None:
    relative_paths = (
        "memcommit/api/_operations/atomize.py",
        "memcommit/api/_operations/atomize_grounding.py",
        "memcommit/atomize_workflow.py",
        "memcommit/commands/atomize.py",
        "memcommit/commands/atomize_grounding.py",
        "memcommit/commands/atomize_sessions.py",
        "memcommit/commands/impact.py",
        "memcommit/commands/review.py",
        "memcommit/interfaces/cli/atomize.py",
        "memcommit/interfaces/cli/atomize_grounding.py",
        "memcommit/interfaces/tui/operations/atomize/adapter.py",
        "memcommit/interfaces/tui/operations/atomize/screen.py",
        "memcommit/operations/atomize/analysis_application.py",
        "memcommit/operations/atomize/analysis_runtime.py",
        "memcommit/operations/atomize/application.py",
        "memcommit/operations/atomize/grounding_application.py",
        "memcommit/operations/atomize/grounding_runtime.py",
        "memcommit/operations/atomize/runtime.py",
        "memcommit/ops.py",
        "memcommit/provenance.py",
        "memcommit/review.py",
        "memcommit/review_report_adapters.py",
        "memcommit/store.py",
        "memcommit/study_prewarm/atomize.py",
    )
    legacy_names = tuple(legacy_name for legacy_name, _canonical in MODULE_PAIRS)

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for legacy_name in legacy_names:
            assert legacy_name not in source


def test_atomize_view_adapters_remain_read_only_projections() -> None:
    for relative_path in (
        "memcommit/operations/atomize/result_adapter.py",
        "memcommit/operations/atomize/resolution_adapter.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "MemoryStore" not in source
        assert "provider.complete" not in source
        assert "memcommit.commands" not in source
        assert "memcommit.interfaces" not in source
