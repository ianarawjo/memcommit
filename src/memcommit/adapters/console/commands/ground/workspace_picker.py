"""Compatibility alias for the interface-owned Ground workspace picker."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.tui.operations.ground_workspace import picker as _picker

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _picker
