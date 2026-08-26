"""Terminal selection adapter for the Switch operation."""

from memcommit.interfaces.tui.operations.switch.model import SwitchTuiSetup
from memcommit.interfaces.tui.operations.switch.screen import run_switch_tui

__all__ = ["SwitchTuiSetup", "run_switch_tui"]
