"""Compatibility alias for the interface-owned Context reach dialog."""

from __future__ import annotations

import sys

from memcommit.interfaces.tui.components import (
    context_reach_dialog as _context_reach_dialog,
)

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _context_reach_dialog
