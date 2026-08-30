"""Canonical ownership for provider-free exact Dedup."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_MODULE = "memcommit.application.operations.dedup.application"


def test_dedup_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.dedup

assert "memcommit.application.operations.dedup.application" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_dedup_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/dedup.py",
        "src/memcommit/adapters/python_api/_operations/exact_duplicates.py",
        "src/memcommit/adapters/console/commands/dedup/command.py",
        "src/memcommit/adapters/console/commands/find_duplicates/command.py",
        "src/memcommit/application/capabilities/ops.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.exact_dedup" not in source
        assert "memcommit.exact_dedup_application" not in source


def test_exact_dedup_and_semantic_dedun_remain_separate_owners() -> None:
    exact = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/dedup/application.py"
    ).read_text(encoding="utf-8")
    semantic = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/dedun/application.py",
            "src/memcommit/application/operations/dedun/runtime.py",
        )
    )

    exact_imports = {
        node.module
        for node in ast.walk(ast.parse(exact))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "memcommit.application.operations.dedun" not in exact
    assert "memcommit.application.operations.dedup" not in semantic
    assert (
        not {
            "memcommit.findings",
            "memcommit.semantic_provider",
            "memcommit.application.operations.dedun.application",
            "memcommit.application.operations.dedun.runtime",
        }
        & exact_imports
    )
