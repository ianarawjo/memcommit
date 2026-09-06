"""Ownership and compatibility contracts for the init-study operation."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]


def _top_level_function_names(relative_path: str) -> set[str]:
    path = REPOSITORY_ROOT / relative_path
    paths = tuple(sorted(path.glob("*.py"))) if path.is_dir() else (path,)
    return {
        node.name
        for source_path in paths
        for node in ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        ).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_init_study_command_imports_the_operation_owned_application() -> None:
    path = (
        REPOSITORY_ROOT
        / "src/memcommit/adapters/console/commands/init_study/command.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module: {alias.name for alias in node.names}
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert {
        "generate_study_profile_name",
        "init_coffee_study_profile",
        "init_legacy_study_profile",
    } <= imports["memcommit.application.operations.init_study.application"]
    assert not {
        "init_coffee_study_profile",
        "init_legacy_study_profile",
    }.intersection(imports["memcommit.application.operations.profile.model"])


def test_init_study_profile_construction_has_one_canonical_owner() -> None:
    study_lifecycle_functions = _top_level_function_names(
        "src/memcommit/application/operations/profile/study"
    )
    composition_functions = _top_level_function_names(
        "src/memcommit/application/operations/init_study/profile/composition.py"
    )
    publication_functions = _top_level_function_names(
        "src/memcommit/application/operations/init_study/profile/publication.py"
    )
    package_functions = _top_level_function_names(
        "src/memcommit/application/operations/init_study/profile/package.py"
    )

    assert "_snapshot_legacy_scenario" in composition_functions
    assert "_compose_study_run_pair" in composition_functions
    assert "_publish_study_run_pair" in publication_functions
    assert "_study_packages" in package_functions
    assert not {
        "_snapshot_legacy_scenario",
        "_compose_study_run_pair",
        "_publish_study_run_pair",
        "_study_packages",
    }.intersection(study_lifecycle_functions)
    assert not _top_level_function_names(
        "src/memcommit/application/operations/init_study/composition.py"
    )
    assert not _top_level_function_names(
        "src/memcommit/application/operations/init_study/publication.py"
    )


def test_old_init_study_construction_imports_are_compatibility_aliases() -> None:
    program = (
        "from memcommit.application.operations.init_study.profile.composition "
        "import _compose_study_run_pair as canonical_composition\n"
        "from memcommit.application.operations.init_study.composition "
        "import _compose_study_run_pair as old_composition\n"
        "from memcommit.application.operations.init_study.profile.publication "
        "import _publish_study_run_pair as canonical_publication\n"
        "from memcommit.application.operations.init_study.publication "
        "import _publish_study_run_pair as old_publication\n"
        "from memcommit.application.operations.init_study.profile.package "
        "import _study_packages as canonical_packages\n"
        "from memcommit.application.operations.profile.model "
        "import _study_packages as old_aggregate_packages\n"
        "assert old_composition is canonical_composition\n"
        "assert old_publication is canonical_publication\n"
        "assert old_aggregate_packages is canonical_packages\n"
    )

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_init_study_package_import_is_lazy() -> None:
    program = (
        "import sys\n"
        "import memcommit.application.operations.init_study\n"
        "assert 'memcommit.application.operations.init_study.application' not in sys.modules\n"
        "assert 'memcommit.application.operations.init_study.composition' not in sys.modules\n"
        "assert 'memcommit.application.operations.init_study.publication' not in sys.modules\n"
        "assert 'memcommit.application.operations.init_study.profile.model' not in sys.modules\n"
        "assert 'memcommit.application.operations.init_study.profile.package' not in sys.modules\n"
        "assert 'memcommit.application.operations.init_study.profile.composition' not in sys.modules\n"
        "assert 'memcommit.application.operations.init_study.profile.publication' not in sys.modules\n"
    )

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
