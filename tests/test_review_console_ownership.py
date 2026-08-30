"""Console ownership boundaries for saved Review-session presentation."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_review_command_owns_snapshot_without_interface_facade() -> None:
    command_root = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/review"

    assert (command_root / "snapshot.py").is_file()
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/review.py"
    ).exists()


def test_terminal_review_contracts_have_one_shared_console_owner() -> None:
    shared_module = (
        REPOSITORY_ROOT / "src/memcommit/adapters/console/coordination/review.py"
    )
    old_package = (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/tui/workbenches/review"
    )

    assert shared_module.is_file()
    assert not tuple(old_package.glob("*.py"))
    source = shared_module.read_text(encoding="utf-8")
    assert "memcommit.adapters.console.commands" not in source
    assert "memcommit.adapters.interfaces" not in source


def test_review_atomize_and_impact_import_the_shared_contract_directly() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/review/command.py",
        "src/memcommit/adapters/console/commands/review/snapshot.py",
        "src/memcommit/adapters/console/commands/atomize/review.py",
        "src/memcommit/adapters/console/commands/atomize/impact.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.adapters.interfaces.tui.workbenches.review" not in source
    assert "memcommit.adapters.console.commands.review.snapshot" in (
        REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/review/command.py"
    ).read_text(encoding="utf-8")
