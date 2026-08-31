"""Ownership and compatibility paths for general and Ground Fit."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_fit_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.quality_resolution.validate.fit

assert "memcommit.application.operations.quality_resolution.validate.fit.application" not in sys.modules
assert "memcommit.application.operations.quality_resolution.validate.fit.runtime" not in sys.modules
assert "memcommit.application.operations.quality_resolution.validate.fit.ground_report" not in sys.modules
assert "memcommit.application.operations.quality_resolution.validate.fit.judgment" not in sys.modules
assert "memcommit.application.operations.quality_resolution.validate.fit.coherence" not in sys.modules
assert "memcommit.application.operations.quality_resolution.validate.fit.store" not in sys.modules
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
        "src/memcommit/adapters/console/commands/quality_resolution/validate/fit/command.py",
        "src/memcommit/adapters/console/commands/quality_resolution/diagnose/find_conflicts/command.py",
        "src/memcommit/adapters/console/commands/quality_resolution/repair/resolve/impact.py",
        "src/memcommit/adapters/console/commands/quality_resolution/repair/resolve/command.py",
        "src/memcommit/application/operations/semantic_updates/derive/makemore/model.py",
        "src/memcommit/application/operations/ground/workspace_fit.py",
        "src/memcommit/application/operations/quality_resolution/validate/fit/application.py",
        "src/memcommit/application/operations/quality_resolution/validate/fit/runtime.py",
        "src/memcommit/application/operations/quality_resolution/repair/resolve/application.py",
        "src/memcommit/application/operations/quality_resolution/repair/resolve/semantic.py",
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
