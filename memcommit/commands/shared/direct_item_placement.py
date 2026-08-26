"""Compatibility alias for the interface-owned direct-item placement component."""

from __future__ import annotations

import sys

from memcommit.interfaces.tui.components import (
    direct_item_placement as _direct_item_placement,
)

# Keep old imports attached to the split interface package so callers cannot
# revive the retired command-owned copy by patching through the legacy path.
sys.modules[__name__] = _direct_item_placement
