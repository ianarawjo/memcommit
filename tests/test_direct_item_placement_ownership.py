"""Ownership and compatibility paths for direct-item placement controls."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_NAME = "memcommit.adapters.console.terminal.components.direct_item_placement"
CANONICAL_NAME = "memcommit.adapters.console.terminal.components.direct_item_placement"


@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_placement_module_identity_is_independent_of_import_order(
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


def test_legacy_placement_path_exposes_canonical_objects() -> None:
    legacy = importlib.import_module(LEGACY_NAME)
    canonical = importlib.import_module(CANONICAL_NAME)

    assert legacy is canonical
    for name in canonical.__all__:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_retired_placement_facade_is_absent() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/adapters/console/coordination/direct_item_placement.py"
    assert not path.exists()
