"""Resolve safe ordinary Context storage paths."""

from __future__ import annotations

from pathlib import Path

from .records import _context_name_parts


class _ContextAddressingMixin:
    def _assert_context_storage_root(self) -> bool:
        """Return whether the ordinary root exists, rejecting unsafe aliases.

        A symlink at ``contexts/`` used to bypass the per-namespace symlink
        checks because every descendant resolved inside the aliased root. All
        ordinary Context paths enter through this guard so reads and writes
        enforce the same storage boundary.
        """
        if self.contexts_dir.is_symlink():
            raise ValueError("Context storage root cannot be a symbolic link.")
        if not self.contexts_dir.exists():
            return False
        if not self.contexts_dir.is_dir():
            raise ValueError("Context storage root is not a directory.")
        return True

    def _context_dir(self, name: str) -> Path:
        self._assert_context_storage_root()
        parts = _context_name_parts(name)
        path = self.contexts_dir.joinpath(*parts)
        candidate = self.contexts_dir
        for part in parts:
            candidate /= part
            if candidate.is_symlink():
                raise ValueError(
                    f"Invalid context name '{name}': symbolic links are not "
                    "allowed in context namespaces."
                )
            if candidate.exists() and not candidate.is_dir():
                raise ValueError(
                    f"Invalid context name '{name}': namespace component "
                    f"'{candidate.name}' is not a directory."
                )
        contexts_root = self.contexts_dir.resolve()
        resolved = path.resolve(strict=False)
        if resolved != contexts_root and contexts_root not in resolved.parents:
            raise ValueError(
                f"Invalid context name '{name}': path escapes the context store."
            )
        return path

    def _context_file(self, name: str) -> Path:
        return self._context_dir(name) / "context.json"

    def _checkpoints_dir(self, name: str) -> Path:
        path = self._context_dir(name) / "checkpoints"
        if path.is_symlink():
            raise ValueError(
                f"Refusing to access checkpoints for '{name}' through a symbolic link."
            )
        contexts_root = self.contexts_dir.resolve()
        resolved = path.resolve(strict=False)
        if resolved != contexts_root and contexts_root not in resolved.parents:
            raise ValueError(
                f"Refusing to access checkpoints for '{name}' outside the "
                "context store."
            )
        return path
