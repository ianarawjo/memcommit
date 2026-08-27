"""Compatibility alias for the interface-owned paste-input component."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.tui.components import paste_input as _paste_input

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _paste_input
