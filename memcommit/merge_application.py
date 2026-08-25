"""Compatibility alias for the operation-owned Merge application contract."""

from __future__ import annotations

import sys

from memcommit.operations.merge import application as _application

# Preserve one implementation module for legacy imports, monkeypatches, and
# serialized globals while canonical ownership moves under operations/merge.
sys.modules[__name__] = _application
