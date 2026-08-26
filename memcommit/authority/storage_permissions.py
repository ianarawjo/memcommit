"""Owner-only POSIX permissions for private MemCommit storage.

This module deliberately changes only filesystem mode bits.  It neither
deletes retained artifacts nor treats possession of a cache file as current
application authority; operation runtimes must still revalidate Grants and
frozen revisions before use.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


class StoragePermissionError(ValueError):
    """A private storage tree contains an unsafe filesystem object."""


@dataclass(frozen=True)
class StoragePermissionReport:
    """Counts from one content-preserving permission migration."""

    root: Path
    directories: int
    files: int


def ensure_private_directory(path: Path, *, parents: bool = False) -> None:
    """Create or harden one directory without following a symbolic link."""

    value = Path(path)
    if value.is_symlink():
        raise StoragePermissionError(
            f"Private storage directory cannot be a symbolic link: {value}"
        )
    if value.exists() and not value.is_dir():
        raise StoragePermissionError(
            f"Private storage path is not a directory: {value}"
        )
    value.mkdir(parents=parents, exist_ok=True, mode=PRIVATE_DIRECTORY_MODE)
    # mkdir's mode is filtered by umask and does not repair an existing tree.
    os.chmod(value, PRIVATE_DIRECTORY_MODE, follow_symlinks=False)


def open_private_exclusive(path: Path) -> int:
    """Create one owner-only file and return its writable descriptor."""

    value = Path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(value, flags, PRIVATE_FILE_MODE)
    try:
        # Creation mode is filtered by umask.  Set the exact private mode
        # before the caller writes any retained Memory or provider material.
        os.fchmod(descriptor, PRIVATE_FILE_MODE)
    except BaseException:
        os.close(descriptor)
        if value.exists() and not value.is_symlink():
            value.unlink()
        raise
    return descriptor


def _private_tree_paths(root: Path) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Preflight one tree completely before changing any permission bits."""

    directories: list[Path] = []
    files: list[Path] = []

    def visit(directory: Path) -> None:
        if directory.is_symlink() or not directory.is_dir():
            raise StoragePermissionError(
                f"Private storage tree contains an unsafe directory: {directory}"
            )
        directories.append(directory)
        try:
            entries = tuple(directory.iterdir())
        except OSError as error:
            raise StoragePermissionError(
                f"Private storage directory could not be inspected: {directory}"
            ) from error
        for entry in entries:
            if entry.is_symlink():
                raise StoragePermissionError(
                    f"Private storage tree contains a symbolic link: {entry}"
                )
            if entry.is_dir():
                visit(entry)
            elif entry.is_file():
                files.append(entry)
            else:
                raise StoragePermissionError(
                    f"Private storage tree contains an unsupported object: {entry}"
                )

    visit(root)
    return tuple(directories), tuple(files)


def harden_private_storage_tree(root: Path) -> StoragePermissionReport:
    """Restrict an existing tree to its owner without changing file contents.

    Missing roots are a no-op so callers can migrate the legacy and managed
    Profile roots independently.  The complete tree is checked before chmod;
    a symbolic link or special file therefore fails without partially changing
    the already inspected tree or following a path outside the requested root.
    """

    value = Path(root)
    if not value.exists() and not value.is_symlink():
        return StoragePermissionReport(value, directories=0, files=0)
    directories, files = _private_tree_paths(value)
    try:
        for path in files:
            os.chmod(path, PRIVATE_FILE_MODE, follow_symlinks=False)
        # Harden children before their parents so migration remains able to
        # traverse the complete legacy tree until the final root change.
        for path in reversed(directories):
            os.chmod(path, PRIVATE_DIRECTORY_MODE, follow_symlinks=False)
    except OSError as error:
        raise StoragePermissionError(
            f"Private storage permissions could not be hardened: {value}"
        ) from error
    return StoragePermissionReport(
        value,
        directories=len(directories),
        files=len(files),
    )


__all__ = [
    "PRIVATE_DIRECTORY_MODE",
    "PRIVATE_FILE_MODE",
    "StoragePermissionError",
    "StoragePermissionReport",
    "ensure_private_directory",
    "harden_private_storage_tree",
    "open_private_exclusive",
]
