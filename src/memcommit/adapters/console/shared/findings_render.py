"""Compatibility alias for interface-owned quality-finding rendering."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.cli import quality_findings as _quality_findings

# Keep legacy imports and monkeypatches on the exact implementation module.
sys.modules[__name__] = _quality_findings
