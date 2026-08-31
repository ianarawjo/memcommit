"""Ownership and compatibility paths for read-only Summarize."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_summarize_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.summarize

assert "memcommit.application.operations.summarize.application" not in sys.modules
assert "memcommit.application.operations.summarize.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_summarize_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/summarize/command.py",
        "src/memcommit/application/operations/distill/application.py",
        "src/memcommit/application/operations/distill/runtime.py",
        "src/memcommit/study_scenarios/legacy/prewarm/generation/summarize_exact_matrix.py",
        "src/memcommit/application/operations/ground/distill.py",
        "src/memcommit/adapters/console/commands/summarize/scope_label.py",
        "src/memcommit/adapters/console/commands/summarize/presentation.py",
        "src/memcommit/adapters/console/commands/summarize/workbench/presentation.py",
        "src/memcommit/adapters/console/commands/summarize/workbench/model.py",
        "src/memcommit/adapters/console/commands/summarize/workbench/screen.py",
        "src/memcommit/application/operations/summarize/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.summarize_application import" not in source
        assert "from memcommit.summarize_runtime import" not in source


def test_summarize_console_owns_presentation_and_workbench_without_facades() -> None:
    command_root = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/summarize"
    retired_tui_root = (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/tui/operations/summarize"
    )

    assert (command_root / "presentation.py").is_file()
    assert (command_root / "workbench/model.py").is_file()
    assert (command_root / "workbench/presentation.py").is_file()
    assert (command_root / "workbench/screen.py").is_file()
    assert not tuple(retired_tui_root.glob("*.py"))
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/summarize.py"
    ).exists()
