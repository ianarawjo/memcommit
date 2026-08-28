"""Compatibility alias for the interface-owned Memory report picker."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.tui.components import memory_report_picker as _memory_report_picker

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _memory_report_picker
