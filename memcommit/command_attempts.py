"""Compatibility alias for the shared infrastructure module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.infrastructure.command_ledger.attempts")
sys.modules[__name__] = _canonical
