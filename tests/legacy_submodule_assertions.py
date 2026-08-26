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
        module_path = (
            relative_path.relative_to("src")
            if relative_path.is_relative_to("src")
            else relative_path
        )
        source_path = Path("src") / module_path
        legacy_name = ".".join(module_path.with_suffix("").parts)
    else:
        legacy_name = legacy_path_or_name
        module_path = Path(*legacy_name.split(".")).with_suffix(".py")
        source_path = Path("src") / module_path
    assert module_path.parent == Path("memcommit")
    assert not (REPOSITORY_ROOT / source_path).exists()
    assert legacy_name in LEGACY_SUBMODULE_ALIASES
    if canonical_name is not None:
        assert LEGACY_SUBMODULE_ALIASES[legacy_name] == canonical_name


__all__ = ["assert_legacy_root_submodule_is_centralized"]
