"""Compatibility alias for the interface-owned Impact route registry."""

from __future__ import annotations

import sys

from memcommit.interfaces.cli import impact_registry as _impact_registry

# Preserve one implementation module so imports and monkeypatches through the
# historical command path observe the interface-owned module's exact globals.
sys.modules[__name__] = _impact_registry
