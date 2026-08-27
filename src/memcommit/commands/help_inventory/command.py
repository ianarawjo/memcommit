"""Compatibility alias for the interface-owned Help inventory."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.tui.operations.help import inventory as _inventory

# Preserve module identity for callers that patch Help rendering during a test
# or an embedding session. A copied namespace would make those patches affect
# the facade while the implementation continued using different globals.
sys.modules[__name__] = _inventory
