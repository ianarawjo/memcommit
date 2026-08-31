"""Ownership and compatibility paths for provider-free Find."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_find_operation_package_import_keeps_literal_slice_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.search_explain.retrieve_answer.find

assert "memcommit.application.operations.search_explain.retrieve_answer.find.application" not in sys.modules
assert "memcommit.application.operations.search_explain.retrieve_answer.find.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_find_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/find.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/find/command.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/find/source_row.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/find/presentation.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/find/compact.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/find/workbench/model.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/find/workbench/screen.py",
        "src/memcommit/application/operations/search_explain/retrieve_answer/find/runtime.py",
        "src/memcommit/application/operations/direct_changes/replace/application.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.literal_find_application import" not in source
        assert "from memcommit.literal_find_runtime import" not in source


def test_find_does_not_absorb_semantic_search_or_interfaces() -> None:
    application_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/search_explain/retrieve_answer/find/application.py"
    ).read_text(encoding="utf-8")
    runtime_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/search_explain/retrieve_answer/find/runtime.py"
    ).read_text(encoding="utf-8")
    combined = application_source + runtime_source

    assert "memcommit.application.operations.search_explain.retrieve_answer.search.application" not in combined
    assert "memcommit.application.operations.search_explain.retrieve_answer.search.runtime" not in combined
    assert "memcommit.adapters.console.commands" not in combined
    assert "memcommit.adapters.interfaces" not in combined
    assert "provider.complete" not in combined


def test_find_console_owns_presentation_and_workbench_without_interface_facades() -> (
    None
):
    command_root = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/find"

    assert (command_root / "presentation.py").is_file()
    assert (command_root / "compact.py").is_file()
    assert (command_root / "workbench/model.py").is_file()
    assert (command_root / "workbench/screen.py").is_file()
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/find.py"
    ).exists()
    assert not tuple(
        (
            REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/tui/operations/find"
        ).glob("*.py")
    )


def test_selected_public_find_loads_canonical_modules_without_aliases(
    tmp_path: Path,
) -> None:
    program = f"""
import sys
from pathlib import Path
from memcommit.adapters.python_api import FindContextError, MemCommitClient

client = MemCommitClient(root=Path({str(tmp_path / "store")!r}), create=True)
try:
    client.find('needle')
except FindContextError:
    pass
else:
    raise AssertionError('Find without a current Context unexpectedly succeeded')

assert 'memcommit.adapters.python_api._operations.find' in sys.modules
assert 'memcommit.application.operations.search_explain.retrieve_answer.find.application' in sys.modules
assert 'memcommit.application.operations.search_explain.retrieve_answer.find.runtime' in sys.modules
assert 'memcommit.literal_find_application' not in sys.modules
assert 'memcommit.literal_find_runtime' not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
