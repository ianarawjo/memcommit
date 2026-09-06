"""Shared Profile operation failure, independent of storage and lifecycle."""


class ProfileError(RuntimeError):
    """A profile operation cannot complete without risking local state."""
