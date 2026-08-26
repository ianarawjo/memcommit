"""Compatibility evidence for the Switch ownership-only relocation."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys

import pytest

from tests.legacy_submodule_assertions import (
    assert_legacy_root_submodule_is_centralized,
)


REPOSITORY_ROOT = Path(__file__).parents[1]
SWITCH_MODULES = (
    (
        "memcommit.switch_application",
        "memcommit.operations.switch.application",
    ),
    (
        "memcommit.switch_runtime",
        "memcommit.operations.switch.runtime",
    ),
)


def test_legacy_switch_application_path_is_the_canonical_module() -> None:
    legacy = importlib.import_module("memcommit.switch_application")
    canonical = importlib.import_module("memcommit.operations.switch.application")

    assert legacy is canonical
    assert legacy.SwitchContextRequest is canonical.SwitchContextRequest
    assert legacy.SwitchContextResult is canonical.SwitchContextResult
    assert legacy.switch_context is canonical.switch_context


def test_legacy_switch_runtime_path_is_the_canonical_module() -> None:
    legacy = importlib.import_module("memcommit.switch_runtime")
    canonical = importlib.import_module("memcommit.operations.switch.runtime")

    assert legacy is canonical
    assert legacy.SwitchSetupSnapshot is canonical.SwitchSetupSnapshot
    assert legacy.prepare_switch is canonical.prepare_switch
    assert legacy.execute_switch_context is canonical.execute_switch_context


@pytest.mark.parametrize("legacy_name,canonical_name", SWITCH_MODULES)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_switch_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name)
        if legacy_first
        else (canonical_name, legacy_name)
    )
    program = (
        "import importlib\n"
        f"first = importlib.import_module({first_name!r})\n"
        f"second = importlib.import_module({second_name!r})\n"
        "assert first is second\n"
    )

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/switch_application.py", "src/memcommit/switch_runtime.py"),
)
def test_legacy_switch_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_switch_package_import_does_not_eagerly_load_implementation_modules() -> None:
    program = (
        "import sys\n"
        "import memcommit.operations.switch\n"
        "assert 'memcommit.operations.switch.application' not in sys.modules\n"
        "assert 'memcommit.operations.switch.runtime' not in sys.modules\n"
    )

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
