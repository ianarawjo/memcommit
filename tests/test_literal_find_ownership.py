"""Ownership and compatibility paths for provider-free Literal Find."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import pickle
import subprocess
import sys

import pytest

from tests.legacy_submodule_assertions import (
    assert_legacy_root_submodule_is_centralized,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    (
        "memcommit.literal_find_application",
        "memcommit.operations.find.literal_application",
    ),
    (
        "memcommit.literal_find_runtime",
        "memcommit.operations.find.literal_runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_literal_find_module_identity_is_independent_of_import_order(
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


def test_literal_find_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module(
        "memcommit.literal_find_application"
    )
    canonical_application = importlib.import_module(
        "memcommit.operations.find.literal_application"
    )
    legacy_runtime = importlib.import_module("memcommit.literal_find_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.operations.find.literal_runtime"
    )

    assert legacy_application is canonical_application
    assert (
        legacy_application.LiteralFindRequest
        is canonical_application.LiteralFindRequest
    )
    assert legacy_application.run_literal_find is canonical_application.run_literal_find
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.ReadableLiteralFindSourcePort
        is canonical_runtime.ReadableLiteralFindSourcePort
    )
    assert legacy_runtime.execute_literal_find is canonical_runtime.execute_literal_find


@pytest.mark.parametrize(
    "relative_path",
    (
        "memcommit/literal_find_application.py",
        "memcommit/literal_find_runtime.py",
    ),
)
def test_literal_find_legacy_facades_define_no_behavior(
    relative_path: str,
) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_find_operation_package_import_keeps_literal_slice_lazy() -> None:
    program = """
import sys
import memcommit.operations.find

assert "memcommit.operations.find.literal_application" not in sys.modules
assert "memcommit.operations.find.literal_runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_literal_find_globals_load_through_aliases() -> None:
    canonical_application = importlib.import_module(
        "memcommit.operations.find.literal_application"
    )
    canonical_runtime = importlib.import_module(
        "memcommit.operations.find.literal_runtime"
    )

    restored_request = pickle.loads(
        b"cmemcommit.literal_find_application\nLiteralFindRequest\n."
    )
    restored_port = pickle.loads(
        b"cmemcommit.literal_find_runtime\nReadableLiteralFindSourcePort\n."
    )

    assert restored_request is canonical_application.LiteralFindRequest
    assert restored_port is canonical_runtime.ReadableLiteralFindSourcePort


def test_production_literal_find_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "memcommit/api/_operations/find.py",
        "memcommit/commands/literal_find.py",
        "memcommit/interfaces/literal_find.py",
        "memcommit/interfaces/cli/find.py",
        "memcommit/interfaces/tui/operations/find/compact.py",
        "memcommit/interfaces/tui/operations/find/model.py",
        "memcommit/interfaces/tui/operations/find/screen.py",
        "memcommit/operations/find/literal_runtime.py",
        "memcommit/operations/replace/application.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.literal_find_application import" not in source
        assert "from memcommit.literal_find_runtime import" not in source


def test_literal_find_does_not_absorb_semantic_search_or_interfaces() -> None:
    application_source = (
        REPOSITORY_ROOT / "memcommit/operations/find/literal_application.py"
    ).read_text(encoding="utf-8")
    runtime_source = (
        REPOSITORY_ROOT / "memcommit/operations/find/literal_runtime.py"
    ).read_text(encoding="utf-8")
    combined = application_source + runtime_source

    assert "memcommit.operations.search.application" not in combined
    assert "memcommit.operations.search.runtime" not in combined
    assert "memcommit.commands" not in combined
    assert "memcommit.interfaces" not in combined
    assert "provider.complete" not in combined


def test_selected_public_find_loads_canonical_modules_without_aliases(
    tmp_path: Path,
) -> None:
    program = f"""
import sys
from pathlib import Path
from memcommit.api import FindContextError, MemCommitClient

client = MemCommitClient(root=Path({str(tmp_path / 'store')!r}), create=True)
try:
    client.find('needle')
except FindContextError:
    pass
else:
    raise AssertionError('Find without a current Context unexpectedly succeeded')

assert 'memcommit.api._operations.find' in sys.modules
assert 'memcommit.operations.find.literal_application' in sys.modules
assert 'memcommit.operations.find.literal_runtime' in sys.modules
assert 'memcommit.literal_find_application' not in sys.modules
assert 'memcommit.literal_find_runtime' not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
