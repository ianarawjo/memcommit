"""Lazy public surfaces for command entry packages."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _load_entrypoint_attribute(
    package_name: str,
    public_names: list[str],
    attribute: str,
) -> Any:
    """Load one declared CLI object without eagerly loading package support."""

    if attribute not in public_names:
        raise AttributeError(f"module {package_name!r} has no attribute {attribute!r}")
    package = import_module(package_name)
    value = getattr(import_module(f"{package_name}.command"), attribute)
    setattr(package, attribute, value)
    return value
