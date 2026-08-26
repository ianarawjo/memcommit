"""Compatibility alias for the interface-owned flat-selection dialog."""

from __future__ import annotations

import sys

from memcommit.interfaces.tui.components import (
    flat_selection_dialog as _flat_selection_dialog,
)

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _flat_selection_dialog
