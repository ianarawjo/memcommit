"""Ownership and compatibility paths for Translate."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_translate_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.translate

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.application.operations.translate.")
]
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_translate_consumers_use_operation_owners() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/translate/command.py",
        "src/memcommit/study_scenarios/legacy/bundle.py",
        "src/memcommit/application/operations/query/granted_source.py",
        "src/memcommit/application/operations/translate/view.py",
        "src/memcommit/application/operations/translate/view_store.py",
        "src/memcommit/application/operations/translate/application.py",
        "src/memcommit/application/operations/translate/catalog_application.py",
        "src/memcommit/application/operations/translate/materialization.py",
        "src/memcommit/application/ops.py",
        "src/memcommit/application/operations/profile/model.py",
        "src/memcommit/application/retained_history/memory_history_reconstruction/memory_history_event_derivation.py",
        "src/memcommit/persistence/store/operation_state.py",
        "src/memcommit/persistence/store/context_memory.py",
        "src/memcommit/persistence/store/record_restore_checkpoint.py",
    )
    legacy_imports = (
        "from memcommit.translate import",
        "from memcommit.translation_view import",
        "from memcommit.translation_view_store import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_translate_owners_keep_the_existing_dependency_direction() -> None:
    runtime_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/translate/runtime.py"
    ).read_text(encoding="utf-8")
    view_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/translate/view.py"
    ).read_text(encoding="utf-8")
    store_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/translate/view_store.py"
    ).read_text(encoding="utf-8")
    application_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/translate/application.py"
    ).read_text(encoding="utf-8")
    catalog_application_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/translate/catalog_application.py"
    ).read_text(encoding="utf-8")
    materialization_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/translate/materialization.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.application.operations.translate.view" not in runtime_source
    assert (
        "from memcommit.application.operations.translate.runtime import" in view_source
    )
    assert "from memcommit.application.operations.translate.view import" in store_source
    operation_sources = (
        runtime_source
        + view_source
        + store_source
        + application_source
        + catalog_application_source
        + materialization_source
    )
    assert "memcommit.adapters.console.commands" not in operation_sources
    assert "memcommit.adapters.interfaces" not in operation_sources
    assert "import typer" not in operation_sources


def test_translate_command_is_only_an_io_and_presentation_adapter() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/translate/command.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "memcommit.application.operations.translate.application" in imports
    assert "memcommit.application.operations.translate.materialization" in imports
    assert "memcommit.core.context_targeting.loading" not in imports
    assert "memcommit.application.operations.translate.view_store" not in imports
    assert "memcommit.persistence.store" in imports
    assert "import memcommit.application.ops" not in source
    assert "AutoCheckpoint" not in source
    assert "save_translation_catalog(" not in source
    assert "load_translation_catalog_for_context(" not in source
    assert "with_curated(" not in source
    assert "with_review_status(" not in source
    assert "create_context_with_sources(" not in source


def test_translate_request_validation_precedes_store_access() -> None:
    from memcommit.application.operations.translate.application import (
        TranslateRequest,
        prepare_translation,
    )
    from memcommit.application.operations.translate.runtime import TranslateError

    class ClosedStore:
        def __getattr__(self, name):
            raise AssertionError(f"Store accessed before validation: {name}")

    with pytest.raises(TranslateError, match="only one"):
        prepare_translation(
            ClosedStore(),  # type: ignore[arg-type]
            TranslateRequest(edit=True, verify=True),
            current_name="source",
        )
