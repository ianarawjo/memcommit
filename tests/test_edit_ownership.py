"""Ownership and compatibility paths for the Edit operation slice."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_edit_command_owns_its_workbench_without_a_tui_facade() -> None:
    command_root = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/edit"
    retired_root = (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/tui/operations/edit"
    )

    assert (command_root / "command.py").is_file()
    assert (command_root / "input_records.py").is_file()
    assert (command_root / "workbench/model.py").is_file()
    assert (command_root / "workbench/setup.py").is_file()
    assert (command_root / "workbench/screen.py").is_file()
    assert not tuple(retired_root.glob("*.py"))
