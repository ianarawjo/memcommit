"""Ownership contracts for the interface-owned Memory report picker."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.adapters.console.terminal.components.memory_report_picker"
OWNER_MODULE = "memcommit.adapters.console.terminal.components.memory_report_picker"


@pytest.mark.parametrize(
    "first_name,second_name",
    ((LEGACY_MODULE, OWNER_MODULE), (OWNER_MODULE, LEGACY_MODULE)),
    ids=("old-first", "new-first"),
)
def test_memory_report_picker_identity_is_independent_of_import_order(
    first_name: str,
    second_name: str,
) -> None:
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_MODULE!r})
canonical = importlib.import_module({OWNER_MODULE!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{OWNER_MODULE!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_memory_picker_legacy_path_is_the_canonical_module_object() -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(OWNER_MODULE)

    assert legacy is canonical


def test_retired_memory_picker_facade_is_absent() -> None:
    source_path = REPOSITORY_ROOT / "src/memcommit/adapters/console/coordination/memory_picker.py"
    assert not source_path.exists()


def test_legacy_monkeypatch_changes_canonical_picker_globals(monkeypatch) -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(OWNER_MODULE)
    observed: dict[str, object] = {}

    def choose(names, **kwargs):
        observed["names"] = names
        observed.update(kwargs)
        return None

    monkeypatch.setattr(legacy, "choose_context", choose)
    item = canonical.ScopedMemoryPickerItem(
        context_name="notes",
        uid="memory-1",
        content="one",
        status="CURRENT",
    )

    selected = canonical.choose_memory_report_target(
        (item,),
        context_name="notes",
        operation="trace",
        require_tty=False,
    )

    assert selected is None
    assert observed["names"] == ("notes",)
    assert observed["current"] == "notes"
    assert observed["title"] == "TRACE · SELECT A MEMORY · notes"
