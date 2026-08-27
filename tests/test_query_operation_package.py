"""Package contracts for Query's vertical operation slice."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

def test_query_operation_package_import_is_lazy():
    program = """
import sys
import memcommit.application.operations.query

blocked = (
    "memcommit.application.operations.query.ordinary_application",
    "memcommit.application.operations.query.ordinary_runtime",
    "memcommit.application.operations.query.granted_application",
    "memcommit.application.operations.query.granted_runtime",
    "memcommit.application.operations.query.reference_application",
    "memcommit.application.operations.query.reference_runtime",
)
assert not any(name in sys.modules for name in blocked)
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=Path(__file__).parents[1],
        check=True,
    )


def test_command_owned_query_execution_facade_is_retired():
    root = Path(__file__).parents[1] / "src" / "memcommit"

    assert not (root / "commands" / "query_execution.py").exists()
    violations: list[Path] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "memcommit.adapters.console.commands.query_execution"
            ):
                violations.append(path.relative_to(root))
            elif isinstance(node, ast.Import) and any(
                alias.name == "memcommit.adapters.console.commands.query_execution"
                for alias in node.names
            ):
                violations.append(path.relative_to(root))

    assert violations == []
