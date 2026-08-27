"""Ownership and compatibility paths for provider-free Literal Find."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_find_operation_package_import_keeps_literal_slice_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.find

assert "memcommit.application.operations.find.literal_application" not in sys.modules
assert "memcommit.application.operations.find.literal_runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_literal_find_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/find.py",
        "src/memcommit/adapters/console/commands/literal_find/command.py",
        "src/memcommit/adapters/interfaces/literal_find.py",
        "src/memcommit/adapters/interfaces/cli/find.py",
        "src/memcommit/adapters/interfaces/tui/operations/find/compact.py",
        "src/memcommit/adapters/interfaces/tui/operations/find/model.py",
        "src/memcommit/adapters/interfaces/tui/operations/find/screen.py",
        "src/memcommit/application/operations/find/literal_runtime.py",
        "src/memcommit/application/operations/replace/application.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.literal_find_application import" not in source
        assert "from memcommit.literal_find_runtime import" not in source


def test_literal_find_does_not_absorb_semantic_search_or_interfaces() -> None:
    application_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/find/literal_application.py"
    ).read_text(encoding="utf-8")
    runtime_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/find/literal_runtime.py"
    ).read_text(encoding="utf-8")
    combined = application_source + runtime_source

    assert "memcommit.application.operations.search.application" not in combined
    assert "memcommit.application.operations.search.runtime" not in combined
    assert "memcommit.adapters.console.commands" not in combined
    assert "memcommit.adapters.interfaces" not in combined
    assert "provider.complete" not in combined


def test_selected_public_find_loads_canonical_modules_without_aliases(
    tmp_path: Path,
) -> None:
    program = f"""
import sys
from pathlib import Path
from memcommit.adapters.python_api import FindContextError, MemCommitClient

client = MemCommitClient(root=Path({str(tmp_path / 'store')!r}), create=True)
try:
    client.find('needle')
except FindContextError:
    pass
else:
    raise AssertionError('Find without a current Context unexpectedly succeeded')

assert 'memcommit.adapters.python_api._operations.find' in sys.modules
assert 'memcommit.application.operations.find.literal_application' in sys.modules
assert 'memcommit.application.operations.find.literal_runtime' in sys.modules
assert 'memcommit.literal_find_application' not in sys.modules
assert 'memcommit.literal_find_runtime' not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
