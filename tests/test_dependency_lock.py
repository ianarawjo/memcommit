"""Catch direct runtime dependencies omitted from the uv lock."""

from __future__ import annotations

from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10; pytest installs its tomli dependency.
    import tomli as tomllib


_ROOT = Path(__file__).resolve().parents[1]


def _canonical_dependency_name(requirement: str) -> str:
    name = re.split(r"[<>=!~; @\[]", requirement, maxsplit=1)[0].strip()
    return re.sub(r"[-_.]+", "-", name).lower()


def test_uv_lock_includes_every_declared_runtime_dependency():
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((_ROOT / "uv.lock").read_text(encoding="utf-8"))

    declared = {
        _canonical_dependency_name(requirement)
        for requirement in project["project"]["dependencies"]
    }
    locked_project = next(
        package for package in lock["package"] if package["name"] == "memcommit"
    )
    locked = {
        _canonical_dependency_name(dependency["name"])
        for dependency in locked_project["dependencies"]
    }
    locked_metadata = {
        _canonical_dependency_name(requirement["name"])
        for requirement in locked_project["metadata"]["requires-dist"]
    }
    resolved = {
        _canonical_dependency_name(package["name"])
        for package in lock["package"]
    }

    assert declared <= locked
    assert declared <= locked_metadata
    assert declared <= resolved
