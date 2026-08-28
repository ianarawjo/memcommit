"""Restore globally ordered Context commands and companion sessions."""

from .archive import _CommandArchiveMixin
from .engine import _CommandRestorationEngineMixin
from .handlers.atomize import _AtomizeRestorationMixin
from .handlers.branch import _BranchRestorationMixin
from .handlers.companion_sessions import _CompanionSessionRestorationMixin
from .handlers.merge import _MergeRestorationMixin
from .handlers.sever import _SeverRestorationMixin


class CommandRestorationStoreMixin(
    _CommandArchiveMixin,
    _CommandRestorationEngineMixin,
    _BranchRestorationMixin,
    _MergeRestorationMixin,
    _AtomizeRestorationMixin,
    _SeverRestorationMixin,
    _CompanionSessionRestorationMixin,
):
    """Compatibility composition for command-level Undo and Redo."""


__all__ = ["CommandRestorationStoreMixin"]
