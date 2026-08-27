"""Ownership and compatibility paths for the unified Delete operation."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# This protocol-4 payload predates the ownership relocation. Its GLOBAL opcode
# names memcommit.delete_application.DirectItemDeleteRequest directly.
_LEGACY_DELETE_REQUEST_PICKLE = (
    "gASVVwAAAAAAAACMHG1lbWNvbW1pdC5kZWxldGVfYXBwbGljYXRpb26UjBdE"
    "aXJlY3RJdGVtRGVsZXRlUmVxdWVzdJSTlCmBlF2UKIwIbWVtb3J5LTGUjAVv"
    "d25lcpRlYi4="
)


def test_delete_package_import_does_not_eagerly_load_implementation_modules() -> None:
    source = """
import sys
import memcommit.application.operations.delete

assert "memcommit.application.operations.delete.application" not in sys.modules
assert "memcommit.application.operations.delete.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
