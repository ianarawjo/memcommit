"""Ownership contracts for shared quality-finding CLI rendering."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "memcommit"
LEGACY_MODULE = "memcommit.commands.shared.findings_render"
OWNER_MODULE = "memcommit.interfaces.cli.quality_findings"


@pytest.mark.parametrize(
    "first,second",
    ((LEGACY_MODULE, OWNER_MODULE), (OWNER_MODULE, LEGACY_MODULE)),
)
def test_legacy_and_owner_imports_share_module_identity(first: str, second: str) -> None:
    program = (
        "import importlib\n"
        f"first = importlib.import_module({first!r})\n"
        f"second = importlib.import_module({second!r})\n"
        "assert first is second\n"
    )

    subprocess.run([sys.executable, "-c", program], cwd=ROOT, check=True)


def test_legacy_facade_contains_no_implementation() -> None:
    path = PACKAGE / "commands" / "shared" / "findings_render.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_quality_finding_commands_import_the_interface_owner() -> None:
    for filename in (
        "find_ambiguities/command.py",
        "find_conflicts/command.py",
        "find_duplicates/command.py",
        "find_exact_duplicates/command.py",
    ):
        source = (PACKAGE / "commands" / filename).read_text(encoding="utf-8")
        assert "from memcommit.interfaces.cli.quality_findings import (" in source
        assert "from memcommit.commands.shared.findings_render import (" not in source
