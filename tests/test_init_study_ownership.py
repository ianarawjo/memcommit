"""Ownership and compatibility contracts for the init-study operation."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import importlib
from pathlib import Path
import subprocess
import sys
import uuid


REPOSITORY_ROOT = Path(__file__).parents[1]


def _top_level_function_names(relative_path: str) -> set[str]:
    path = REPOSITORY_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_init_study_command_imports_the_operation_owned_application() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/commands/init_study/command.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module: {alias.name for alias in node.names}
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert {
        "generate_study_profile_name",
        "init_coffee_study_profile",
        "init_study_profile",
    } <= imports["memcommit.application.operations.init_study.application"]
    assert not {
        "init_coffee_study_profile",
        "init_study_profile",
    }.intersection(imports["memcommit.application.operations.profile.model"])


def test_init_study_composition_and_publication_are_not_profile_implementation() -> None:
    profile_functions = _top_level_function_names(
        "src/memcommit/application/operations/profile/model.py"
    )
    composition_functions = _top_level_function_names(
        "src/memcommit/application/operations/init_study/composition.py"
    )
    publication_functions = _top_level_function_names(
        "src/memcommit/application/operations/init_study/publication.py"
    )

    assert "_snapshot_study_baseline" in composition_functions
    assert "_compose_study_run_pair" in composition_functions
    assert "_publish_study_run_pair" in publication_functions
    assert not {
        "_snapshot_study_baseline",
        "_compose_study_run_pair",
        "_publish_study_run_pair",
    }.intersection(profile_functions)


def test_legacy_profile_imports_delegate_to_the_operation_owned_result() -> None:
    legacy = importlib.import_module("memcommit.profiles")
    result_model = importlib.import_module("memcommit.application.operations.init_study.model")
    application = importlib.import_module(
        "memcommit.application.operations.init_study.application"
    )
    created = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    generated_uid = uuid.UUID("12345678-0000-4000-8000-000000000000")

    assert legacy.StudyInitializationResult is result_model.StudyInitializationResult
    assert legacy.generate_study_profile_name(
        created=created,
        generated_uid=generated_uid,
    ) == application.generate_study_profile_name(
        created=created,
        generated_uid=generated_uid,
    )


def test_init_study_package_import_is_lazy() -> None:
    program = (
        "import sys\n"
        "import memcommit.application.operations.init_study\n"
        "assert 'memcommit.application.operations.init_study.application' not in sys.modules\n"
        "assert 'memcommit.application.operations.init_study.composition' not in sys.modules\n"
        "assert 'memcommit.application.operations.init_study.publication' not in sys.modules\n"
    )

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
