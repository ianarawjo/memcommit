"""Ordinary Profile registration, selection, import, and removal."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import uuid
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    ProfileConfigError,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    validate_profile_name,
)
from memcommit.models.profile import Profile
from memcommit.persistence.store.infrastructure.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)

from ._storage import (
    ProfileError as ProfileError,
    StoreInspection as StoreInspection,
    _copy_store as _copy_store,
    _fsync_directory as _fsync_directory,
    _prepare_profile_deletion_batch as _prepare_profile_deletion_batch,
    _publish_permanent_removal as _publish_permanent_removal,
    _write_registry as _write_registry,
    inspect_store as inspect_store,
)

from memcommit.application.operations.profile.study.topology import (
    group_study_run_profiles,
)


@dataclass(frozen=True)
class ProfileCreationResult:
    """One published folder Profile, its setup, and explicit selection receipt."""

    profile: Profile
    inspection: StoreInspection
    active_profile_name: str
    imported_file_count: int = 0
    skipped_paths: tuple[str, ...] = ()
    selected: bool = False


@dataclass(frozen=True)
class ProfileRenameResult:
    """One stable Profile identity published under a new display name."""

    previous_name: str
    profile: Profile
    active_profile_name: str
    was_active: bool
    changed: bool


@dataclass(frozen=True)
class ProfileRemovalResult:
    """One unregistered Profile whose Store was permanently deleted."""

    profile: Profile
    study_name: str | None
    active_profile_name: str
    remaining_study_profile_count: int
    deleted_store: Path


def list_profiles() -> tuple[ProfileRegistry, tuple[StoreInspection, ...]]:
    registry = load_profile_registry()
    visible = registry.visible_profiles
    base = tuple(
        inspect_store(
            profile_store_dir(item),
        )
        for item in visible
    )
    return registry, base


def use_profile(name: str) -> tuple[ProfileRegistry, StoreInspection, bool]:
    canonical = validate_profile_name(name)
    registry = load_profile_registry()
    target = registry.by_name(canonical)
    if target is None:
        raise ProfileError(f"Profile {canonical!r} does not exist.")
    inspection = inspect_store(
        profile_store_dir(target),
    )
    if target.uid == registry.active_uid:
        return registry, inspection, False
    updated = ProfileRegistry(
        generation=max(1, registry.generation + 1),
        active_uid=target.uid,
        profiles=registry.profiles,
    )
    _write_registry(updated)
    return updated, inspection, True


def _write_empty_profile_store(destination: Path) -> StoreInspection:
    """Stage the smallest valid store without resolving the active Profile.

    Profile creation is a control-plane operation. Building the new root
    directly keeps the process-local active store frozen while still using the
    same private permissions and durable JSON boundary as ordinary stores.
    """

    if destination.exists() or destination.is_symlink():
        raise ProfileError(f"Profile staging path is already occupied: {destination}")
    ensure_private_directory(destination)
    contexts = destination / "contexts"
    ensure_private_directory(contexts)
    state = destination / "state.json"
    descriptor = open_private_exclusive(state)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump({"current": None}, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        if state.exists() and not state.is_symlink():
            state.unlink()
        raise
    _fsync_directory(contexts)
    _fsync_directory(destination)
    return inspect_store(destination)


def create_profile(
    name: str,
    *,
    expected_generation: int | None = None,
    root_dir: Path | str | None = None,
    import_project_files: bool = False,
    expected_import_digest: str | None = None,
    select_created: bool = False,
) -> ProfileCreationResult:
    """Publish project setup and optional selection in one registry generation."""

    if any(type(value) is not bool for value in (import_project_files, select_created)):
        raise TypeError("Profile setup options must be boolean.")

    try:
        canonical = validate_profile_name(name)
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError("New Profile name is invalid.") from error
    if canonical.casefold() == AUTHORING_PROFILE_NAME.casefold():
        raise ProfileError("The fixed authoring Profile name is reserved.")
    registry = load_profile_registry()
    if (
        expected_generation is not None
        and registry.generation != expected_generation
    ):
        raise ProfileError(
            "Profile registry changed after create review; review the current "
            "Profile list and try again."
        )
    collision = next(
        (
            profile
            for profile in registry.profiles
            if profile.name.casefold() == canonical.casefold()
        ),
        None,
    )
    if collision is not None:
        raise ProfileError(f"Profile {collision.name!r} already exists.")
    profile = Profile(
        uid=str(uuid.uuid4()),
        name=canonical,
        kind="MANAGED",
        source={
            "kind": "EMPTY_PROFILE",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    from memcommit.application.operations.profile.project_root import (
        prepare_profile_root,
        write_profile_marker,
    )

    profile = prepare_profile_root(
        profile=profile, requested_root=root_dir, registry=registry
    )
    from memcommit.application.operations.profile.project_documents import (
        import_project_documents,
        prepare_project_import,
        verify_project_import_source,
    )

    prepared = (
        prepare_project_import(profile.root_dir) if import_project_files else None
    )
    if expected_import_digest is not None and (
        prepared is None or prepared.digest != expected_import_digest
    ):
        raise ProfileError(
            "Project files changed after create review; review creation again."
        )
    destination = profile_store_dir(profile)
    staging = destination.parent / f".mem-staging-{uuid.uuid4().hex}"
    published = False
    try:
        inspection = _write_empty_profile_store(staging)
        write_profile_marker(store_root=staging, uid=profile.uid)
        if import_project_files:
            from memcommit.persistence.store import ProfileStore

            store = ProfileStore(root=staging, create=False)
            if prepared is not None:
                import_project_documents(store=store, prepared=prepared)
            if prepared is not None:
                verify_project_import_source(prepared)
            inspection = inspect_store(staging)
        if destination.exists() or destination.is_symlink():
            raise ProfileError("Managed Profile destination is occupied.")
        os.replace(staging, destination)
        published = True
        try:
            _fsync_directory(destination.parent)
        except Exception:
            os.replace(destination, staging)
            published = False
            _fsync_directory(destination.parent)
            raise
        retained_profiles = registry.profiles
        if select_created and registry.generation == 0:
            from memcommit.application.operations.profile.config import (
                default_store_dir,
            )

            # A new install needs only its folder Profile. A physical legacy
            # authoring store is never discarded, even without a registry.
            if (
                not default_store_dir().exists()
                and not default_store_dir().is_symlink()
            ):
                retained_profiles = ()
        updated = replace(
            registry,
            generation=max(1, registry.generation + 1),
            profiles=(*retained_profiles, profile),
            active_uid=profile.uid if select_created else registry.active_uid,
        )
        try:
            _write_registry(updated)
        except Exception as error:
            try:
                visible = load_profile_registry()
            except (OSError, ProfileConfigError, ValueError) as read_error:
                raise ProfileError(
                    "Profile creation registry state could not be confirmed; "
                    "inspect it with 'mem profile list'."
                ) from read_error
            if visible == updated:
                raise ProfileError(
                    f"Profile {canonical!r} was created, but registry "
                    "durability could not be confirmed; it remains registered."
                ) from error
            if visible != registry:
                raise ProfileError(
                    "Profile creation registry changed unexpectedly; inspect "
                    "it with 'mem profile list'."
                ) from error
            os.replace(destination, staging)
            published = False
            _fsync_directory(destination.parent)
            raise
        return ProfileCreationResult(
            profile=profile,
            inspection=replace(inspection, root=destination),
            active_profile_name=updated.active.name,
            imported_file_count=len(prepared.files) if prepared else 0,
            skipped_paths=prepared.skipped_paths if prepared else (),
            selected=select_created,
        )
    finally:
        if not published and staging.exists() and not staging.is_symlink():
            shutil.rmtree(staging)


def rename_profile(
    new_name: str,
    *,
    old_name: str | None = None,
    expected_uid: str | None = None,
    expected_generation: int | None = None,
) -> ProfileRenameResult:
    """Rename one ordinary managed Profile without changing its stable identity."""

    try:
        canonical_new = validate_profile_name(new_name)
        canonical_old = (
            validate_profile_name(old_name) if old_name is not None else None
        )
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError("Profile rename name is invalid.") from error

    registry = load_profile_registry()
    if (
        expected_generation is not None
        and registry.generation != expected_generation
    ):
        raise ProfileError(
            "Profile registry changed after rename selection; review the "
            "current Profile list and try again."
        )
    target = (
        registry.active
        if canonical_old is None
        else registry.by_name(canonical_old)
    )
    if target is None:
        raise ProfileError(f"Profile {canonical_old!r} does not exist.")
    if expected_uid is not None and target.uid != expected_uid:
        raise ProfileError(
            f"Profile {target.name!r} identity changed after rename "
            "selection; nothing was renamed."
        )
    was_active = target.uid == registry.active_uid

    # An exact no-op must not become a hidden store validation or registry
    # write, including for fixed anchors that cannot actually be renamed.
    if target.name == canonical_new:
        return ProfileRenameResult(
            previous_name=target.name,
            profile=target,
            active_profile_name=registry.active.name,
            was_active=was_active,
            changed=False,
        )

    if target.kind == "AUTHORING":
        raise ProfileError("The fixed authoring Profile cannot be renamed.")
    if canonical_new.casefold() == AUTHORING_PROFILE_NAME.casefold():
        raise ProfileError("The fixed authoring Profile name is reserved.")
    collision = next(
        (
            profile
            for profile in registry.profiles
            if profile.uid != target.uid
            and profile.name.casefold() == canonical_new.casefold()
        ),
        None,
    )
    if collision is not None:
        raise ProfileError(f"Profile {collision.name!r} already exists.")
    # Rename is a control-plane metadata mutation, but validate the live
    # target before publishing a new locator for an unsafe or missing root.
    inspect_store(profile_store_dir(target))
    renamed = replace(target, name=canonical_new)
    updated = ProfileRegistry(
        generation=max(1, registry.generation + 1),
        active_uid=registry.active_uid,
        profiles=tuple(
            renamed if profile.uid == target.uid else profile
            for profile in registry.profiles
        ),
    )
    try:
        _write_registry(updated)
    except Exception as error:
        try:
            visible = load_profile_registry()
        except (OSError, ProfileConfigError, ValueError) as read_error:
            raise ProfileError(
                "Profile rename registry state could not be confirmed; "
                "inspect it with 'mem profile list'."
            ) from read_error
        if visible == updated:
            raise ProfileError(
                f"Profile {target.name!r} was renamed to {renamed.name!r}, "
                "but registry durability could not be confirmed; it remains "
                "renamed."
            ) from error
        if visible != registry:
            raise ProfileError(
                "Profile rename registry changed unexpectedly; inspect it "
                "with 'mem profile list'."
            ) from error
        raise

    return ProfileRenameResult(
        previous_name=target.name,
        profile=renamed,
        active_profile_name=updated.active.name,
        was_active=was_active,
        changed=True,
    )


def _profile_study_target(
    registry: ProfileRegistry,
    profile: Profile,
) -> tuple[str, str, tuple[Profile, ...]] | None:
    """Return the registered Study members containing a Profile, if any."""

    for group in group_study_run_profiles(registry.profiles):
        members = group.profiles
        if any(member.uid == profile.uid for member in members):
            return group.uid, group.name, members
    return None


def remove_profile(
    name: str,
    *,
    expected_uid: str | None = None,
    expected_generation: int | None = None,
) -> ProfileRemovalResult:
    """Permanently delete one Profile store, including every checkpoint."""

    canonical = validate_profile_name(name)
    registry = load_profile_registry()
    if (
        expected_generation is not None
        and registry.generation != expected_generation
    ):
        raise ProfileError("Profile registry changed after removal review.")
    target = registry.by_name(canonical)
    if target is None:
        raise ProfileError(f"Profile {canonical!r} does not exist.")
    if expected_uid is not None and target.uid != expected_uid:
        raise ProfileError("Profile identity changed after removal review.")
    if target.kind == "AUTHORING":
        raise ProfileError("The fixed authoring Profile cannot be removed.")
    if target.uid == registry.active_uid:
        raise ProfileError(
            f"Profile {target.name!r} is active; select another Profile "
            "before removing it."
        )
    store = profile_store_dir(target)
    # Validate every byte tree before it is moved into the private deletion
    # batch. This prevents a recursive delete from following an unsafe link
    # or accepting an already-corrupt Profile as the reviewed target.
    inspect_store(
        store,
    )
    study = _profile_study_target(registry=registry, profile=target)
    updated = ProfileRegistry(
        generation=max(1, registry.generation + 1),
        active_uid=registry.active_uid,
        profiles=tuple(
            profile for profile in registry.profiles if profile.uid != target.uid
        ),
    )
    batch = _prepare_profile_deletion_batch((target,))
    _publish_permanent_removal(
        previous=registry,
        updated=updated,
        batch=batch,
        profiles=(target,),
        label=f"Profile {target.name!r}",
    )
    members = study[2] if study is not None else ()
    return ProfileRemovalResult(
        profile=target,
        study_name=study[1] if study is not None else None,
        active_profile_name=registry.active.name,
        remaining_study_profile_count=max(0, len(members) - 1),
        deleted_store=store,
    )
