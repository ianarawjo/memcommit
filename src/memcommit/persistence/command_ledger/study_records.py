"""Initialize and resolve retained Study records independently of project folders."""

from collections.abc import Mapping
import json
from pathlib import Path

from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
    study_run_identity,
)
from memcommit.models.profile import Profile
from memcommit.persistence.store.infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)
from memcommit.persistence.store.infrastructure.storage_permissions import (
    ensure_private_directory,
)


def initialize_study_records(
    records_root: Path,
    *,
    study_uid: str,
    study_name: str,
    created_at: str,
    profiles_by_session: Mapping[str, Profile],
) -> None:
    """Create session record directories and their original run ownership manifest."""
    ensure_private_directory(records_root)
    for session in profiles_by_session:
        ensure_private_directory(records_root / session)
    # The directory may be staged; the manifest retains final project locations.
    _write_json_atomic(
        records_root / "study.json",
        {
            "schema_version": 1,
            "study_uid": study_uid,
            "study_name": study_name,
            "created_at": created_at,
            "profiles": [
                {"uid": profile.uid, "session": session, "root_dir": profile.root_dir}
                for session, profile in profiles_by_session.items()
            ],
        },
    )


def study_record_directory(profile: Profile, category: str) -> Path | None:
    identity = study_run_identity(profile)
    if identity is None or identity.records_root is None:
        return None
    return Path(identity.records_root) / identity.session / category


def registered_profile_for_store(store_dir: Path) -> Profile | None:
    root = Path(store_dir).resolve()
    return next(
        (
            profile
            for profile in load_profile_registry().profiles
            if profile_store_dir(profile) == root
        ),
        None,
    )


def validate_study_record_directory(
    profile: Profile, directory: Path, *, create: bool
) -> Path:
    """Require the run manifest to bind both immutable identities before access."""
    identity = study_run_identity(profile)
    if identity is None or identity.records_root is None:
        raise ProfileConfigError("Profile has no external Study records.")
    root = Path(identity.records_root)
    if not directory.is_relative_to(root):
        raise ProfileConfigError(
            "Study record directory is outside its registered root."
        )
    for path in (directory, *directory.parents):
        if path.is_symlink() or path.exists() and not path.is_dir():
            raise ProfileConfigError(f"Invalid Study record directory: {path}")
    manifest_path = root / "study.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ProfileConfigError("Study record manifest is missing or unsafe.")
    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, ValueError) as error:
        raise ProfileConfigError("Study record manifest is unreadable.") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("study_uid") != identity.uid
        or not isinstance(manifest.get("profiles"), list)
        or not any(
            isinstance(member, dict)
            and member.get("uid") == profile.uid
            and member.get("session") == identity.session
            for member in manifest["profiles"]
        )
    ):
        raise ProfileConfigError(
            "Study record manifest belongs to another run or Profile."
        )
    if create:
        for path in reversed((directory, *directory.parents)):
            if path == root or path.is_relative_to(root):
                ensure_private_directory(path)
    return directory
