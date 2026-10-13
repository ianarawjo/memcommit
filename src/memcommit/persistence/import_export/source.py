"""Read a selected file tree without following links or executing its contents."""

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class SourceReadResult:
    files: tuple[tuple[str, bytes], ...]
    skipped: tuple[str, ...]
    single_file: bool = False


def require_regular_output_path(base: Path, relative: str) -> Path:
    """Reject links and special files at every component of an external claim."""
    from memcommit.core.document import relative_document_path

    relative_document_path(relative)
    base = Path(base).absolute()
    if any(part.casefold() in {".mem", ".git"} for part in base.parts):
        raise ValueError("Documents cannot be written inside internal .mem or .git state.")
    for parent in (*reversed(base.parents), base):
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError(f"Invalid output directory: {parent}")
    target = base / relative
    for parent in target.parents:
        if parent == base:
            break
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError(f"Invalid output directory: {parent}")
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError(f"Output must be a regular file: {target}")
    return target


def read_output_files(base: Path, paths) -> dict[str, bytes | None]:
    result = {}
    for relative in paths:
        path = require_regular_output_path(base, relative)
        result[relative] = path.read_bytes() if path.exists() else None
    return result


def read_output_tree(
    base: Path, prefix: str, *, excluded_paths=(), excluded_prefixes=()
) -> tuple[dict[str, bytes], tuple[str, ...]]:
    """A complete selected tree; unreadable members must never look like deletion."""
    from memcommit.core.document import relative_document_path

    relative_document_path(prefix)
    base = Path(base).absolute()
    root = base / prefix
    for parent in (*reversed(root.parents), root):
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError(f"Invalid output tree: {parent}")
    if not root.exists():
        return {}, ()
    files = {}
    directories = []

    def raise_walk_error(error):
        raise error

    for parent, dirs, names in os.walk(
        root, followlinks=False, onerror=raise_walk_error
    ):
        directories.append(Path(parent).relative_to(base).as_posix())
        for name in sorted(dirs):
            child = Path(parent) / name
            relative = child.relative_to(base).as_posix()
            if any(
                relative == excluded or relative.startswith(excluded + "/")
                for excluded in excluded_prefixes
            ):
                dirs.remove(name)
                continue
            if child.is_symlink():
                raise ValueError(f"Output tree contains a symbolic link: {child}")
        for name in sorted(names):
            child = Path(parent) / name
            if child.relative_to(base).as_posix() in excluded_paths:
                continue
            if child.is_symlink() or not child.is_file():
                raise ValueError(f"Output tree contains a nonregular file: {child}")
            files[child.relative_to(base).as_posix()] = child.read_bytes()
    return files, tuple(sorted(directories))


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
            if name.casefold() in {".mem", ".git"} or child.is_symlink() or not recursive:
                skipped.append(child.relative_to(path).as_posix() + "/")
                dirs.remove(name)
        for name in sorted(names):
            child = Path(parent) / name
            relative = child.relative_to(path).as_posix()
            if child.is_symlink() or not child.is_file():
                skipped.append(relative)
            elif child.suffix.lower() in {".md", ".txt", ".yaml", ".yml"} or (path / "SKILL.md").is_file() or name == "context.json" or relative.startswith("attached-files/"):
                files.append((relative, child.read_bytes()))
            else:
                skipped.append(relative)
    return SourceReadResult(tuple(sorted(files)), tuple(sorted(skipped)))
