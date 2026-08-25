"""Compatibility alias for the operation-owned Switch application."""

from __future__ import annotations

import sys

from memcommit.operations.switch import application as _application

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the operation-owned path.
sys.modules[__name__] = _application
