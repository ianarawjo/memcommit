"""History must remain usable without importing an operation's approval UI."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("modules", "blocked"),
    [
        (
            (
                "memcommit.adapters.console.terminal.components.history.picker",
                "memcommit.adapters.console.terminal.components.history.browser",
                "memcommit.adapters.console.terminal.components.history.update_checkpoint",
            ),
            ("memcommit.adapters.console.commands.revert",),
        ),
        (
            (
                "memcommit.adapters.console.terminal.components.history.model",
                "memcommit.adapters.console.terminal.components.history.rendering",
                "memcommit.adapters.console.terminal.components.history.presentation",
                "memcommit.adapters.console.terminal.components.history.checkpoint_diff",
            ),
            (
                "memcommit.adapters.console.commands.revert",
                "memcommit.adapters.console.terminal.components.history.picker",
                "memcommit.adapters.console.terminal.components.history.controls",
            ),
        ),
    ],
)
def test_history_imports_without_its_consumers(modules, blocked):
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, PYTHONPATH=str(root / "src"))
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import importlib
import importlib.abc
import sys

class BlockConsumers(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in {blocked!r}):
            raise ImportError(f'History imported a consuming screen: {{fullname}}')

sys.meta_path.insert(0, BlockConsumers())
for module in {modules!r}:
    importlib.import_module(module)
""",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
