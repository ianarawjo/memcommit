"""Compatibility alias for the operation-owned Dedup module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.reviewing.direct_item_duplicates")
sys.modules[__name__] = _canonical
