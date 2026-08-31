"""Ownership and compatibility paths for deterministic Update application."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_NAME = "memcommit.application.operations.update.materialization"


def test_update_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.update

assert "memcommit.application.operations.update.materialization" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_update_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/persistence/operations/update",
        "src/memcommit/persistence/store/context_memory",
        "src/memcommit/persistence/store/record_restore_checkpoint.py",
        "src/memcommit/persistence/store/checkpoint",
        "src/memcommit/persistence/store/command_restoration",
        "src/memcommit/application/operations/update/publication.py",
        "src/memcommit/application/operations/update/history.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        paths = tuple(sorted(path.rglob("*.py"))) if path.is_dir() else (path,)
        for source_path in paths:
            source = source_path.read_text(encoding="utf-8")
            assert "from memcommit.update_application import" not in source


def test_update_does_not_invent_an_operation_runtime() -> None:
    assert not (
        REPOSITORY_ROOT / "src/memcommit/application/operations/update/runtime.py"
    ).exists()


def test_update_has_no_endpoint_specific_application_modules() -> None:
    update_root = REPOSITORY_ROOT / "src/memcommit/application/operations/update"

    assert not (update_root / "granted_source.py").exists()
    assert not (update_root / "granted_target.py").exists()


def test_update_model_facade_preserves_concept_owned_modules() -> None:
    from memcommit.application.operations.update.model import (
        AddOperation,
        UpdateApplicationReceipt,
        UpdateInputs,
        UpdateSession,
        plan_update,
    )

    assert AddOperation.__module__.endswith(".model.changes")
    assert UpdateApplicationReceipt.__module__.endswith(".model.receipts")
    assert UpdateInputs.__module__.endswith(".model.inputs")
    assert UpdateSession.__module__.endswith(".model.session")
    assert plan_update.__module__.endswith(".model.planning")
