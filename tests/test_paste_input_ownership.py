"""Ownership contracts for concealed terminal paste capture."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


REPOSITORY_ROOT = Path(__file__).parents[1]
LEGACY_MODULE = "memcommit.adapters.console.terminal.components.paste_input"
OWNER_MODULE = "memcommit.adapters.console.terminal.components.paste_input"


@pytest.mark.parametrize(
    "first_name,second_name",
    ((LEGACY_MODULE, OWNER_MODULE), (OWNER_MODULE, LEGACY_MODULE)),
    ids=("old-first", "new-first"),
)
def test_paste_input_module_identity_is_independent_of_import_order(
    first_name: str,
    second_name: str,
) -> None:
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_MODULE!r})
canonical = importlib.import_module({OWNER_MODULE!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{OWNER_MODULE!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_retired_paste_input_facade_is_absent() -> None:
    path = (
        REPOSITORY_ROOT
        / "src"
        / "memcommit"
        / "adapters"
        / "console"
        / "shared"
        / "paste_input.py"
    )
    assert not path.exists()


def test_legacy_monkeypatch_changes_canonical_capture_globals(monkeypatch) -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(OWNER_MODULE)
    non_terminal = SimpleNamespace(isatty=lambda: False)
    terminal = SimpleNamespace(isatty=lambda: True)
    patched_sys = SimpleNamespace(stdin=non_terminal, stdout=terminal)

    monkeypatch.setattr(legacy, "sys", patched_sys)

    assert canonical.sys is patched_sys
    with pytest.raises(
        ValueError,
        match="--paste requires an interactive terminal",
    ):
        canonical.capture_paste()


def test_add_command_imports_the_interface_owner() -> None:
    source = (
        REPOSITORY_ROOT
        / "src"
        / "memcommit"
        / "adapters"
        / "console"
        / "commands"
        / "add"
        / "command.py"
    ).read_text(encoding="utf-8")

    assert "from memcommit.adapters.console.terminal.components.paste_input import (" in source
    assert "from memcommit.adapters.console.coordination.paste_input import" not in source
