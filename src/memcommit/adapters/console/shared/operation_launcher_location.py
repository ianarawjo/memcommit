"""Compatibility alias for interface-owned launcher location discovery."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.tui.components.operation_launcher import location as _location

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the profile and Store globals used by canonical interface-path callers.
sys.modules[__name__] = _location
