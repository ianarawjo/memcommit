"""Physical-root and import contracts for centralized legacy submodules."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from memcommit.compatibility.legacy_submodules import (
    LEGACY_SUBMODULE_ALIASES,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "memcommit"
ROOT_BOUNDARIES = {
    "__init__.py",
    "bootstrap.py",
    "cli.py",
    "context.py",
    "context_locator.py",
    "ops.py",
    "store.py",
}


def test_package_root_contains_only_real_implementation_boundaries() -> None:
    assert {path.name for path in PACKAGE_ROOT.glob("*.py")} == ROOT_BOUNDARIES
    assert len(LEGACY_SUBMODULE_ALIASES) == 242
    for legacy_name in LEGACY_SUBMODULE_ALIASES:
        relative_path = Path(*legacy_name.split(".")).with_suffix(".py")
        assert not (REPOSITORY_ROOT / relative_path).exists()


def test_legacy_finder_is_idempotent_and_preserves_canonical_metadata() -> None:
    program = """
import importlib
import sys
import memcommit
from memcommit.compatibility.legacy_submodules import (
    install_legacy_submodule_aliases,
)

install_legacy_submodule_aliases()
install_legacy_submodule_aliases()
finders = [
    finder
    for finder in sys.meta_path
    if getattr(finder, "marker", None)
    == "memcommit-legacy-submodule-aliases-v1"
]
assert len(finders) == 1

legacy = importlib.import_module("memcommit.atomize_analysis_runtime")
canonical = importlib.import_module(
    "memcommit.operations.atomize.analysis_runtime"
)
assert legacy is canonical
assert legacy.__name__ == "memcommit.operations.atomize.analysis_runtime"
assert legacy.__spec__.name == "memcommit.operations.atomize.analysis_runtime"
assert memcommit.atomize_analysis_runtime is canonical
"""
    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
