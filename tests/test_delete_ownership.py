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
import memcommit.application.operations.direct_changes.delete

assert "memcommit.application.operations.direct_changes.delete.application" not in sys.modules
assert "memcommit.application.operations.direct_changes.delete.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_delete_console_owns_review_receipt_and_picker_without_facades() -> None:
    command_root = (
        REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/direct_changes/delete"
    )

    assert (command_root / "review.py").is_file()
    assert (command_root / "receipt.py").is_file()
    assert (command_root / "picker.py").is_file()
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/delete.py"
    ).exists()
    assert not (
        REPOSITORY_ROOT
        / "src/memcommit/adapters/interfaces/tui/operations/delete.py"
    ).exists()
