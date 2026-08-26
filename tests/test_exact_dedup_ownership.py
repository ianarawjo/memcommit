"""Ownership and compatibility paths for provider-free exact Dedup."""

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
CANONICAL_MODULE = "memcommit.operations.exact_dedup.application"
LEGACY_MODULES = (
    "memcommit.exact_dedup",
    "memcommit.exact_dedup_application",
)


@pytest.mark.parametrize("legacy_name", LEGACY_MODULES)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_exact_dedup_module_identity_is_independent_of_import_order(
    legacy_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, CANONICAL_MODULE)
        if legacy_first
        else (CANONICAL_MODULE, legacy_name)
    )
    program = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({legacy_name!r})
canonical = importlib.import_module({CANONICAL_MODULE!r})

assert first is second
assert legacy is canonical
assert sys.modules[{legacy_name!r}] is canonical
assert sys.modules[{CANONICAL_MODULE!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_exact_dedup_legacy_paths_expose_the_canonical_contract() -> None:
    canonical = importlib.import_module(CANONICAL_MODULE)

    for legacy_name in LEGACY_MODULES:
        legacy = importlib.import_module(legacy_name)
        assert legacy is canonical
        assert legacy.ExactDedupReceipt is canonical.ExactDedupReceipt
        assert legacy.find_exact_duplicate_scope is canonical.find_exact_duplicate_scope
        assert legacy.apply_exact_dedup_scope is canonical.apply_exact_dedup_scope


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/exact_dedup.py", "src/memcommit/exact_dedup_application.py"),
)
def test_exact_dedup_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_exact_dedup_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.exact_dedup

assert "memcommit.operations.exact_dedup.application" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_exact_dedup_receipt_global_loads_through_alias() -> None:
    canonical = importlib.import_module(CANONICAL_MODULE)

    restored = pickle.loads(b"cmemcommit.exact_dedup\nExactDedupReceipt\n.")

    assert restored is canonical.ExactDedupReceipt


def test_production_exact_dedup_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/api/_operations/exact_dedup.py",
        "src/memcommit/api/_operations/exact_duplicates.py",
        "src/memcommit/commands/dedup/command.py",
        "src/memcommit/commands/find_exact_duplicates/command.py",
        "src/memcommit/ops.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.exact_dedup" not in source
        assert "memcommit.exact_dedup_application" not in source


def test_exact_dedup_and_semantic_dedun_remain_separate_owners() -> None:
    exact = (
        REPOSITORY_ROOT / "src/memcommit/operations/exact_dedup/application.py"
    ).read_text(encoding="utf-8")
    semantic = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/operations/dedup/application.py",
            "src/memcommit/operations/dedup/runtime.py",
        )
    )

    exact_imports = {
        node.module
        for node in ast.walk(ast.parse(exact))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "memcommit.operations.dedup" not in exact
    assert "memcommit.operations.exact_dedup" not in semantic
    assert not {
        "memcommit.findings",
        "memcommit.semantic_provider",
        "memcommit.operations.dedup.application",
        "memcommit.operations.dedup.runtime",
    } & exact_imports
