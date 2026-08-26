"""Assertions for historical root modules consolidated out of the file tree."""

from __future__ import annotations

from pathlib import Path

from memcommit.compatibility._legacy_alias_map import LEGACY_SUBMODULE_ALIASES


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def assert_legacy_root_submodule_is_centralized(
    legacy_path_or_name: str,
    canonical_name: str | None = None,
) -> None:
    """Require an exact registry entry and no physical root facade."""

    if legacy_path_or_name.endswith(".py"):
        relative_path = Path(legacy_path_or_name)
        legacy_name = ".".join(relative_path.with_suffix("").parts)
    else:
        legacy_name = legacy_path_or_name
        relative_path = Path(*legacy_name.split(".")).with_suffix(".py")
    assert relative_path.parent == Path("memcommit")
    assert not (REPOSITORY_ROOT / relative_path).exists()
    assert legacy_name in LEGACY_SUBMODULE_ALIASES
    if canonical_name is not None:
        assert LEGACY_SUBMODULE_ALIASES[legacy_name] == canonical_name


__all__ = ["assert_legacy_root_submodule_is_centralized"]
