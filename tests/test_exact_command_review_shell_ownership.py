"""Ownership and compatibility paths for the exact-command approval shell."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_NAME = "memcommit.adapters.console.terminal.components.exact_command_review.shell"
CANONICAL_NAME = "memcommit.adapters.console.terminal.components.command_editor.exact_command_review.shell"


def test_review_shell_has_only_the_command_editor_import_path() -> None:
    source = f"""
import importlib
import sys

canonical = importlib.import_module({CANONICAL_NAME!r})

assert sys.modules[{CANONICAL_NAME!r}] is canonical
try:
    importlib.import_module({LEGACY_NAME!r})
except ModuleNotFoundError:
    pass
else:
    raise AssertionError("retired exact-command review path remains importable")
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_review_shell_is_exported_by_the_component_package() -> None:
    canonical = importlib.import_module(CANONICAL_NAME)
    package = importlib.import_module(
        "memcommit.adapters.console.terminal.components.command_editor.exact_command_review"
    )

    assert package.approve_exact_command is canonical.approve_exact_command


def test_retired_review_shell_facade_is_absent() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/adapters/console/coordination/exact_command_review_shell.py"
    assert not path.exists()
