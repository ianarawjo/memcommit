"""Compatibility alias for interface-owned line-oriented batch input."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.cli import batch_input as _batch_input

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _batch_input
