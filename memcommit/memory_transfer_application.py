"""Compatibility alias for the operation-owned Memory Transfer contract."""

from __future__ import annotations

import sys

from memcommit.operations.memory_transfer import application as _application

# Copy and Move retain their historical import surface while one canonical
# module owns request, plan, authority, and receipt globals.
sys.modules[__name__] = _application
