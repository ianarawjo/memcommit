"""Ownership and compatibility paths for the exact-command approval shell."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_NAME = "memcommit.adapters.console.terminal.components.exact_command_review.shell"
CANONICAL_NAME = "memcommit.adapters.console.terminal.components.exact_command_review.shell"


@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_review_shell_module_identity_is_independent_of_import_order(
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (LEGACY_NAME, CANONICAL_NAME) if legacy_first else (CANONICAL_NAME, LEGACY_NAME)
    )
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_NAME!r})
canonical = importlib.import_module({CANONICAL_NAME!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_NAME!r}] is canonical
assert sys.modules[{CANONICAL_NAME!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_review_shell_is_exported_by_the_component_package() -> None:
    legacy = importlib.import_module(LEGACY_NAME)
    canonical = importlib.import_module(CANONICAL_NAME)
    package = importlib.import_module(
        "memcommit.adapters.console.terminal.components.exact_command_review"
    )

    assert legacy is canonical
    assert legacy.approve_exact_command is canonical.approve_exact_command
    assert package.approve_exact_command is canonical.approve_exact_command


def test_retired_review_shell_facade_is_absent() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/adapters/console/coordination/exact_command_review_shell.py"
    assert not path.exists()
