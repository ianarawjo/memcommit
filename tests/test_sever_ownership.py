"""Ownership and compatibility paths for the complete Sever operation."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_sever_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.semantic_updates.curate_integrate.sever

assert "memcommit.application.operations.semantic_updates.curate_integrate.sever.application" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.sever.runtime" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.sever.model" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.sever.provider" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.sever.session_store" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.sever.resolution_adapter" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_sever_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/operation_lifecycle/impact/command.py",
        "src/memcommit/adapters/console/commands/operation_lifecycle/impact/catalog.py",
        "src/memcommit/adapters/console/commands/operation_lifecycle/impact/sessions.py",
        "src/memcommit/adapters/console/commands/operation_lifecycle/review/command.py",
        "src/memcommit/adapters/console/commands/operation_lifecycle/review/sessions.py",
        "src/memcommit/adapters/console/commands/semantic_updates/curate_integrate/sever/command.py",
        "src/memcommit/adapters/console/commands/semantic_updates/curate_integrate/sever/impact.py",
        "src/memcommit/adapters/console/commands/semantic_updates/curate_integrate/sever/review.py",
        "src/memcommit/adapters/console/commands/semantic_updates/curate_integrate/sever/sessions.py",
        "src/memcommit/application/operations/semantic_updates/curate_integrate/sever/application.py",
        "src/memcommit/application/operations/semantic_updates/curate_integrate/sever/provider.py",
        "src/memcommit/application/operations/semantic_updates/curate_integrate/sever/resolution_adapter.py",
        "src/memcommit/study_scenarios/legacy/prewarm/sever.py",
        "src/memcommit/application/operations/semantic_updates/curate_integrate/sever/session_store.py",
        "src/memcommit/application/operations/semantic_updates/curate_integrate/sever/runtime.py",
        "src/memcommit/persistence/operations",
        "src/memcommit/persistence/store/context_memory",
        "src/memcommit/persistence/store/record_restore_checkpoint.py",
        "src/memcommit/persistence/store/checkpoint",
        "src/memcommit/persistence/store/command_restoration",
    )
    legacy_imports = (
        "from memcommit.sever import",
        "from memcommit.sever_provider import",
        "from memcommit.sever_resolution_adapter import",
        "from memcommit.sever_store import",
        "from memcommit.sever_application import",
        "from memcommit.sever_runtime import",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        paths = tuple(sorted(path.rglob("*.py"))) if path.is_dir() else (path,)
        for source_path in paths:
            source = source_path.read_text(encoding="utf-8")
            assert not [legacy for legacy in legacy_imports if legacy in source]
