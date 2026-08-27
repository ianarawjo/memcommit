"""Ownership and compatibility paths for exact and semantic Help."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_help_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.help

assert "memcommit.application.operations.help.application" not in sys.modules
assert "memcommit.application.operations.help.lookup_application" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_help_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/help.py",
        "src/memcommit/adapters/interfaces/agent/help.py",
        "src/memcommit/adapters/interfaces/tui/operations/help/inventory.py",
        "src/memcommit/application/operations/help/lookup_application.py",
    )
    legacy_imports = (
        "from memcommit.help_application import",
        "from memcommit.help_lookup_application import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_help_owner_preserves_catalog_and_injected_provider_boundaries() -> None:
    application_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/help/application.py"
    ).read_text(encoding="utf-8")
    lookup_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/help/lookup_application.py"
    ).read_text(encoding="utf-8")
    combined = application_source + lookup_source

    assert "memcommit.commands" not in combined
    assert "memcommit.adapters.interfaces" not in combined
    assert "memcommit.store" not in combined
    assert "memcommit.infrastructure" not in combined
    assert "provider.complete" not in application_source
    assert "provider.complete" in lookup_source
    assert "connect_help_provider" not in lookup_source
    assert "memcommit.application.operations.help.application" in lookup_source


def test_selected_public_help_loads_only_exact_catalog_application(
    tmp_path: Path,
) -> None:
    program = f"""
import sys
from pathlib import Path
from memcommit.adapters.python_api import MemCommitClient

root = Path({str(tmp_path / 'missing-store')!r})
result = MemCommitClient(root=root).describe_operation('compare')
assert result.name == 'compare'
assert not root.exists()
assert 'memcommit.adapters.python_api._operations.help' in sys.modules
assert 'memcommit.application.operations.help.application' in sys.modules
assert 'memcommit.application.operations.help.lookup_application' not in sys.modules
assert 'memcommit.help_application' not in sys.modules
assert 'memcommit.help_lookup_application' not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
