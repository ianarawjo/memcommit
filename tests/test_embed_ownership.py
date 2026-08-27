"""Ownership and compatibility paths for live Context and Memory Embed."""

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
        "memcommit.embed_application",
        "memcommit.application.operations.embed.application",
    ),
    (
        "memcommit.embed_runtime",
        "memcommit.application.operations.embed.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_embed_module_identity_is_independent_of_import_order(
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


def test_embed_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.embed_application")
    canonical_application = importlib.import_module(
        "memcommit.application.operations.embed.application"
    )
    legacy_runtime = importlib.import_module("memcommit.embed_runtime")
    canonical_runtime = importlib.import_module("memcommit.application.operations.embed.runtime")

    assert legacy_application is canonical_application
    assert legacy_application.EmbedRequest is canonical_application.EmbedRequest
    assert (
        legacy_application.MemoryEmbedRequest
        is canonical_application.MemoryEmbedRequest
    )
    assert legacy_application.run_embed is canonical_application.run_embed
    assert legacy_application.run_memory_embed is canonical_application.run_memory_embed
    assert legacy_runtime is canonical_runtime
    assert legacy_runtime.MemoryStoreEmbedPort is canonical_runtime.MemoryStoreEmbedPort
    assert legacy_runtime.execute_embed is canonical_runtime.execute_embed


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/embed_application.py", "src/memcommit/embed_runtime.py"),
)
def test_embed_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_embed_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.embed

assert "memcommit.application.operations.embed.application" not in sys.modules
assert "memcommit.application.operations.embed.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_embed_request_global_loads_through_alias() -> None:
    canonical = importlib.import_module("memcommit.application.operations.embed.application")

    restored = pickle.loads(b"cmemcommit.embed_application\nEmbedRequest\n.")

    assert restored is canonical.EmbedRequest


def test_production_embed_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/embed.py",
        "src/memcommit/interfaces/cli/embed.py",
        "src/memcommit/interfaces/tui/operations/embed/adapter.py",
        "src/memcommit/interfaces/tui/operations/embed/screen.py",
        "src/memcommit/application/operations/embed/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.embed_application import" not in source
        assert "from memcommit.embed_runtime import" not in source


def test_reference_and_embed_remain_separate_operation_packages() -> None:
    for relative_path in (
        "src/memcommit/application/operations/reference/application.py",
        "src/memcommit/application/operations/reference/runtime.py",
        "src/memcommit/application/operations/embed/application.py",
        "src/memcommit/application/operations/embed/runtime.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        if "/reference/" in relative_path:
            assert "memcommit.application.operations.embed" not in source
        else:
            assert "memcommit.application.operations.reference" not in source
