"""Register a physical project once without claiming its existing documents."""

from dataclasses import replace
import json
from pathlib import Path

from .config import ProfileConfigError, profile_root_dir


def prepare_profile_root(profile, requested_root, registry):
    root = Path(requested_root).expanduser().resolve() if requested_root is not None else profile_root_dir(profile).resolve()
    if root.exists() and not root.is_dir():
        raise ProfileConfigError(f"Project folder is not a directory: {root}")
    if any(part in {".mem", ".git"} for part in root.parts):
        raise ProfileConfigError("A project cannot be inside internal .mem or .git state.")
    for other in registry.visible_profiles:
        existing = profile_root_dir(other).resolve()
        if root == existing or root.is_relative_to(existing) or existing.is_relative_to(root):
            raise ProfileConfigError(f"Project folder overlaps Profile {other.name!r}: {existing}")
    if (root / ".mem").exists() or (root / ".mem").is_symlink():
        raise ProfileConfigError(f"Project folder already contains .mem: {root}")
    root.mkdir(parents=True, exist_ok=True)
    return replace(profile, root_dir=str(root))


def write_profile_marker(store_root, uid):
    # The registry and local marker agree on ownership even after a rename.
    path = Path(store_root) / "profile.json"
    if path.is_symlink():
        raise ProfileConfigError("Profile marker cannot be a symbolic link.")
    from memcommit.persistence.store.infrastructure.atomic_io import _write_json_atomic
    _write_json_atomic(path, {"profile_uid": uid})


def validate_profile_marker(profile):
    path = profile_root_dir(profile) / ".mem" / "profile.json"
    if path.is_symlink() or not path.is_file():
        raise ProfileConfigError(f"Profile ownership marker is missing: {path}")
    if json.loads(path.read_text(encoding="utf-8")) != {"profile_uid": profile.uid}:
        raise ProfileConfigError("Project .mem belongs to a different Profile.")
