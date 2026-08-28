"""Ownership gates for operation-launcher location discovery."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from memcommit.application.operations.profile.config import ProfileConfigError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.adapters.console.shared.operation_launcher_location"
CANONICAL_MODULE = (
    "memcommit.adapters.interfaces.tui.components.operation_launcher.location"
)


def test_legacy_monkeypatch_changes_canonical_location_globals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(CANONICAL_MODULE)
    frozen_root = tmp_path / "frozen-store"

    def unavailable_registry():
        raise ProfileConfigError("unavailable")

    monkeypatch.setattr(legacy.store_module, "STORE_DIR", frozen_root)
    monkeypatch.setattr(legacy, "load_profile_registry", unavailable_registry)

    assert legacy is canonical
    assert canonical.operation_launcher_orientation().rows == (
        ("PROFILE", "(registry unavailable)"),
        ("STORE", str(frozen_root)),
    )
