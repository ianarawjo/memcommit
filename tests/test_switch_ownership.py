"""Compatibility evidence for the Switch ownership-only relocation."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).parents[1]


def test_switch_package_import_does_not_eagerly_load_implementation_modules() -> None:
    program = (
        "import sys\n"
        "import memcommit.application.operations.browse_navigate.switch\n"
        "assert 'memcommit.application.operations.browse_navigate.switch.application' not in sys.modules\n"
        "assert 'memcommit.application.operations.browse_navigate.switch.runtime' not in sys.modules\n"
    )

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
