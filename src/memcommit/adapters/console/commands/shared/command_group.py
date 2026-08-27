"""Compatibility alias for interface-owned command-group routing."""

from __future__ import annotations

import sys

from memcommit.adapters.interfaces.cli import command_group as _command_group

# Preserve one implementation module so old-path monkeypatches keep changing
# the routing globals observed by canonical interface imports.
sys.modules[__name__] = _command_group
