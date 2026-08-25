"""Compatibility alias for the operation-owned Replace runtime adapter."""

from __future__ import annotations

import sys

from memcommit.operations.replace import runtime as _runtime

# A true module alias preserves patches to runtime globals through either path.
sys.modules[__name__] = _runtime
