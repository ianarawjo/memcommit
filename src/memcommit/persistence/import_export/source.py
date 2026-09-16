"""Read a selected file tree without following links or executing its contents."""

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class SourceReadResult:
    files: tuple[tuple[str, bytes], ...]
    skipped: tuple[str, ...]
    single_file: bool = False


def read_source(path: Path, recursive: bool = False) -> SourceReadResult:
    path = Path(path)
    if path.is_symlink():
        raise ValueError(
            "Input must be a regular file or directory, not a symbolic link."
        )
    if path.is_file():
        return SourceReadResult(((path.name, path.read_bytes()),), (), True)
    if not path.is_dir():
        raise FileNotFoundError(f"Input does not exist: {path}")
    files = []
    skipped = []
    for parent, dirs, names in os.walk(path, followlinks=False):
        dirs.sort()
        for name in list(dirs):
            child = Path(parent) / name
            if child.is_symlink() or not recursive:
                skipped.append(child.relative_to(path).as_posix() + "/")
                dirs.remove(name)
        for name in sorted(names):
            child = Path(parent) / name
            relative = child.relative_to(path).as_posix()
            if child.is_symlink() or not child.is_file():
                skipped.append(relative)
            else:
                files.append((relative, child.read_bytes()))
    return SourceReadResult(tuple(sorted(files)), tuple(sorted(skipped)))
