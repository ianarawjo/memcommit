"""Read a selected file tree without following links or executing its contents."""

from dataclasses import dataclass
from pathlib import Path
import os

from memcommit.application.capabilities.import_export.model import ProjectDocumentSnapshot


@dataclass(frozen=True)
class SourceReadResult:
    files: tuple[tuple[str, bytes], ...]
    skipped: tuple[str, ...]
    single_file: bool = False


def read_project_documents(root: Path) -> ProjectDocumentSnapshot:
    """Freeze selected project bytes without following links or hidden Store state."""
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Project must be a regular directory: {root}")
    rules = read_project_document_rules(root)
    ignore_bytes = rules.ignore_bytes
    files = []
    total_bytes = 0
    visited = 0
    selected_directories = []

    def raise_walk_error(error):
        raise error

    for parent, directories, names in os.walk(root, followlinks=False, onerror=raise_walk_error):
        directories.sort()
        visited += len(directories)
        if visited > 100_000:
            raise ValueError("Project discovery exceeds the bounded entry-count limit.")
        parent = Path(parent)
        if parent != root:
            selected_directories.append(parent.relative_to(root).as_posix())
        for name in list(directories):
            child = parent / name
            relative = child.relative_to(root).as_posix()
            if child.is_symlink() or rules.excludes(relative, directory=True):
                directories.remove(name)
        for name in sorted(names):
            visited += 1
            if visited > 100_000:
                raise ValueError("Project discovery exceeds the bounded file-count limit.")
            child = parent / name
            relative = child.relative_to(root).as_posix()
            if child.is_symlink() or not child.is_file() or rules.excludes(relative):
                continue
            if not rules.supports(relative):
                continue
            if child.stat().st_size > 2_000_000:
                raise ValueError(f"Project document exceeds the bounded file-size limit: {relative}")
            data = child.read_bytes()
            total_bytes += len(data)
            if len(data) > 2_000_000 or total_bytes > 50_000_000 or len(files) >= 10_000:
                raise ValueError("Project documents exceed the bounded discovery limit.")
            files.append((relative, data))
    return ProjectDocumentSnapshot(root, tuple(sorted(files)), ignore_bytes, tuple(sorted(selected_directories)))


def read_project_document_rules(root: Path):
    from memcommit.application.capabilities.import_export.project_documents import ProjectDocumentRules

    path = require_regular_output_path(Path(root).absolute(), ".memignore")
    if path.exists() and path.stat().st_size > 100_000:
        raise ValueError(".memignore exceeds the bounded project rule limit.")
    return ProjectDocumentRules(path.read_bytes() if path.exists() else None)


def require_regular_output_path(base: Path, relative: str) -> Path:
    """Reject links and special files at every component of an external claim."""
    from memcommit.core.document_path import relative_document_path

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
    from memcommit.core.document_path import relative_document_path

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
