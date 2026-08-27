"""Ownership and compatibility paths for the Merge operation slice."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_merge_package_import_is_lazy() -> None:
    source = """
import sys
import memcommit.application.operations.merge

assert "memcommit.application.operations.merge.application" not in sys.modules
assert "memcommit.application.operations.merge.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
