"""Ownership and compatibility paths for the complete Sever operation."""

from __future__ import annotations

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
        "memcommit.sever",
        "memcommit.application.operations.sever.model",
    ),
    (
        "memcommit.sever_provider",
        "memcommit.application.operations.sever.provider",
    ),
    (
        "memcommit.sever_store",
        "memcommit.application.operations.sever.session_store",
    ),
    (
        "memcommit.sever_resolution_adapter",
        "memcommit.application.operations.sever.resolution_adapter",
    ),
    (
        "memcommit.sever_application",
        "memcommit.application.operations.sever.application",
    ),
    (
        "memcommit.sever_runtime",
        "memcommit.application.operations.sever.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_sever_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name) if legacy_first else (canonical_name, legacy_name)
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


def test_sever_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_model = importlib.import_module("memcommit.sever")
    canonical_model = importlib.import_module(
        "memcommit.application.operations.sever.model"
    )
    legacy_provider = importlib.import_module("memcommit.sever_provider")
    canonical_provider = importlib.import_module(
        "memcommit.application.operations.sever.provider"
    )
    legacy_store = importlib.import_module("memcommit.sever_store")
    canonical_store = importlib.import_module(
        "memcommit.application.operations.sever.session_store"
    )
    legacy_resolution = importlib.import_module("memcommit.sever_resolution_adapter")
    canonical_resolution = importlib.import_module(
        "memcommit.application.operations.sever.resolution_adapter"
    )
    legacy_application = importlib.import_module("memcommit.sever_application")
    canonical_application = importlib.import_module(
        "memcommit.application.operations.sever.application"
    )
    legacy_runtime = importlib.import_module("memcommit.sever_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.application.operations.sever.runtime"
    )

    assert legacy_model is canonical_model
    assert legacy_model.SeverSession is canonical_model.SeverSession
    assert legacy_provider is canonical_provider
    assert legacy_provider.analyze_sever is canonical_provider.analyze_sever
    assert legacy_store is canonical_store
    assert legacy_store.SeverSessionStore is canonical_store.SeverSessionStore
    assert legacy_resolution is canonical_resolution
    assert (
        legacy_resolution.SeverResolutionWorkbenchAdapter
        is canonical_resolution.SeverResolutionWorkbenchAdapter
    )
    assert legacy_application is canonical_application
    assert (
        legacy_application.SeverAnalysisRequest
        is canonical_application.SeverAnalysisRequest
    )
    assert (
        legacy_application.SeverSessionApplicationFlowPort
        is canonical_application.SeverSessionApplicationFlowPort
    )
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreSeverInputPort
        is canonical_runtime.MemoryStoreSeverInputPort
    )
    assert (
        legacy_runtime.execute_sever_session_apply
        is canonical_runtime.execute_sever_session_apply
    )


@pytest.mark.parametrize(
    "relative_path",
    (
        "src/memcommit/sever.py",
        "src/memcommit/sever_provider.py",
        "src/memcommit/sever_store.py",
        "src/memcommit/sever_resolution_adapter.py",
        "src/memcommit/sever_application.py",
        "src/memcommit/sever_runtime.py",
    ),
)
def test_sever_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_sever_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.sever

assert "memcommit.application.operations.sever.application" not in sys.modules
assert "memcommit.application.operations.sever.runtime" not in sys.modules
assert "memcommit.application.operations.sever.model" not in sys.modules
assert "memcommit.application.operations.sever.provider" not in sys.modules
assert "memcommit.application.operations.sever.session_store" not in sys.modules
assert "memcommit.application.operations.sever.resolution_adapter" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_sever_request_global_loads_through_alias() -> None:
    canonical = importlib.import_module(
        "memcommit.application.operations.sever.application"
    )

    restored = pickle.loads(b"cmemcommit.sever_application\nSeverAnalysisRequest\n.")

    assert restored is canonical.SeverAnalysisRequest


def test_pre_relocation_sever_session_global_loads_through_alias() -> None:
    canonical = importlib.import_module("memcommit.application.operations.sever.model")

    restored = pickle.loads(b"cmemcommit.sever\nSeverSession\n.")

    assert restored is canonical.SeverSession


def test_production_sever_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/commands/impact/command.py",
        "src/memcommit/commands/impact/catalog.py",
        "src/memcommit/commands/impact/sessions.py",
        "src/memcommit/commands/review/command.py",
        "src/memcommit/commands/review/sessions.py",
        "src/memcommit/commands/sever/command.py",
        "src/memcommit/commands/sever/sessions.py",
        "src/memcommit/application/operations/sever/application.py",
        "src/memcommit/application/operations/sever/provider.py",
        "src/memcommit/application/operations/sever/resolution_adapter.py",
        "src/memcommit/study_scenarios/legacy/prewarm/sever.py",
        "src/memcommit/application/operations/sever/session_store.py",
        "src/memcommit/application/operations/sever/runtime.py",
        "src/memcommit/application/operations/review/report_adapters.py",
        "src/memcommit/persistence/store/operation_state.py",
        "src/memcommit/persistence/store/context_memory.py",
        "src/memcommit/persistence/store/record_restore_checkpoint.py",
    )
    legacy_imports = (
        "from memcommit.sever import",
        "from memcommit.sever_provider import",
        "from memcommit.sever_resolution_adapter import",
        "from memcommit.sever_store import",
        "from memcommit.sever_application import",
        "from memcommit.sever_runtime import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]
