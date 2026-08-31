"""Ownership and compatibility paths for deterministic Update application."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_NAME = "memcommit.application.operations.update.application"


def test_update_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.update

assert "memcommit.application.operations.update.application" not in sys.modules
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
        "src/memcommit/application/operations/update/inspection.py",
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


def test_update_publication_separates_coordination_from_transaction() -> None:
    application_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/update/publication.py"
    ).read_text(encoding="utf-8")
    transaction_source = (
        REPOSITORY_ROOT
        / "src/memcommit/persistence/operations/update/publication_repository.py"
    ).read_text(encoding="utf-8")

    assert "publish_update_transaction" in application_source
    assert "authority_grant_snapshot_lock" in application_source
    assert "authorize_context_use" in application_source
    assert "_context_write_locks" not in application_source
    assert "_write_json_atomic" not in application_source

    assert "publish_update_transaction" in transaction_source
    assert "_context_write_locks" in transaction_source
    assert "_write_json_atomic" in transaction_source
    assert "authorize_context_use" not in transaction_source
    assert "revalidate_granted_context_binding" not in transaction_source


def test_update_receipts_have_one_persistence_repository() -> None:
    assert not (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/update/receipt_store.py"
    ).exists()
    repository = (
        REPOSITORY_ROOT
        / "src/memcommit/persistence/operations/update/receipt_repository.py"
    )
    assert repository.is_file()
    assert "class UpdateReceiptRepository" in repository.read_text(encoding="utf-8")


def test_update_history_is_split_by_read_and_recovery_responsibility() -> None:
    update_root = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/update"
    )
    assert not (update_root / "history.py").exists()

    inspection = (update_root / "inspection.py").read_text(encoding="utf-8")
    recovery = (
        REPOSITORY_ROOT
        / "src/memcommit/application/capabilities/command_recovery/update.py"
    ).read_text(encoding="utf-8")
    assert "def inspect_update" in inspection
    assert "restore_recent_context_command" not in inspection
    assert "def restore_update_command" in recovery
    assert "restore_recent_context_command" in recovery


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
