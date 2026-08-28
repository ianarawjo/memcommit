from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.adapters.console.terminal.components.exact_name_dialog"
CANONICAL_MODULE = "memcommit.adapters.console.terminal.components.exact_name_dialog"


@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_exact_name_dialog_module_identity_is_import_order_independent(
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (LEGACY_MODULE, CANONICAL_MODULE)
        if legacy_first
        else (CANONICAL_MODULE, LEGACY_MODULE)
    )
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_MODULE!r})
canonical = importlib.import_module({CANONICAL_MODULE!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{CANONICAL_MODULE!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_retired_exact_name_dialog_facade_is_absent() -> None:
    source_path = REPOSITORY_ROOT / "src/memcommit/adapters/console/coordination/exact_name_dialog.py"
    assert not source_path.exists()
