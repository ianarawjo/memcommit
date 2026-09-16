"""Persist and revert Context checkpoints."""

from .repository import _CheckpointRepositoryMixin
from .revert import _CheckpointRevertMixin


class CheckpointStoreMixin(
    _CheckpointRepositoryMixin,
    _CheckpointRevertMixin,
):
    """Compatibility composition for checkpoint persistence."""


__all__ = ["CheckpointStoreMixin"]
