"""Check whether a new ordinary Context can use a name and storage location."""

from __future__ import annotations

from memcommit.core.context_targeting.naming import (
    RESERVED_CONTEXT_SEGMENTS,
    validate_portable_context_name,
)


class _ContextCreationAvailabilityMixin:
    def context_exists(self, name: str) -> bool:
        if not self._assert_context_storage_root():
            return False
        try:
            context_file = self._context_file(name)
        except (OSError, TypeError, ValueError):
            return False
        return context_file.is_file() and not context_file.is_symlink()

    def _assert_context_storage_available(self, name: str) -> None:
        """Allow a new root Context when only namespace directories predate it."""
        context_dir = self._context_dir(name)
        if not context_dir.exists():
            return
        invalid_entries = [
            entry.name
            for entry in context_dir.iterdir()
            if (
                entry.is_symlink()
                or not entry.is_dir()
                or entry.name.casefold() in RESERVED_CONTEXT_SEGMENTS
            )
        ]
        if invalid_entries:
            raise ValueError(
                f"Cannot create context '{name}': its storage directory already "
                "exists and is not empty; only child namespace directories may "
                "precede a root Context. Invalid entries: "
                + ", ".join(sorted(invalid_entries))
            )

    def assert_context_creatable(self, name: str) -> None:
        """Fail before expensive work when a new Context cannot use this name."""
        validate_portable_context_name(name)
        if self.context_exists(name):
            raise FileExistsError(f"Context '{name}' already exists.")
        self._assert_context_storage_available(name)
