"""Ownership and compatibility paths for the complete Sever operation."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_sever_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.sever

assert "memcommit.application.operations.sever.application" not in sys.modules
assert "memcommit.application.operations.sever.runtime" not in sys.modules
assert "memcommit.application.operations.sever.model" not in sys.modules
assert "memcommit.application.operations.sever.provider" not in sys.modules
assert "memcommit.application.operations.sever.session_store" not in sys.modules
assert "memcommit.application.operations.sever.resolution_adapter" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_sever_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/impact/command.py",
        "src/memcommit/adapters/console/commands/impact/catalog.py",
        "src/memcommit/adapters/console/commands/impact/sessions.py",
        "src/memcommit/adapters/console/commands/review/command.py",
        "src/memcommit/adapters/console/commands/review/sessions.py",
        "src/memcommit/adapters/console/commands/sever/command.py",
        "src/memcommit/adapters/console/commands/sever/impact.py",
        "src/memcommit/adapters/console/commands/sever/review.py",
        "src/memcommit/adapters/console/commands/sever/sessions.py",
        "src/memcommit/application/operations/sever/application.py",
        "src/memcommit/application/operations/sever/provider.py",
        "src/memcommit/application/operations/sever/resolution_adapter.py",
        "src/memcommit/application/operations/sever/session_store.py",
        "src/memcommit/application/operations/sever/runtime.py",
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
