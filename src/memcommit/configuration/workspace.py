"""Locate workspace data without depending on the Store or Profile registry."""

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
import sys
from pathlib import Path
import tempfile


class WorkspaceError(ValueError):
    pass


def config_file() -> Path:
    location = os.environ.get("MEMCOMMIT_CONFIG_DIR")
    if location:
        base = Path(location).expanduser()
    elif sys.platform == "darwin":
        # Use the user-owned macOS settings directory, independently of data storage.
        base = Path.home() / "Library" / "Application Support" / "memcommit"
    else:
        base = Path.home() / ".config" / "memcommit"
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


def canonical_workspace(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceError("workspace_dir must be a nonempty directory path.")
    return Path(value).expanduser().resolve()


@dataclass(frozen=True)
class WorkspacePaths:
    workspace_dir: Path

    @property
    def store_dir(self) -> Path:
        return self.workspace_dir / ".mem"

    @property
    def contexts_dir(self) -> Path:
        return self.workspace_dir / "contexts"


def workspace_paths() -> WorkspacePaths:
    value = os.environ.get("MEMCOMMIT_WORKSPACE_DIR")
    if value is None:
        value = read_configuration().get(
            "workspace_dir", str(Path.home() / "memcommit")
        )
    return WorkspacePaths(canonical_workspace(value))


def legacy_locations() -> tuple[Path, Path]:
    return Path.home() / ".mem", Path.home() / ".mem-profiles"


def needs_legacy_migration() -> bool:
    return (
        "MEMCOMMIT_WORKSPACE_DIR" not in os.environ
        and "workspace_dir" not in read_configuration()
        and any(path.exists() or path.is_symlink() for path in legacy_locations())
    )


def require_workspace_ready() -> None:
    if needs_legacy_migration():
        raise WorkspaceError(
            "Existing ~/.mem or ~/.mem-profiles data needs migration. Run "
            "mem config set workspace_dir ~/memcommit (or your chosen directory). "
            "The original data will be retained."
        )


def ensure_workspace() -> WorkspacePaths:
    paths = workspace_paths()
    for path in (paths.workspace_dir, paths.store_dir, paths.contexts_dir):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise WorkspaceError(f"Workspace directory is invalid: {path}")
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return paths


@contextmanager
def _bootstrap_lock(name: str, *, exclusive: bool):
    # Keep the lock outside the moving tree. CLI operations hold a shared lease;
    # relocation cannot copy a workspace that another current CLI is modifying.
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
