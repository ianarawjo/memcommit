"""Compatibility alias for the operation-owned Merge runtime adapter."""

from __future__ import annotations

import sys

from memcommit.operations.merge import runtime as _runtime

# Runtime patches through either path must affect the same Store adapter.
sys.modules[__name__] = _runtime
