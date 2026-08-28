"""Compatibility alias for the interface-owned checkpoint-location picker."""

from __future__ import annotations

import sys

from memcommit.adapters.console.tui.components import checkpoint_location as _checkpoint_location

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _checkpoint_location
