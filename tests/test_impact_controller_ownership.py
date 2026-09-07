"""Impact owns concrete projections; the terminal host only consumes their shape."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from memcommit.adapters.console.commands.impact.projection import (
    ImpactController,
    ImpactEntry,
    ImpactView,
)


ROOT = Path(__file__).parents[1]


def test_concrete_impact_projection_belongs_to_the_impact_command():
    for value in (ImpactController, ImpactEntry, ImpactView):
        assert value.__module__ == "memcommit.adapters.console.commands.impact.projection"
    assert not (ROOT / "src/memcommit/adapters/console/terminal/components/impact.py").exists()


def test_session_host_does_not_load_impact_or_other_commands():
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
import memcommit.adapters.console.terminal.components.resolution.session_shell
assert not any(name.startswith('memcommit.adapters.console.commands') for name in sys.modules)
"""],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
