"""Ownership-only relocation evidence for the exact-name dialog."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path



REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.adapters.console.commands.shared.exact_name_dialog"
CANONICAL_MODULE = "memcommit.adapters.interfaces.tui.components.exact_name_dialog"
LEGACY_SOURCE_SHA256 = "b3875ebf6bdc72cf5f6b9070cb853eb51ce080fc1b5f068af167747d42bf10e1"


def test_legacy_exact_name_dialog_is_an_import_only_module_alias() -> None:
    source_path = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/shared/exact_name_dialog.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "memcommit.adapters.interfaces.tui.components"
        and any(alias.name == "exact_name_dialog" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "sys"
            and target.value.attr == "modules"
            for target in node.targets
        )
        for node in tree.body
    )


def test_canonical_source_matches_pre_move_source_after_import_normalization() -> None:
    source_path = (
        REPOSITORY_ROOT
        / "src/memcommit/adapters/interfaces/tui/components/exact_name_dialog.py"
    )
    source = source_path.read_text(encoding="utf-8")
    canonical_control_import = """from memcommit.adapters.interfaces.tui.components.exact_name import (
    ExactNameFieldControl,
    ExactNameFieldView,
)"""
    legacy_control_import = (
        "from memcommit.commands.tui_primitives import "
        "ExactNameFieldControl, ExactNameFieldView"
    )
    canonical_console_import = (
        "from memcommit.adapters.console.text import "
        "display_escape_text, safe_terminal_text"
    )
    legacy_console_import = (
        "from memcommit.interfaces.console.text import "
        "display_escape_text, safe_terminal_text"
    )
    canonical_theme_import = (
        "from memcommit.adapters.interfaces.tui.core.theme import "
        "MEMCOMMIT_TUI_STYLE"
    )
    legacy_theme_import = (
        "from memcommit.interfaces.tui.core.theme import MEMCOMMIT_TUI_STYLE"
    )

    assert source.count(canonical_control_import) == 1
    assert source.count(canonical_console_import) == 1
    assert source.count(canonical_theme_import) == 1
    normalized = source.replace(canonical_control_import, legacy_control_import)
    # Later adapter staging and console-owner consolidations are also
    # ownership-only moves, so restore every import to the original snapshot.
    normalized = normalized.replace(canonical_console_import, legacy_console_import)
    normalized = normalized.replace(canonical_theme_import, legacy_theme_import)
    # Canonical import sorting places console before components. Restore the
    # former command-hosted order before comparing the complete source digest.
    normalized = normalized.replace(
        f"{legacy_console_import}\n{legacy_control_import}",
        f"{legacy_control_import}\n{legacy_console_import}",
    )

    assert hashlib.sha256(normalized.encode("utf-8")).hexdigest() == (
        LEGACY_SOURCE_SHA256
    )


def test_import_workbench_uses_the_interface_owned_dialog() -> None:
    source_path = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/import_profile/workbench.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "choose_exact_name" for alias in node.names)
    ]

    assert len(imports) == 1
    assert imports[0].module == CANONICAL_MODULE
