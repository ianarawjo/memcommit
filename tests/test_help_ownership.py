"""Ownership and compatibility paths for exact and semantic Help."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import pickle
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    ("memcommit.help_application", "memcommit.operations.help.application"),
    (
        "memcommit.help_lookup_application",
        "memcommit.operations.help.lookup_application",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_help_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name)
        if legacy_first
        else (canonical_name, legacy_name)
    )
    program = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({legacy_name!r})
canonical = importlib.import_module({canonical_name!r})

assert first is second
assert legacy is canonical
assert sys.modules[{legacy_name!r}] is canonical
assert sys.modules[{canonical_name!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


@pytest.mark.parametrize(
    "relative_path",
    ("memcommit/help_application.py", "memcommit/help_lookup_application.py"),
)
def test_help_legacy_facades_define_no_behavior(relative_path: str) -> None:
    path = REPOSITORY_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_help_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.help

assert "memcommit.operations.help.application" not in sys.modules
assert "memcommit.operations.help.lookup_application" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_help_globals_load_through_aliases() -> None:
    application = importlib.import_module("memcommit.operations.help.application")
    lookup = importlib.import_module("memcommit.operations.help.lookup_application")

    restored_error = pickle.loads(
        b"cmemcommit.help_application\nHelpApplicationInputError\n."
    )
    restored_plan = pickle.loads(
        b"cmemcommit.help_lookup_application\nHelpLookupPlan\n."
    )

    assert restored_error is application.HelpApplicationInputError
    assert restored_plan is lookup.HelpLookupPlan


def test_production_help_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "memcommit/api/_operations/help.py",
        "memcommit/interfaces/agent/help.py",
        "memcommit/interfaces/tui/operations/help/inventory.py",
        "memcommit/operations/help/lookup_application.py",
    )
    legacy_imports = (
        "from memcommit.help_application import",
        "from memcommit.help_lookup_application import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_help_owner_preserves_catalog_and_injected_provider_boundaries() -> None:
    application_source = (
        REPOSITORY_ROOT / "memcommit/operations/help/application.py"
    ).read_text(encoding="utf-8")
    lookup_source = (
        REPOSITORY_ROOT / "memcommit/operations/help/lookup_application.py"
    ).read_text(encoding="utf-8")
    combined = application_source + lookup_source

    assert "memcommit.commands" not in combined
    assert "memcommit.interfaces" not in combined
    assert "memcommit.store" not in combined
    assert "memcommit.infrastructure" not in combined
    assert "provider.complete" not in application_source
    assert "provider.complete" in lookup_source
    assert "connect_help_provider" not in lookup_source
    assert "memcommit.operations.help.application" in lookup_source


def test_selected_public_help_loads_only_exact_catalog_application(
    tmp_path: Path,
) -> None:
    program = f"""
import sys
from pathlib import Path
from memcommit.api import MemCommitClient

root = Path({str(tmp_path / 'missing-store')!r})
result = MemCommitClient(root=root).describe_operation('compare')
assert result.name == 'compare'
assert not root.exists()
assert 'memcommit.api._operations.help' in sys.modules
assert 'memcommit.operations.help.application' in sys.modules
assert 'memcommit.operations.help.lookup_application' not in sys.modules
assert 'memcommit.help_application' not in sys.modules
assert 'memcommit.help_lookup_application' not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
