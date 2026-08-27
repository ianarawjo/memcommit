"""Compatibility alias for the interface-owned exact-name dialog."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.tui.components import (
    exact_name_dialog as _exact_name_dialog,
)

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _exact_name_dialog
