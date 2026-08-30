"""Ownership and compatibility paths for Distill and Elaborate."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("operation", ("distill", "elaborate"))
def test_operation_package_import_is_lazy(operation: str) -> None:
    program = f"""
import sys
import memcommit.application.operations.{operation}

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.application.operations.{operation}.")
]
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_consumers_use_operation_owners() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/distill.py",
        "src/memcommit/adapters/python_api/_operations/elaborate.py",
        "src/memcommit/adapters/console/commands/distill/command.py",
        "src/memcommit/adapters/console/commands/elaborate/command.py",
        "src/memcommit/adapters/console/commands/distill/impact.py",
        "src/memcommit/adapters/console/commands/elaborate/impact.py",
        "src/memcommit/application/operations/ground/distill.py",
        "src/memcommit/application/operations/ground/elaborate.py",
        "src/memcommit/adapters/console/commands/elaborate/proposal.py",
        "src/memcommit/adapters/console/commands/elaborate/runner.py",
        "src/memcommit/adapters/console/commands/elaborate/viewer/projection.py",
        "src/memcommit/adapters/console/commands/elaborate/viewer/screen.py",
        "src/memcommit/application/operations/distill/runtime.py",
        "src/memcommit/application/operations/elaborate/runtime.py",
        "src/memcommit/application/operations/elaborate/add_runtime.py",
    )
    legacy_imports = (
        "from memcommit.distill_application import",
        "from memcommit.distill_runtime import",
        "from memcommit.elaborate_application import",
        "from memcommit.elaborate_runtime import",
        "from memcommit.elaborate_add_runtime import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_distill_and_elaborate_keep_distinct_execution_contracts() -> None:
    distill_source = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/distill/application.py",
            "src/memcommit/application/operations/distill/runtime.py",
        )
    )
    elaborate_application = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/elaborate/application.py"
    ).read_text(encoding="utf-8")
    elaborate_runtime = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/elaborate/runtime.py"
    ).read_text(encoding="utf-8")
    elaborate_add_runtime = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/elaborate/add_runtime.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.application.operations.elaborate" not in distill_source
    assert "memcommit.application.operations.distill" not in (
        elaborate_application + elaborate_runtime + elaborate_add_runtime
    )
    assert "memorize_semantic_result" not in elaborate_runtime
    assert "MemoryStore" not in elaborate_runtime
    assert "from memcommit.application.operations.elaborate.runtime import" in elaborate_add_runtime
    assert "memorize_semantic_result" in elaborate_add_runtime
    assert "memcommit.application.operations.add" not in elaborate_add_runtime
    assert (
        "memcommit.application.capabilities.semantic_result_memorization"
        in elaborate_add_runtime
    )
    assert "prepare_distill_add" in distill_source
    assert "apply_prepared_distill_add" in distill_source


def test_operation_owners_do_not_depend_on_command_or_interface_adapters() -> None:
    package_source = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("distill", "elaborate")
        for path in sorted(
            (REPOSITORY_ROOT / "src/memcommit/application/operations" / package).glob("*.py")
        )
    )

    assert "memcommit.adapters.console.commands" not in package_source
    assert "memcommit.adapters.interfaces" not in package_source


def test_semantic_result_memorization_is_not_owned_by_add() -> None:
    source = REPOSITORY_ROOT / "src/memcommit/application"
    capability = source / "capabilities/semantic_result_memorization.py"
    retired = source / "operations/add/semantic_runtime.py"

    assert capability.is_file()
    assert not retired.exists()
    capability_source = capability.read_text(encoding="utf-8")
    assert "def memorize_semantic_result(" in capability_source
    assert "def append_semantic_memories(" not in capability_source
