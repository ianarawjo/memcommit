"""Ownership and compatibility paths for Atomize semantic support modules."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys



REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    ("memcommit.atomize", "memcommit.application.operations.atomize.domain"),
    (
        "memcommit.atomize_workbench",
        "memcommit.application.operations.atomize.workbench",
    ),
    (
        "memcommit.atomize_grounding",
        "memcommit.application.operations.atomize.grounding",
    ),
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


def test_atomize_support_imports_follow_the_canonical_dependency_direction() -> None:
    canonical_paths = tuple(
        Path(*canonical_name.split(".")).with_suffix(".py")
        for _legacy_name, canonical_name in MODULE_PAIRS
    )
    legacy_names = tuple(legacy_name for legacy_name, _canonical in MODULE_PAIRS)

    for relative_path in canonical_paths:
        source = (REPOSITORY_ROOT / "src" / relative_path).read_text(encoding="utf-8")
        assert "memcommit.adapters.console.commands" not in source
        assert "memcommit.adapters.interfaces" not in source
        for legacy_name in legacy_names:
            assert legacy_name not in source


def test_atomize_production_consumers_use_canonical_support_modules() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/atomize.py",
        "src/memcommit/adapters/python_api/_operations/atomize_grounding.py",
        "src/memcommit/application/operations/atomize/workflow.py",
        "src/memcommit/adapters/console/commands/atomize/command.py",
        "src/memcommit/adapters/console/commands/atomize/grounding.py",
        "src/memcommit/adapters/console/commands/atomize/sessions.py",
        "src/memcommit/adapters/console/commands/impact/command.py",
        "src/memcommit/adapters/console/commands/review/command.py",
        "src/memcommit/adapters/console/commands/atomize/render.py",
        "src/memcommit/adapters/console/commands/atomize/grounding.py",
        "src/memcommit/adapters/console/commands/atomize/workbench/adapter.py",
        "src/memcommit/adapters/console/commands/atomize/workbench/screen.py",
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
        "src/memcommit/study_scenarios/legacy/prewarm/atomize.py",
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
        assert "memcommit.adapters.console.commands" not in source
        assert "memcommit.adapters.interfaces" not in source
