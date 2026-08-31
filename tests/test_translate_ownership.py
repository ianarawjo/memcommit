"""Ownership boundaries for Translate."""

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
import memcommit.application.operations.translation.translate

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.application.operations.translation.translate.")
]
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_translate_consumers_use_operation_owners() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/translation/translate/command.py",
        "src/memcommit/study_scenarios/legacy/bundle.py",
        "src/memcommit/application/operations/search_explain/retrieve_answer/query/granted_source.py",
        "src/memcommit/core/memory_translation",
        "src/memcommit/persistence/store/translation_catalog",
        "src/memcommit/application/operations/translation/translate/application.py",
        "src/memcommit/application/operations/translation/translate/provider_catalog.py",
        "src/memcommit/application/operations/translation/translate/curate_translations.py",
        "src/memcommit/application/operations/translation/translate/exchange_translations.py",
        "src/memcommit/application/operations/translation/translate/add_translations_to_current_context.py",
        "src/memcommit/application/operations/translation/translate/create_translated_context.py",
        "src/memcommit/application/capabilities/ops.py",
        "src/memcommit/application/operations/profiles/profile/model",
        "src/memcommit/application/capabilities/history/reconstruction/memory_effect_derivation.py",
        "src/memcommit/persistence/operations",
        "src/memcommit/persistence/store/context_memory",
        "src/memcommit/persistence/store/record_restore_checkpoint.py",
        "src/memcommit/persistence/store/checkpoint",
        "src/memcommit/persistence/store/command_restoration",
    )
    legacy_imports = (
        "from memcommit.translate import",
        "from memcommit.translation_view import",
        "from memcommit.translation_view_store import",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        paths = tuple(sorted(path.rglob("*.py"))) if path.is_dir() else (path,)
        for source_path in paths:
            source = source_path.read_text(encoding="utf-8")
            assert not [legacy for legacy in legacy_imports if legacy in source]


def test_translate_owners_keep_the_layer_dependency_direction() -> None:
    runtime_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/translation/translate/runtime.py"
    ).read_text(encoding="utf-8")
    catalog_source = (
        REPOSITORY_ROOT / "src/memcommit/core/memory_translation/catalog.py"
    ).read_text(encoding="utf-8")
    repository_source = (
        REPOSITORY_ROOT
        / "src/memcommit/persistence/store/translation_catalog/repository.py"
    ).read_text(encoding="utf-8")
    application_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/translation/translate/application.py"
    ).read_text(encoding="utf-8")
    provider_catalog_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/translation/translate/provider_catalog.py"
    ).read_text(encoding="utf-8")
    context_action_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/translation/translate/create_translated_context.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.application" not in catalog_source
    assert "memcommit.persistence" not in catalog_source
    assert "memcommit.application" not in repository_source
    assert "memcommit.core.memory_translation" in repository_source
    operation_sources = (
        runtime_source
        + catalog_source
        + repository_source
        + application_source
        + provider_catalog_source
        + context_action_source
    )
    assert "memcommit.adapters.console.commands" not in operation_sources
    assert "memcommit.adapters.interfaces" not in operation_sources
    assert "import typer" not in operation_sources


def test_translate_command_is_only_an_io_and_presentation_adapter() -> None:
    path = (
        REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/translation/translate/command.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "memcommit.application.operations.translation.translate.application" in imports
    assert (
        "memcommit.application.operations.translation.translate.create_translated_context"
        in imports
    )
    assert (
        "memcommit.application.operations.translation.translate.add_translations_to_current_context"
        in imports
    )
    assert "memcommit.core.context_targeting.loading" not in imports
    assert "memcommit.persistence.store.translation_catalog" not in imports
    assert "memcommit.persistence.store" in imports
    assert "import memcommit.application.capabilities.ops" not in source
    assert "AutoCheckpoint" not in source
    assert "save_translation_catalog(" not in source
    assert "load_translation_catalog_for_context(" not in source
    assert "with_curated(" not in source
    assert "with_review_status(" not in source
    assert "create_context_with_sources(" not in source


def test_translate_request_validation_precedes_store_access() -> None:
    from memcommit.application.operations.translation.translate.application import (
        TranslateRequest,
        prepare_translation,
    )
    from memcommit.application.operations.translation.translate.runtime import TranslateError

    class ClosedStore:
        def __getattr__(self, name):
            raise AssertionError(f"Store accessed before validation: {name}")

    with pytest.raises(TranslateError, match="only one"):
        prepare_translation(
            ClosedStore(),  # type: ignore[arg-type]
            TranslateRequest(edit=True, verify=True),
            current_name="source",
        )
