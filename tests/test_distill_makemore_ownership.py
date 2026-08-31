"""Ownership and compatibility paths for Distill and Makemore."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("operation", ("distill", "makemore"))
def test_operation_package_import_is_lazy(operation: str) -> None:
    program = f"""
import sys
import memcommit.application.operations.semantic_updates.derive.{operation}

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.application.operations.semantic_updates.derive.{operation}.")
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
        "src/memcommit/adapters/python_api/_operations/makemore.py",
        "src/memcommit/adapters/console/commands/semantic_updates/derive/distill/command.py",
        "src/memcommit/adapters/console/commands/semantic_updates/derive/makemore/command.py",
        "src/memcommit/adapters/console/commands/semantic_updates/derive/distill/impact.py",
        "src/memcommit/adapters/console/commands/semantic_updates/derive/makemore/impact.py",
        "src/memcommit/application/operations/ground/distill.py",
        "src/memcommit/application/operations/ground/makemore.py",
        "src/memcommit/adapters/console/commands/semantic_updates/derive/makemore/proposal.py",
        "src/memcommit/adapters/console/commands/semantic_updates/derive/makemore/viewer/projection.py",
        "src/memcommit/adapters/console/commands/semantic_updates/derive/makemore/viewer/screen.py",
        "src/memcommit/application/operations/semantic_updates/derive/distill/runtime.py",
        "src/memcommit/application/operations/semantic_updates/derive/makemore/runtime.py",
        "src/memcommit/application/operations/semantic_updates/derive/makemore/add_runtime.py",
    )
    legacy_imports = (
        "from memcommit.distill_application import",
        "from memcommit.distill_runtime import",
        "from memcommit.makemore_application import",
        "from memcommit.makemore_runtime import",
        "from memcommit.makemore_add_runtime import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_distill_and_makemore_keep_distinct_execution_contracts() -> None:
    distill_source = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/semantic_updates/derive/distill/application.py",
            "src/memcommit/application/operations/semantic_updates/derive/distill/runtime.py",
        )
    )
    makemore_application = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/semantic_updates/derive/makemore/application.py"
    ).read_text(encoding="utf-8")
    makemore_runtime = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/semantic_updates/derive/makemore/runtime.py"
    ).read_text(encoding="utf-8")
    makemore_add_runtime = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/semantic_updates/derive/makemore/add_runtime.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.application.operations.semantic_updates.derive.makemore" not in distill_source
    assert "memcommit.application.operations.semantic_updates.derive.distill" not in (
        makemore_application + makemore_runtime + makemore_add_runtime
    )
    assert "memorize_semantic_result" not in makemore_runtime
    assert "MemoryStore" not in makemore_runtime
    assert (
        "from memcommit.application.operations.semantic_updates.derive.makemore.runtime import"
        in makemore_add_runtime
    )
    assert "memorize_semantic_result" in makemore_add_runtime
    assert "memcommit.application.operations.add" not in makemore_add_runtime
    assert (
        "memcommit.application.capabilities.semantic_result_memorization"
        in makemore_add_runtime
    )
    assert "prepare_distill_add" in distill_source
    assert "apply_prepared_distill_add" in distill_source


def test_operation_owners_do_not_depend_on_command_or_interface_adapters() -> None:
    package_source = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("distill", "makemore")
        for path in sorted(
            (REPOSITORY_ROOT / "src/memcommit/application/operations" / package).glob(
                "*.py"
            )
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
