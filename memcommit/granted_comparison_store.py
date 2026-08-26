"""Compatibility alias for the operation-owned Compare module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.compare.ledger.granted_store")
sys.modules[__name__] = _canonical
