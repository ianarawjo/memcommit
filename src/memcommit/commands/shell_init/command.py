"""Compatibility alias for the interface-owned shell integration command."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.cli import shell_init as _shell_init

# Preserve one implementation module so legacy-path monkeypatches keep changing
# the globals used by callers imported through the interface-owned path.
sys.modules[__name__] = _shell_init
