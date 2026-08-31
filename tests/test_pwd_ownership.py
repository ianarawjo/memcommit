"""Console ownership checks for ``mem pwd`` presentation."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_pwd_command_owns_plain_presentation_without_a_cli_facade() -> None:
    command_root = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/browse_navigate/pwd"

    assert (command_root / "command.py").is_file()
    assert (command_root / "presentation.py").is_file()
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/pwd.py"
    ).exists()
