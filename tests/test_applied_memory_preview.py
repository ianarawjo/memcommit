from __future__ import annotations

import ast
from pathlib import Path

import pytest

from memcommit.adapters.console.terminal.components.applied_memory_preview import (
    applied_memory_preview_lines,
)
from memcommit.adapters.console.terminal.core.theme import memory_object_color_rgb
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import SEMANTIC_VIEWER_STYLE


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SHARED_MODULE = "memcommit.adapters.console.terminal.components.applied_memory_preview"
FORMER_MODULE = "memcommit.adapters.interfaces.cli.semantic_add"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def test_distill_and_makemore_import_the_shared_preview_owner() -> None:
    commands = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands"

    for operation in ("distill", "makemore"):
        imported = _imports(commands / operation / "command.py")
        assert SHARED_MODULE in imported
        assert FORMER_MODULE not in imported


def test_shared_preview_has_no_command_dependency_or_compatibility_facade() -> None:
    shared = (
        REPOSITORY_ROOT
        / "src/memcommit/adapters/console/terminal/components/applied_memory_preview.py"
    )
    former = REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/semantic_add.py"

    assert shared.is_file()
    assert not former.exists()
    assert not any(
        module.startswith("memcommit.adapters.console.commands")
        for module in _imports(shared)
    )


def test_applied_memory_preview_shows_twenty_then_reports_the_remainder() -> None:
    uids = tuple(f"{index:08d}-memory" for index in range(23))
    contents = tuple(f"Memory {index}" for index in range(23))

    lines = applied_memory_preview_lines(uids, contents)

    assert len(lines) == 21
    assert lines[0] == "  [memory 00000000] Memory 0"
    assert lines[19] == "  [memory 00000019] Memory 19"
    assert lines[20] == "  … AND 3 MORE"
    assert all("00000020" not in line for line in lines)


def test_applied_memory_preview_folds_and_escapes_content_on_one_line() -> None:
    lines = applied_memory_preview_lines(
        ("12345678-memory",),
        ("first\n  second\x1b",),
    )

    assert lines == (r"  [memory 12345678] first second\x1b",)


def test_applied_memory_preview_rejects_misaligned_identity_and_content() -> None:
    with pytest.raises(ValueError, match="identities and contents must align"):
        applied_memory_preview_lines(("12345678-memory",), ())


def test_applied_memory_preview_uses_the_shared_memory_object_foreground() -> None:
    attrs = SEMANTIC_VIEWER_STYLE.get_attrs_for_style_str("class:memory-object")

    assert memory_object_color_rgb() == tuple(bytes.fromhex(attrs.color))
