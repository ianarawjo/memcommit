"""Compatibility alias for the operation-owned Status application contract."""

from __future__ import annotations

import sys

from memcommit.operations.status import application as _application

# Keep legacy imports and monkeypatches attached to the one implementation
# module while operation ownership moves to its canonical package.
sys.modules[__name__] = _application
