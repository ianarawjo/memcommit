"""One external writer for new and existing Export and Sync destinations."""

from hashlib import sha256
from pathlib import Path
import os
import shutil
import stat
import tempfile

from memcommit.core.document_path import relative_document_path
from .source import read_output_files, require_regular_output_path


def write_output_files(
    destination: Path,
    files: tuple[tuple[str, bytes], ...],
    *,
    removals: tuple[str, ...] = (),
    directories: tuple[str, ...] = (),
    removed_directories: tuple[str, ...] = (),
    expected_hashes: dict[str, str | None] | None = None,
) -> tuple[str, ...]:
    destination = Path(destination).absolute()
    paths = [relative_document_path(path) for path, _ in files]
    if len({path.casefold() for path in paths}) != len(paths):
        raise ValueError("Duplicate output path.")
    removed_paths = tuple(relative_document_path(path) for path in removals)
    if set(paths).intersection(removed_paths):
        raise ValueError("Output path is both written and removed.")
    for path in paths:
        if any(other.startswith(path + "/") for other in paths):
            raise ValueError("Output file is also used as a directory.")
    originals = read_output_files(destination, (*paths, *removed_paths))
    for directory in directories:
        relative_document_path(directory)
        if any(directory == path or directory.startswith(path + "/") for path in paths):
            raise ValueError("Output directory conflicts with an output file.")
        target = destination / directory
        for parent in (*reversed(target.parents), target):
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError(f"Invalid output directory: {parent}")
    if expected_hashes is not None:
        if set(expected_hashes) != set(originals):
            raise ValueError("Incomplete external publication preconditions.")
        for path, data in originals.items():
            digest = sha256(data).hexdigest() if data is not None else None
            if digest != expected_hashes[path]:
                raise ValueError(f"External file changed before publication: {path}")
    changed = tuple((path, data) for path, data in files if originals[path] != data)
    modes = {
        path: stat.S_IMODE((destination / path).stat().st_mode)
        for path, data in originals.items()
        if data is not None
    }
    created_dirs = []
    installed = []
    installed_after = {}
    removed_dirs = []
    stage = None

    def ensure_directory(path):
        missing = []
        while not path.exists():
            missing.append(path)
            path = path.parent
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"Invalid output directory: {path}")
        for path in reversed(missing):
            path.mkdir()
            created_dirs.append(path)

    def require_unchanged_target(path):
        target = require_regular_output_path(destination, path)
        actual = target.read_bytes() if target.exists() else None
        if actual != originals[path]:
            raise ValueError(f"External file changed during publication: {path}")
        return target

    try:
        ensure_directory(destination)
        stage = Path(tempfile.mkdtemp(prefix=".mem-export-", dir=destination))
        for index, (path, data) in enumerate(changed):
            staged = stage / str(index)
            with staged.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(staged, modes.get(path, 0o644))
        for directory in directories:
            ensure_directory(destination / directory)
        for index, (path, _) in enumerate(changed):
            target = require_unchanged_target(path)
            ensure_directory(target.parent)
            # Claim new files exclusively; replace existing files in one
            # rename and preserve their executable/access mode.
            if originals[path] is None:
                os.link(stage / str(index), target)
            else:
                os.replace(stage / str(index), target)
            installed.append(path)
            installed_after[path] = dict(changed)[path]
        for path in removed_paths:
            if originals[path] is not None:
                require_unchanged_target(path).unlink()
                installed.append(path)
                installed_after[path] = None
        for relative in sorted(
            removed_directories, key=lambda path: path.count("/"), reverse=True
        ):
            relative_document_path(relative)
            target = destination / relative
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise ValueError(f"Invalid removed directory: {target}")
            if target.exists():
                mode = stat.S_IMODE(target.stat().st_mode)
                try:
                    target.rmdir()
                except OSError as error:
                    import errno

                    # Disabled children/unowned external files may still use
                    # a parent. Never infer permission to remove their contents.
                    if error.errno not in {errno.ENOTEMPTY, errno.EEXIST}:
                        raise
                else:
                    removed_dirs.append((target, mode))
    except BaseException as publication_error:
        # Restore preimages on an exception. Process death instead leaves
        # Sync's before/after-hash manifest available for a checked retry.
        for directory, mode in reversed(removed_dirs):
            directory.mkdir(parents=True, exist_ok=True)
            directory.chmod(mode)
        rollback_conflicts = []
        for path in reversed(installed):
            target = destination / path
            try:
                checked = require_regular_output_path(destination, path)
                actual = checked.read_bytes() if checked.exists() else None
            except (OSError, ValueError):
                rollback_conflicts.append(path)
                continue
            if actual != installed_after[path]:
                rollback_conflicts.append(path)
                continue
            data = originals[path]
            if data is None:
                target.unlink(missing_ok=True)
            else:
                fd, temporary = tempfile.mkstemp(prefix=".restore-", dir=target.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.chmod(temporary, modes[path])
                    os.replace(temporary, target)
                finally:
                    Path(temporary).unlink(missing_ok=True)
        if stage is not None:
            shutil.rmtree(stage)
            stage = None
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        if rollback_conflicts:
            raise RuntimeError(
                "Export rollback preserved independently changed paths: "
                + ", ".join(rollback_conflicts)
            ) from publication_error
        raise
    finally:
        if stage is not None:
            shutil.rmtree(stage)
    return tuple(str(destination / path) for path in paths)
