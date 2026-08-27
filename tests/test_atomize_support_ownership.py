"""Ownership and compatibility paths for Atomize semantic support modules."""

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
    ("memcommit.atomize", "memcommit.application.operations.atomize.domain"),
    ("memcommit.atomize_workbench", "memcommit.application.operations.atomize.workbench"),
    ("memcommit.atomize_grounding", "memcommit.application.operations.atomize.grounding"),
    (
        "memcommit.atomize_grounding_provider",
        "memcommit.application.operations.atomize.grounding_provider",
    ),
    (
        "memcommit.atomize_meld_adapter",
        "memcommit.application.operations.atomize.grounding_meld_adapter",
    ),
    (
        "memcommit.atomize_normal_form",
        "memcommit.application.operations.atomize.normal_form",
    ),
    (
        "memcommit.atomize_result_adapter",
        "memcommit.application.operations.atomize.result_adapter",
    ),
    (
        "memcommit.atomize_resolution_adapter",
        "memcommit.application.operations.atomize.resolution_adapter",
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
    assert_legacy_root_submodule_is_centralized(legacy_name, _canonical_name)


def test_atomize_package_keeps_support_modules_lazy() -> None:
    canonical_names = tuple(canonical for _legacy, canonical in MODULE_PAIRS)
    program = f"""
import sys
import memcommit.application.operations.atomize

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
            "memcommit.application.operations.atomize.domain",
            "AtomizeAnalysisSession",
        ),
        (
            "memcommit.atomize_workbench",
            "memcommit.application.operations.atomize.workbench",
            "AtomizeWorkbenchSession",
        ),
        (
            "memcommit.atomize_grounding",
            "memcommit.application.operations.atomize.grounding",
            "AtomizeGroundingSession",
        ),
        (
            "memcommit.atomize_grounding_provider",
            "memcommit.application.operations.atomize.grounding_provider",
            "AtomizeGroundingProviderError",
        ),
        (
            "memcommit.atomize_meld_adapter",
            "memcommit.application.operations.atomize.grounding_meld_adapter",
            "AtomizeMeldView",
        ),
        (
            "memcommit.atomize_normal_form",
            "memcommit.application.operations.atomize.normal_form",
            "AtomizeNormalFormProjection",
        ),
        (
            "memcommit.atomize_result_adapter",
            "memcommit.application.operations.atomize.result_adapter",
            "AtomizeResultWorkbenchAdapter",
        ),
        (
            "memcommit.atomize_resolution_adapter",
            "memcommit.application.operations.atomize.resolution_adapter",
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
        source = (REPOSITORY_ROOT / "src" / relative_path).read_text(
            encoding="utf-8"
        )
        assert "memcommit.commands" not in source
        assert "memcommit.adapters.interfaces" not in source
        for legacy_name in legacy_names:
            assert legacy_name not in source


def test_atomize_production_consumers_use_canonical_support_modules() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/atomize.py",
        "src/memcommit/adapters/python_api/_operations/atomize_grounding.py",
        "src/memcommit/application/operations/atomize/workflow.py",
        "src/memcommit/commands/atomize/command.py",
        "src/memcommit/commands/atomize/grounding.py",
        "src/memcommit/commands/atomize/sessions.py",
        "src/memcommit/commands/impact/command.py",
        "src/memcommit/commands/review/command.py",
        "src/memcommit/adapters/interfaces/cli/atomize.py",
        "src/memcommit/adapters/interfaces/cli/atomize_grounding.py",
        "src/memcommit/adapters/interfaces/tui/operations/atomize/adapter.py",
        "src/memcommit/adapters/interfaces/tui/operations/atomize/screen.py",
        "src/memcommit/application/operations/atomize/analysis_application.py",
        "src/memcommit/application/operations/atomize/analysis_runtime.py",
        "src/memcommit/application/operations/atomize/application.py",
        "src/memcommit/application/operations/atomize/grounding_application.py",
        "src/memcommit/application/operations/atomize/grounding_runtime.py",
        "src/memcommit/application/operations/atomize/runtime.py",
        "src/memcommit/application/ops.py",
        "src/memcommit/application/retained_history/memory_history_reconstruction/retained_record_verification.py",
        "src/memcommit/application/retained_history/memory_history_reconstruction/memory_history_event_derivation.py",
        "src/memcommit/application/retained_history/memory_history_reconstruction/memory_history_construction.py",
        "src/memcommit/application/operations/review/model.py",
        "src/memcommit/application/operations/review/report_adapters.py",
        "src/memcommit/persistence/store/operation_state.py",
        "src/memcommit/persistence/store/context_memory.py",
        "src/memcommit/persistence/store/record_restore_checkpoint.py",
        "src/memcommit/study_prewarm/atomize.py",
    )
    legacy_names = tuple(legacy_name for legacy_name, _canonical in MODULE_PAIRS)

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for legacy_name in legacy_names:
            assert legacy_name not in source


def test_atomize_view_adapters_remain_read_only_projections() -> None:
    for relative_path in (
        "src/memcommit/application/operations/atomize/result_adapter.py",
        "src/memcommit/application/operations/atomize/resolution_adapter.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "MemoryStore" not in source
        assert "provider.complete" not in source
        assert "memcommit.commands" not in source
        assert "memcommit.adapters.interfaces" not in source
