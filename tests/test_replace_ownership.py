"""Ownership and compatibility paths for deterministic Replace."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# This protocol-4 payload was created before the ownership relocation. Its
# GLOBAL opcode names memcommit.replace_application.ReplaceRequest directly.
_LEGACY_REPLACE_REQUEST_PICKLE = (
    "gASVZQAAAAAAAACMHW1lbWNvbW1pdC5yZXBsYWNlX2FwcGxpY2F0aW9ulIwO"
    "UmVwbGFjZVJlcXVlc3SUk5QpgZRdlCiMBm5lZWRsZZSMBnRocmVhZJSMBWFs"
    "cGhhlIWUiYmMB0xJVEVSQUyUiWViLg=="
)


def test_replace_package_import_does_not_eagerly_load_implementation_modules() -> None:
    source = """
import sys
import memcommit.application.operations.direct_changes.replace

assert "memcommit.application.operations.direct_changes.replace.application" not in sys.modules
assert "memcommit.application.operations.direct_changes.replace.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
