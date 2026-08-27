"""Ownership and compatibility paths for semantic Search."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_search_operation_package_import_is_lazy_and_separate_from_literal_find() -> None:
    program = """
import sys
import memcommit.application.operations.search

blocked = (
    "memcommit.application.operations.search.application",
    "memcommit.application.operations.search.runtime",
    "memcommit.application.operations.search.materialization_application",
    "memcommit.application.operations.search.materialization_runtime",
    "memcommit.application.operations.find.literal_application",
    "memcommit.application.operations.find.literal_runtime",
)
assert not [name for name in blocked if name in sys.modules]
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_search_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/search.py",
        "src/memcommit/commands/find/command.py",
        "src/memcommit/commands/find/materialization.py",
        "src/memcommit/commands/find/search_workbench.py",
        "src/memcommit/application/operations/search/runtime.py",
        "src/memcommit/application/operations/search/materialization_application.py",
        "src/memcommit/application/operations/search/materialization_runtime.py",
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
        REPOSITORY_ROOT / "src/memcommit/application/operations/search/application.py"
    ).read_text(encoding="utf-8")
    materialization_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/search/materialization_application.py"
    ).read_text(encoding="utf-8")
    package_source = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/search/application.py",
            "src/memcommit/application/operations/search/runtime.py",
            "src/memcommit/application/operations/search/materialization_application.py",
            "src/memcommit/application/operations/search/materialization_runtime.py",
        )
    )

    assert "materialization" not in application_source.lower()
    assert "memcommit.application.operations.search.application" in materialization_source
    assert "memcommit.commands" not in package_source
    assert "memcommit.adapters.interfaces" not in package_source


def test_selected_public_search_loads_analysis_without_materialization(
    tmp_path: Path,
) -> None:
    program = f"""
import sys
from pathlib import Path
from memcommit.adapters.python_api import MemCommitClient, SemanticContextError

client = MemCommitClient(root=Path({str(tmp_path / 'store')!r}), create=True)
try:
    client.search('needle')
except SemanticContextError:
    pass
else:
    raise AssertionError('Search without a current Context unexpectedly succeeded')

assert 'memcommit.adapters.python_api._operations.search' in sys.modules
assert 'memcommit.application.operations.search.application' in sys.modules
assert 'memcommit.application.operations.search.runtime' in sys.modules
assert 'memcommit.application.operations.search.materialization_application' not in sys.modules
assert 'memcommit.application.operations.search.materialization_runtime' not in sys.modules
assert 'memcommit.find_application' not in sys.modules
assert 'memcommit.find_runtime' not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
