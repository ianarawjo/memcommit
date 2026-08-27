"""Compatibility alias for the interface-owned exact-command review shell."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.tui.components.exact_command_review import shell as _shell

# Preserve one implementation module so patches through the historical command
# path still change the globals used by the canonical interface component.
sys.modules[__name__] = _shell
