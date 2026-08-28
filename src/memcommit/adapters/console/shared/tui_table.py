"""Compatibility alias for the interface-owned terminal table component."""

from __future__ import annotations

import sys

from memcommit.adapters.console.tui.components import table as _table

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _table
