"""Compatibility evidence for the Status ownership-only relocation."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[1]


def test_status_plain_presentation_is_command_owned_without_a_facade() -> None:
    presentation = (
        REPOSITORY_ROOT
        / "src/memcommit/adapters/console/commands/status/presentation.py"
    )
    former_interface = (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/status.py"
    )
    command = (
        REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/status/command.py"
    )

    assert presentation.is_file()
    assert not former_interface.exists()
    command_source = command.read_text(encoding="utf-8")
    assert (
        "from memcommit.adapters.console.commands.status.presentation "
        "import render_status"
    ) in command_source
    assert "memcommit.adapters.interfaces.cli.status" not in command_source
