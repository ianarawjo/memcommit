"""Ownership and compatibility paths for Translate."""

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
    ("memcommit.translate", "memcommit.operations.translate.runtime"),
    ("memcommit.translation_view", "memcommit.operations.translate.view"),
    (
        "memcommit.translation_view_store",
        "memcommit.operations.translate.view_store",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_translate_module_identity_is_independent_of_import_order(
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
        "memcommit/translate.py",
        "memcommit/translation_view.py",
        "memcommit/translation_view_store.py",
    ),
)
def test_translate_legacy_facades_define_no_behavior(relative_path: str) -> None:
    path = REPOSITORY_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_translate_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.translate

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.operations.translate.")
]
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_translate_globals_load_through_aliases() -> None:
    runtime = importlib.import_module("memcommit.operations.translate.runtime")
    view = importlib.import_module("memcommit.operations.translate.view")
    view_store = importlib.import_module(
        "memcommit.operations.translate.view_store"
    )

    assert (
        pickle.loads(b"cmemcommit.translate\nTranslationPlan\n.")
        is runtime.TranslationPlan
    )
    assert (
        pickle.loads(b"cmemcommit.translation_view\nTranslationCatalog\n.")
        is view.TranslationCatalog
    )
    assert (
        pickle.loads(
            b"cmemcommit.translation_view_store\n"
            b"ConcurrentTranslationViewUpdateError\n."
        )
        is view_store.ConcurrentTranslationViewUpdateError
    )


def test_production_translate_consumers_use_operation_owners() -> None:
    relative_paths = (
        "memcommit/commands/translate.py",
        "memcommit/eval/study_bundle.py",
        "memcommit/operations/query/granted_source.py",
        "memcommit/operations/translate/view.py",
        "memcommit/operations/translate/view_store.py",
        "memcommit/operations/translate/application.py",
        "memcommit/operations/translate/catalog_application.py",
        "memcommit/operations/translate/materialization.py",
        "memcommit/ops.py",
        "memcommit/profiles.py",
        "memcommit/provenance.py",
        "memcommit/store.py",
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
        REPOSITORY_ROOT / "memcommit/operations/translate/runtime.py"
    ).read_text(encoding="utf-8")
    view_source = (
        REPOSITORY_ROOT / "memcommit/operations/translate/view.py"
    ).read_text(encoding="utf-8")
    store_source = (
        REPOSITORY_ROOT / "memcommit/operations/translate/view_store.py"
    ).read_text(encoding="utf-8")
    application_source = (
        REPOSITORY_ROOT / "memcommit/operations/translate/application.py"
    ).read_text(encoding="utf-8")
    catalog_application_source = (
        REPOSITORY_ROOT
        / "memcommit/operations/translate/catalog_application.py"
    ).read_text(encoding="utf-8")
    materialization_source = (
        REPOSITORY_ROOT
        / "memcommit/operations/translate/materialization.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.operations.translate.view" not in runtime_source
    assert "from memcommit.operations.translate.runtime import" in view_source
    assert "from memcommit.operations.translate.view import" in store_source
    operation_sources = (
        runtime_source
        + view_source
        + store_source
        + application_source
        + catalog_application_source
        + materialization_source
    )
    assert "memcommit.commands" not in operation_sources
    assert "memcommit.interfaces" not in operation_sources
    assert "import typer" not in operation_sources


def test_translate_command_is_only_an_io_and_presentation_adapter() -> None:
    path = REPOSITORY_ROOT / "memcommit/commands/translate.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "memcommit.operations.translate.application" in imports
    assert "memcommit.operations.translate.materialization" in imports
    assert "memcommit.context_targeting.loading" not in imports
    assert "memcommit.operations.translate.view_store" not in imports
    assert "memcommit.store" in imports
    assert "import memcommit.ops" not in source
    assert "AutoCheckpoint" not in source
    assert "save_translation_catalog(" not in source
    assert "load_translation_catalog_for_context(" not in source
    assert "with_curated(" not in source
    assert "with_review_status(" not in source
    assert "create_context_with_sources(" not in source


def test_translate_request_validation_precedes_store_access() -> None:
    from memcommit.operations.translate.application import (
        TranslateRequest,
        prepare_translation,
    )
    from memcommit.operations.translate.runtime import TranslateError

    class ClosedStore:
        def __getattr__(self, name):
            raise AssertionError(f"Store accessed before validation: {name}")

    with pytest.raises(TranslateError, match="only one"):
        prepare_translation(
            ClosedStore(),  # type: ignore[arg-type]
            TranslateRequest(edit=True, verify=True),
            current_name="source",
        )
