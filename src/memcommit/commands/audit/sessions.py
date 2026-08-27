"""Compatibility alias for the interface-owned Audit session catalog."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.tui.operations.audit import catalog as _catalog

# Keep legacy imports and monkeypatches on the exact implementation module.
sys.modules[__name__] = _catalog
