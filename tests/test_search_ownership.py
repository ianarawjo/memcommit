"""Ownership and compatibility paths for semantic Search."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_search_operation_package_import_is_lazy_and_separate_from_find() -> None:
    program = """
import sys
import memcommit.application.operations.search_explain.retrieve_answer.search

blocked = (
    "memcommit.application.operations.search_explain.retrieve_answer.search.application",
    "memcommit.application.operations.search_explain.retrieve_answer.search.runtime",
    "memcommit.application.operations.search_explain.retrieve_answer.search.save_context",
    "memcommit.application.capabilities.save_context_from_selection.application",
    "memcommit.application.capabilities.save_context_from_selection.runtime",
    "memcommit.application.operations.search_explain.retrieve_answer.find.application",
    "memcommit.application.operations.search_explain.retrieve_answer.find.runtime",
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
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/search/command.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/search/search_workbench.py",
        "src/memcommit/application/operations/search_explain/retrieve_answer/search/runtime.py",
        "src/memcommit/application/operations/search_explain/retrieve_answer/search/save_context.py",
        "src/memcommit/application/capabilities/save_context_from_selection/application.py",
        "src/memcommit/application/capabilities/save_context_from_selection/runtime.py",
    )
    legacy_imports = (
        "from memcommit.find_application import",
        "from memcommit.find_runtime import",
        "from memcommit.search_materialization_application import",
        "from memcommit.search_materialization_runtime import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_search_analysis_and_selection_save_remain_separate_use_cases() -> None:
    application_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/search_explain/retrieve_answer/search/application.py"
    ).read_text(encoding="utf-8")
    search_save_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/search_explain/retrieve_answer/search/save_context.py"
    ).read_text(encoding="utf-8")
    shared_save_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/capabilities/save_context_from_selection/application.py"
    ).read_text(encoding="utf-8")
    package_source = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/search_explain/retrieve_answer/search/application.py",
            "src/memcommit/application/operations/search_explain/retrieve_answer/search/runtime.py",
            "src/memcommit/application/operations/search_explain/retrieve_answer/search/save_context.py",
            "src/memcommit/application/capabilities/save_context_from_selection/application.py",
            "src/memcommit/application/capabilities/save_context_from_selection/runtime.py",
        )
    )

    assert "save_context_from_selection" not in application_source
    assert (
        "memcommit.application.operations.search_explain.retrieve_answer.search.application" in search_save_source
    )
    assert "memcommit.application.operations.search_explain.retrieve_answer.search" not in shared_save_source
    assert "memcommit.adapters.console.commands" not in package_source
    assert "memcommit.adapters.interfaces" not in package_source


def test_selected_public_search_loads_analysis_without_selection_save(
    tmp_path: Path,
) -> None:
    program = f"""
import sys
from pathlib import Path
from memcommit.adapters.python_api import MemCommitClient, SemanticContextError

client = MemCommitClient(root=Path({str(tmp_path / "store")!r}), create=True)
try:
    client.search('needle')
except SemanticContextError:
    pass
else:
    raise AssertionError('Search without a current Context unexpectedly succeeded')

assert 'memcommit.adapters.python_api._operations.search' in sys.modules
assert 'memcommit.application.operations.search_explain.retrieve_answer.search.application' in sys.modules
assert 'memcommit.application.operations.search_explain.retrieve_answer.search.runtime' in sys.modules
assert 'memcommit.application.operations.search_explain.retrieve_answer.search.save_context' not in sys.modules
assert 'memcommit.application.capabilities.save_context_from_selection.application' not in sys.modules
assert 'memcommit.application.capabilities.save_context_from_selection.runtime' not in sys.modules
assert 'memcommit.find_application' not in sys.modules
assert 'memcommit.find_runtime' not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
