"""Compatibility alias for the operation-owned Switch runtime."""

from __future__ import annotations

import sys

from memcommit.operations.switch import runtime as _runtime

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the operation-owned path.
sys.modules[__name__] = _runtime
