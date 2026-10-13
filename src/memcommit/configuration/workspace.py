"""Locate common application state independently of project Stores."""

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import tempfile


class WorkspaceError(ValueError):
    pass


def config_file() -> Path:
    location = os.environ.get("MEMCOMMIT_CONFIG_DIR")
    if location:
        base = Path(location).expanduser()
    else:
        base = Path.home() / ".memcommit"
    return base.absolute() / "config.json"


def read_configuration(path: Path | None = None) -> dict:
    path = path or config_file()
    if path.is_symlink():
        raise WorkspaceError("Configuration cannot be a symbolic link.")
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise WorkspaceError(f"Cannot read configuration: {path}") from error
    if not isinstance(value, dict):
        raise WorkspaceError("Configuration must be an object.")
    return value


def write_configuration(value: dict, path: Path | None = None) -> None:
    path = path or config_file()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise WorkspaceError("Configuration cannot be a symbolic link.")
    fd, temporary = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@dataclass(frozen=True)
class WorkspacePaths:
    workspace_dir: Path



def workspace_paths() -> WorkspacePaths:
    """The application-owned home; project locations live in the registry."""
    return WorkspacePaths(config_file().parent.resolve())


def require_workspace_ready() -> None:
    path = config_file().parent
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise WorkspaceError(f"Application home is invalid: {path}")


def ensure_workspace() -> WorkspacePaths:
    paths = workspace_paths()
    path = paths.workspace_dir
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise WorkspaceError(f"Application home is invalid: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return paths


@contextmanager
def _bootstrap_lock(name: str, *, exclusive: bool):
    # Keep the lease in the common app home. A project move must exclude
    # concurrent CLI writes even when its source and target are on other devices.
    path = config_file().parent / name
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        try:
            fcntl.flock(
                fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
            )
        except BlockingIOError as error:
            raise WorkspaceError(
                "Workspace is in use; finish other mem commands and retry."
            ) from error
        yield
    finally:
        os.close(fd)


def workspace_lock(*, exclusive: bool = False):
    return _bootstrap_lock("workspace.lock", exclusive=exclusive)


def configuration_lock():
    return _bootstrap_lock("config.lock", exclusive=True)
