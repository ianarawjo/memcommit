"""Stable access to authored evaluation and prompt-reference resources."""

from __future__ import annotations

from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def fixture_path(name: str) -> Path:
    """Return a filesystem path for Eval campaign code in this distribution."""

    if not isinstance(name, str) or not name or Path(name).name != name:
        raise ValueError("Evaluation fixture name must be one plain filename.")
    return FIXTURE_ROOT / name


def fixture_resource(name: str) -> Traversable:
    """Return one packaged fixture for production prompt/rules consumers."""

    if not isinstance(name, str) or not name or Path(name).name != name:
        raise ValueError("Evaluation fixture name must be one plain filename.")
    return resources.files(__package__).joinpath("fixtures", name)


__all__ = ["FIXTURE_ROOT", "fixture_path", "fixture_resource"]

