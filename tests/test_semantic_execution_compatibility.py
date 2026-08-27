"""Physical ownership coverage for the application semantic executor."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "memcommit"


def test_semantic_execution_has_one_physical_application_owner() -> None:
    canonical = PACKAGE_ROOT / "application" / "semantic_execution"
    assert canonical.is_dir()
    legacy = PACKAGE_ROOT / "semantic_execution"
    assert not (legacy / "__init__.py").exists()
    assert tuple(legacy.glob("*.py")) == ()

    assert not (PACKAGE_ROOT / "compatibility").exists()
