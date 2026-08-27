"""Compatibility alias for the interface-owned search-result presenter."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.cli import search_results as _search_results

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _search_results
