"""Compatibility alias for the operation-owned Pwd runtime adapter."""

from __future__ import annotations

import sys

from memcommit.operations.pwd import runtime as _runtime

# A true module alias preserves patches to runtime globals through either path.
sys.modules[__name__] = _runtime
