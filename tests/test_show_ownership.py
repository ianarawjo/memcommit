"""Ownership and compatibility paths for read-only Show."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_show_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.show

assert "memcommit.application.operations.show.application" not in sys.modules
assert "memcommit.application.operations.show.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_show_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/show.py",
        "src/memcommit/adapters/console/commands/show/command.py",
        "src/memcommit/adapters/interfaces/cli/show.py",
        "src/memcommit/application/operations/show/runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.show_application import" not in source
        assert "from memcommit.show_runtime import" not in source


def test_show_owner_retains_read_only_effect_boundary() -> None:
    application_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/show/application.py"
    ).read_text(encoding="utf-8")
    runtime_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/show/runtime.py"
    ).read_text(encoding="utf-8")
    combined = application_source + runtime_source

    assert "memcommit.adapters.console.commands" not in combined
    assert "memcommit.adapters.interfaces" not in combined
    assert "provider.complete" not in combined
    assert "store.save(" not in runtime_source
    assert "set_current(" not in runtime_source
