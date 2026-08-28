from __future__ import annotations

import importlib
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DIALOG_MODULES = (
    (
        "memcommit.adapters.console.coordination.context_reach_dialog",
        "memcommit.adapters.console.terminal.components.context_reach_dialog",
    ),
    (
        "memcommit.adapters.console.coordination.flat_selection_dialog",
        "memcommit.adapters.console.terminal.components.flat_selection_dialog",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", DIALOG_MODULES)
def test_dialog_has_one_canonical_component_and_no_legacy_import(
    legacy_name: str,
    canonical_name: str,
) -> None:
    assert importlib.import_module(canonical_name).__name__ == canonical_name
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(legacy_name)
    source_path = (
        REPOSITORY_ROOT.joinpath("src", *legacy_name.split(".")).with_suffix(
            ".py"
        )
    )
    assert not source_path.exists()
