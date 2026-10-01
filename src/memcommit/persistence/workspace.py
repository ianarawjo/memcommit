"""Copy and verify workspace trees before a caller publishes their location."""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from memcommit.configuration.workspace import WorkspaceError


def tree_manifest(root: Path) -> dict[str, str | None]:
    if not root.exists():
        if root.is_symlink():
            raise WorkspaceError(f"Workspace source is a symbolic link: {root}")
        return {}
    if root.is_symlink() or not root.is_dir():
        raise WorkspaceError(f"Workspace source must be a directory: {root}")
    result = {}
    for directory, directories, files in os.walk(root, followlinks=False):
        for name in sorted((*directories, *files)):
            path = Path(directory) / name
            if path.is_symlink():
                raise WorkspaceError(f"Cannot relocate a symbolic link: {path}")
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                result[relative] = None
            elif path.is_file():
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                result[relative] = digest.hexdigest()
            else:
                raise WorkspaceError(f"Cannot relocate a special file: {path}")
    return result


@contextmanager
def copied_workspace(destination: Path, sources: tuple[tuple[Path, str], ...]):
    """Yield a verified destination; remove only our copy if publication fails."""
    if destination.exists() or destination.is_symlink():
        raise WorkspaceError("Workspace destination must be a new directory.")
    for source, _ in sources:
        source = source.resolve()
        if (
            destination == source
            or destination.is_relative_to(source)
            or source.is_relative_to(destination)
        ):
            raise WorkspaceError("Workspace source and destination cannot overlap.")
    manifests = [
        (source, relative, tree_manifest(source)) for source, relative in sources
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".mem-workspace-", dir=destination.parent))
    claimed = False
    try:
        for source, relative, expected in manifests:
            target = staging / relative
            if source.exists():
                shutil.copytree(source, target, dirs_exist_ok=True)
                if (
                    tree_manifest(target) != expected
                    or tree_manifest(source) != expected
                ):
                    raise WorkspaceError(
                        "Workspace changed during copying; retry with other clients closed."
                    )
        (staging / ".mem").mkdir(exist_ok=True, mode=0o700)
        (staging / "contexts").mkdir(exist_ok=True, mode=0o700)
        from memcommit.persistence.store.infrastructure.storage_permissions import (
            harden_private_storage_tree,
        )

        harden_private_storage_tree(staging / ".mem")
        # Claim a fresh location so a concurrent creator is never overwritten.
        destination.mkdir(mode=0o700)
        claimed = True
        for child in staging.iterdir():
            os.replace(child, destination / child.name)
        for source, _, expected in manifests:
            if tree_manifest(source) != expected:
                raise WorkspaceError(
                    "Workspace changed before publication; retry with other clients closed."
                )
        yield
    except BaseException:
        if claimed:
            shutil.rmtree(destination)
        raise
    finally:
        shutil.rmtree(staging)
