"""Ownership and compatibility paths for general and Ground Fit."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_fit_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.fit

assert "memcommit.application.operations.fit.application" not in sys.modules
assert "memcommit.application.operations.fit.runtime" not in sys.modules
assert "memcommit.application.operations.fit.ground_report" not in sys.modules
assert "memcommit.application.operations.fit.judgment" not in sys.modules
assert "memcommit.application.operations.fit.coherence" not in sys.modules
assert "memcommit.application.operations.fit.store" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_fit_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/fit.py",
        "src/memcommit/adapters/python_api/_operations/resolve.py",
        "src/memcommit/adapters/console/commands/fit/command.py",
        "src/memcommit/adapters/console/commands/find_conflicts/command.py",
        "src/memcommit/adapters/console/commands/ground/command/workflow/session/dialogue.py",
        "src/memcommit/adapters/console/commands/ground/named_shell/runtime/fit_coordinator.py",
        "src/memcommit/adapters/console/commands/ground/named_shell/runtime/state.py",
        "src/memcommit/adapters/console/commands/ground/named_shell/runtime/turn_controller.py",
        "src/memcommit/adapters/console/commands/resolve/impact.py",
        "src/memcommit/adapters/console/commands/resolve/command.py",
        "src/memcommit/application/operations/elaborate/model.py",
        "src/memcommit/application/operations/ground/workspace_fit.py",
        "src/memcommit/application/operations/fit/application.py",
        "src/memcommit/application/operations/fit/runtime.py",
        "src/memcommit/application/operations/resolve/application.py",
        "src/memcommit/application/operations/resolve/semantic.py",
    )
    legacy_imports = (
        "from memcommit.fit import",
        "from memcommit.fit_judgment import",
        "from memcommit.fit_coherence import",
        "from memcommit.fit_store import",
        "from memcommit.fit_application import",
        "from memcommit.fit_runtime import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for legacy_import in legacy_imports:
            assert legacy_import not in source
