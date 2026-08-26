"""Ownership and compatibility paths for semantic Search."""

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
    ("memcommit.find_application", "memcommit.operations.search.application"),
    ("memcommit.find_runtime", "memcommit.operations.search.runtime"),
    (
        "memcommit.find_materialization_application",
        "memcommit.operations.search.materialization_application",
    ),
    (
        "memcommit.find_materialization_runtime",
        "memcommit.operations.search.materialization_runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_search_module_identity_is_independent_of_import_order(
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
    (
        "src/memcommit/find_application.py",
        "src/memcommit/find_runtime.py",
        "src/memcommit/find_materialization_application.py",
        "src/memcommit/find_materialization_runtime.py",
    ),
)
def test_search_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_search_operation_package_import_is_lazy_and_separate_from_literal_find() -> None:
    program = """
import sys
import memcommit.operations.search

blocked = (
    "memcommit.operations.search.application",
    "memcommit.operations.search.runtime",
    "memcommit.operations.search.materialization_application",
    "memcommit.operations.search.materialization_runtime",
    "memcommit.operations.find.literal_application",
    "memcommit.operations.find.literal_runtime",
)
assert not [name for name in blocked if name in sys.modules]
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_search_globals_load_through_aliases() -> None:
    application = importlib.import_module("memcommit.operations.search.application")
    runtime = importlib.import_module("memcommit.operations.search.runtime")
    materialization_application = importlib.import_module(
        "memcommit.operations.search.materialization_application"
    )
    materialization_runtime = importlib.import_module(
        "memcommit.operations.search.materialization_runtime"
    )

    restored_request = pickle.loads(
        b"cmemcommit.find_application\nFindSearchRequest\n."
    )
    restored_source_port = pickle.loads(
        b"cmemcommit.find_runtime\nMemoryStoreFindSearchSourcePort\n."
    )
    restored_materialization_request = pickle.loads(
        b"cmemcommit.find_materialization_application\n"
        b"FindMaterializationRequest\n."
    )
    restored_materialization_port = pickle.loads(
        b"cmemcommit.find_materialization_runtime\n"
        b"MemoryStoreFindMaterializationPort\n."
    )

    assert restored_request is application.FindSearchRequest
    assert restored_source_port is runtime.MemoryStoreFindSearchSourcePort
    assert (
        restored_materialization_request
        is materialization_application.FindMaterializationRequest
    )
    assert (
        restored_materialization_port
        is materialization_runtime.MemoryStoreFindMaterializationPort
    )


def test_production_search_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/api/_operations/search.py",
        "src/memcommit/commands/find/command.py",
        "src/memcommit/commands/find/materialization.py",
        "src/memcommit/commands/find/search_workbench.py",
        "src/memcommit/operations/search/runtime.py",
        "src/memcommit/operations/search/materialization_application.py",
        "src/memcommit/operations/search/materialization_runtime.py",
    )
    legacy_imports = (
        "from memcommit.find_application import",
        "from memcommit.find_runtime import",
        "from memcommit.find_materialization_application import",
        "from memcommit.find_materialization_runtime import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_search_analysis_and_materialization_remain_separate_use_cases() -> None:
    application_source = (
        REPOSITORY_ROOT / "src/memcommit/operations/search/application.py"
    ).read_text(encoding="utf-8")
    materialization_source = (
        REPOSITORY_ROOT
        / "src/memcommit/operations/search/materialization_application.py"
    ).read_text(encoding="utf-8")
    package_source = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/operations/search/application.py",
            "src/memcommit/operations/search/runtime.py",
            "src/memcommit/operations/search/materialization_application.py",
            "src/memcommit/operations/search/materialization_runtime.py",
        )
    )

    assert "materialization" not in application_source.lower()
    assert "memcommit.operations.search.application" in materialization_source
    assert "memcommit.commands" not in package_source
    assert "memcommit.interfaces" not in package_source


def test_selected_public_search_loads_analysis_without_materialization(
    tmp_path: Path,
) -> None:
    program = f"""
import sys
from pathlib import Path
from memcommit.api import MemCommitClient, SemanticContextError

client = MemCommitClient(root=Path({str(tmp_path / 'store')!r}), create=True)
try:
    client.search('needle')
except SemanticContextError:
    pass
else:
    raise AssertionError('Search without a current Context unexpectedly succeeded')

assert 'memcommit.api._operations.search' in sys.modules
assert 'memcommit.operations.search.application' in sys.modules
assert 'memcommit.operations.search.runtime' in sys.modules
assert 'memcommit.operations.search.materialization_application' not in sys.modules
assert 'memcommit.operations.search.materialization_runtime' not in sys.modules
assert 'memcommit.find_application' not in sys.modules
assert 'memcommit.find_runtime' not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
