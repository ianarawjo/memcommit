"""Ownership compatibility for the interface-owned Impact controller."""

from __future__ import annotations

import importlib


def test_legacy_impact_controller_path_is_the_canonical_interface_module() -> None:
    legacy = importlib.import_module("memcommit.impact_controller")
    canonical = importlib.import_module(
        "memcommit.interfaces.tui.workbenches.impact"
    )

    assert legacy is canonical
    assert legacy.ImpactEntry is canonical.ImpactEntry
    assert legacy.ImpactView is canonical.ImpactView
    assert legacy.ImpactController is canonical.ImpactController
