"""Publish into a require-new directory; never merge or overwrite output files."""

from pathlib import Path
import os
import shutil
import tempfile

from memcommit.core.document import relative_document_path


def write_output_files(
    destination: Path, files: tuple[tuple[str, bytes], ...]
) -> tuple[str, ...]:
    destination = Path(destination).absolute()
    paths = [relative_document_path(path) for path, _ in files]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate output path.")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Output destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".mem-export-", dir=destination.parent))
    written = []
    created_dirs = []
    claimed = False
    try:
        for path, data in files:
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        # mkdir claims the destination exclusively, including in the presence
        # of a concurrent exporter. No replace/merge policy is implicit here.
        destination.mkdir()
        claimed = True
        for path, _ in files:
            target = destination / path
            parents = []
            parent = target.parent
            while parent != destination and not parent.exists():
                parents.append(parent)
                parent = parent.parent
            for parent in reversed(parents):
                parent.mkdir()
                created_dirs.append(parent)
            os.link(stage / path, target)
            written.append(target)
        return tuple(str(path) for path in written)
    except BaseException:
        for target in reversed(written):
            target.unlink(missing_ok=True)
        for parent in reversed(created_dirs):
            try:
                parent.rmdir()
            except OSError:
                pass
        if claimed:
            try:
                destination.rmdir()
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(stage)
