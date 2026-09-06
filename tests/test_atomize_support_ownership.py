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
        "memcommit.application.operations.atomize.records",
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
    canonical_roots = tuple(
        Path(*canonical_name.split("."))
        for _legacy_name, canonical_name in MODULE_PAIRS
    )
    legacy_names = tuple(legacy_name for legacy_name, _canonical in MODULE_PAIRS)

    for relative_root in canonical_roots:
        package_path = REPOSITORY_ROOT / "src" / relative_root
        module_path = package_path.with_suffix(".py")
        source_paths = (
            tuple(sorted(package_path.rglob("*.py")))
            if package_path.is_dir()
            else (module_path,)
        )
        for source_path in source_paths:
            source = source_path.read_text(encoding="utf-8")
            assert "memcommit.adapters.console.commands" not in source
            assert "memcommit.adapters.interfaces" not in source
            for legacy_name in legacy_names:
                assert legacy_name not in source


def test_atomize_production_consumers_use_canonical_support_modules() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/atomize.py",
        "src/memcommit/adapters/console/commands/atomize/command.py",
        "src/memcommit/adapters/console/commands/atomize/impact.py",
        "src/memcommit/adapters/console/commands/atomize/review.py",
        "src/memcommit/adapters/console/commands/atomize/records.py",
        "src/memcommit/adapters/console/commands/impact/command.py",
        "src/memcommit/adapters/console/commands/review/command.py",
        "src/memcommit/application/operations/atomize/analysis_application.py",
        "src/memcommit/application/operations/atomize/analysis_runtime.py",
        "src/memcommit/application/operations/atomize/application.py",
        "src/memcommit/application/operations/atomize/runtime.py",
        "src/memcommit/application/capabilities/ops.py",
        "src/memcommit/application/capabilities/history/verification",
        "src/memcommit/application/capabilities/history/reconstruction/memory_effects",
        "src/memcommit/application/capabilities/history/query/memory_history_slicing.py",
        "src/memcommit/application/operations/review/model.py",
        "src/memcommit/persistence/operations/atomize",
        "src/memcommit/persistence/store/context_memory",
        "src/memcommit/persistence/store/record_restore_checkpoint.py",
        "src/memcommit/persistence/store/checkpoint",
        "src/memcommit/persistence/store/command_restoration",
    )
    legacy_names = tuple(legacy_name for legacy_name, _canonical in MODULE_PAIRS)

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        paths = tuple(sorted(path.rglob("*.py"))) if path.is_dir() else (path,)
        for source_path in paths:
            source = source_path.read_text(encoding="utf-8")
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
