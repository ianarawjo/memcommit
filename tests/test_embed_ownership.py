"""Ownership and compatibility paths for live Context and Memory Embed."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_embed_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.embed

assert "memcommit.application.operations.embed.application" not in sys.modules
assert "memcommit.application.operations.embed.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_embed_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/embed.py",
        "src/memcommit/adapters/console/commands/embed/command.py",
        "src/memcommit/adapters/console/commands/embed/workbench/screen.py",
        "src/memcommit/application/operations/embed/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.embed_application import" not in source
        assert "from memcommit.embed_runtime import" not in source


def test_reference_and_embed_remain_separate_operation_packages() -> None:
    for relative_path in (
        "src/memcommit/application/operations/reference/application.py",
        "src/memcommit/application/operations/reference/runtime.py",
        "src/memcommit/application/operations/embed/application.py",
        "src/memcommit/application/operations/embed/runtime.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        if "/reference/" in relative_path:
            assert "memcommit.application.operations.embed" not in source
        else:
            assert "memcommit.application.operations.reference" not in source
