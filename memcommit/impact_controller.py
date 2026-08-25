"""Compatibility alias for the interface-owned Impact presentation controller."""

from __future__ import annotations

import sys

from memcommit.interfaces.tui.workbenches import impact as _impact

# Preserve one implementation module so legacy imports and monkeypatches keep
# addressing the same controller globals as canonical interface consumers.
sys.modules[__name__] = _impact
