"""Ownership and compatibility paths for provider-free exact Dedup."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_MODULE = "memcommit.application.operations.exact_dedup.application"


def test_exact_dedup_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.exact_dedup

assert "memcommit.application.operations.exact_dedup.application" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_exact_dedup_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/exact_dedup.py",
        "src/memcommit/adapters/python_api/_operations/exact_duplicates.py",
        "src/memcommit/adapters/console/commands/dedup/command.py",
        "src/memcommit/adapters/console/commands/find_exact_duplicates/command.py",
        "src/memcommit/application/ops.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.exact_dedup" not in source
        assert "memcommit.exact_dedup_application" not in source


def test_exact_dedup_and_semantic_dedun_remain_separate_owners() -> None:
    exact = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/exact_dedup/application.py"
    ).read_text(encoding="utf-8")
    semantic = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/dedup/application.py",
            "src/memcommit/application/operations/dedup/runtime.py",
        )
    )

    exact_imports = {
        node.module
        for node in ast.walk(ast.parse(exact))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "memcommit.application.operations.dedup" not in exact
    assert "memcommit.application.operations.exact_dedup" not in semantic
    assert not {
        "memcommit.findings",
        "memcommit.semantic_provider",
        "memcommit.application.operations.dedup.application",
        "memcommit.application.operations.dedup.runtime",
    } & exact_imports
