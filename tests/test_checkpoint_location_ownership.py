"""Ownership checks for the interface-owned checkpoint-location picker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import memcommit.adapters.console.terminal.components.checkpoint_location as legacy_location
from memcommit.adapters.console.terminal.components import checkpoint_location


@pytest.mark.parametrize(
    "first, second",
    (
        (
            "memcommit.adapters.console.terminal.components.checkpoint_location",
            "memcommit.adapters.console.terminal.components.checkpoint_location",
        ),
        (
            "memcommit.adapters.console.terminal.components.checkpoint_location",
            "memcommit.adapters.console.terminal.components.checkpoint_location",
        ),
    ),
)
def test_legacy_and_canonical_imports_share_one_module_in_either_order(
    first: str,
    second: str,
):
    script = (
        "import importlib\n"
        f"first = importlib.import_module({first!r})\n"
        f"second = importlib.import_module({second!r})\n"
        "raise SystemExit(0 if first is second else 1)\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=Path(__file__).resolve().parents[1],
    )

    assert completed.returncode == 0


def test_legacy_path_is_the_canonical_module_object():
    assert legacy_location is checkpoint_location


def test_retired_shared_facade_is_absent():
    facade_path = (
        Path(__file__).resolve().parents[1]
        / "src" / "memcommit" / "adapters" / "console"
        / "shared"
        / "history_location_picker.py"
    )
    assert not facade_path.exists()


def test_legacy_monkeypatch_changes_canonical_picker_globals(monkeypatch):
    sentinel = object()
    observed = {}

    def choose(names, **kwargs):
        observed["names"] = names
        observed.update(kwargs)
        return sentinel

    monkeypatch.setattr(legacy_location, "choose_context", choose)

    selected = checkpoint_location.choose_history_location(
        ("journal",),
        current="journal",
        annotations={"journal": "1 checkpoint"},
        title="DIFF · SELECT A CONTEXT",
        require_tty=False,
    )

    assert selected is sentinel
    assert observed["names"] == ("journal",)
    assert observed["current"] == "journal"
    assert observed["title"] == "DIFF · SELECT A CONTEXT"
