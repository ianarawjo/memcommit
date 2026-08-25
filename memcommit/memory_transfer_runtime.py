"""Compatibility alias for the operation-owned Memory Transfer runtime."""

from __future__ import annotations

import sys

from memcommit.operations.memory_transfer import runtime as _runtime

# Preserve patches and runtime identity through both old and canonical paths.
sys.modules[__name__] = _runtime
