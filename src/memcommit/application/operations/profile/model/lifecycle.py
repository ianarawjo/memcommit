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
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    profile_stores_dir,
    validate_profile_name,
)
from memcommit.application.capabilities.authority.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)

from ._storage import (
    ProfileError as ProfileError,
    StoreInspection as StoreInspection,
    _copy_store as _copy_store,
    _fsync_directory as _fsync_directory,
    _inspection_with_grants as _inspection_with_grants,
    _prepare_profile_deletion_batch as _prepare_profile_deletion_batch,
    _publish_permanent_removal as _publish_permanent_removal,
    _read_granted_public_names as _read_granted_public_names,
    _registry_lock as _registry_lock,
    _source_store as _source_store,
    _write_registry as _write_registry,
    inspect_store as inspect_store,
)

from .study import (
    study_profile_groups as study_profile_groups,
    study_run_profile_pairs as study_run_profile_pairs,
)


@dataclass(frozen=True)
class ProfileCreationResult:
    """One fresh empty managed Profile published without selecting it."""

    profile: ProfileEntry
    inspection: StoreInspection
    active_profile_name: str


@dataclass(frozen=True)
class ProfileRenameResult:
    """One stable Profile identity published under a new display name."""

    previous_name: str
    profile: ProfileEntry
    active_profile_name: str
    was_active: bool
    changed: bool


@dataclass(frozen=True)
class ProfileRemovalResult:
    """One Profile permanently deleted behind a retained identity tombstone."""

    profile: ProfileEntry
    study_name: str | None
    active_profile_name: str
    study_profile_count: int
    study_removed_count: int
    removed_grant_count: int
    deleted_store: Path


def list_profiles() -> tuple[ProfileRegistry, tuple[StoreInspection, ...]]:
    registry = load_profile_registry()
    visible = registry.visible_profiles
    base = tuple(
        inspect_store(
            profile_store_dir(item),
            allowed_virtual_currents=_read_granted_public_names(
                registry,
                item.uid,
            ),
        )
        for item in visible
    )
    cache = {
        profile.uid: inspection
        for profile, inspection in zip(visible, base, strict=True)
    }
    return registry, tuple(
        _inspection_with_grants(
            registry,
            profile,
            inspection,
            cache=cache,
        )
        for profile, inspection in zip(visible, base, strict=True)
    )


def use_profile(name: str) -> tuple[ProfileRegistry, StoreInspection, bool]:
    canonical = validate_profile_name(name)
    with _registry_lock():
        registry = load_profile_registry()
        target = registry.by_name(canonical)
        if target is None:
            raise ProfileError(f"Profile {canonical!r} does not exist.")
        if registry.is_removed(target):
            raise ProfileError(
                f"Profile {canonical!r} was removed from direct selection."
            )
        inspection = _inspection_with_grants(
            registry,
            target,
            inspect_store(
                profile_store_dir(target),
                allowed_virtual_currents=_read_granted_public_names(
                    registry,
                    target.uid,
                ),
            ),
        )
        if target.uid == registry.active_uid:
            return registry, inspection, False
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=target.uid,
            profiles=registry.profiles,
            grants=registry.grants,
            removed_profile_uids=registry.removed_profile_uids,
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
) -> ProfileCreationResult:
    """Atomically publish one empty managed Profile and keep selection fixed."""

    try:
        canonical = validate_profile_name(name)
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError("New Profile name is invalid.") from error
    if canonical.casefold() == AUTHORING_PROFILE_NAME.casefold():
        raise ProfileError("The fixed authoring Profile name is reserved.")
    with _registry_lock():
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
        legacy_study = next(
            (
                group
                for group in study_profile_groups(registry.profiles)
                if group.name.casefold() == canonical.casefold()
            ),
            None,
        )
        if legacy_study is not None:
            raise ProfileError(
                f"Profile name {canonical!r} conflicts with existing legacy "
                f"Study {legacy_study.name!r}."
            )

        profile = ProfileEntry(
            uid=str(uuid.uuid4()),
            name=canonical,
            kind="MANAGED",
            source={
                "kind": "EMPTY_PROFILE",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        staging = profile_stores_dir() / f".{profile.uid}.staging-{uuid.uuid4().hex}"
        destination = profile_store_dir(profile)
        published = False
        try:
            inspection = _write_empty_profile_store(staging)
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
            updated = replace(
                registry,
                generation=max(1, registry.generation + 1),
                profiles=(*registry.profiles, profile),
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

    with _registry_lock():
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
        if registry.is_removed(target):
            raise ProfileError(
                f"Profile {target.name!r} cannot be renamed while removed."
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

        groups = study_profile_groups(registry.profiles)
        membership = next(
            (
                group
                for group in groups
                if any(
                    profile.uid == target.uid
                    for profile in (*group.profiles, *group.support_profiles)
                )
            ),
            None,
        )
        if target.kind == "AUTHORING":
            raise ProfileError("The fixed authoring Profile cannot be renamed.")
        if membership is not None:
            raise ProfileError(
                f"Profile {target.name!r} is a member of legacy Study "
                f"{membership.name!r} and cannot be renamed individually."
            )
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
        group_collision = next(
            (
                group
                for group in groups
                if group.name.casefold() == canonical_new.casefold()
            ),
            None,
        )
        if group_collision is not None:
            raise ProfileError(
                f"Profile name {canonical_new!r} conflicts with existing legacy "
                f"Study {group_collision.name!r}."
            )

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
            grants=registry.grants,
            removed_profile_uids=registry.removed_profile_uids,
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
    profile: ProfileEntry,
) -> tuple[str, str, tuple[ProfileEntry, ...]] | None:
    """Return the complete Study containing a Profile, when one exists."""

    for group in study_profile_groups(registry.profiles):
        members = (*group.profiles, *group.support_profiles)
        if any(member.uid == profile.uid for member in members):
            return group.uid, group.name, members
    for pair in study_run_profile_pairs(registry.profiles):
        members = (pair.participant, pair.authority)
        if any(member.uid == profile.uid for member in members):
            return pair.uid, pair.name, members
    return None


def remove_profile(
    name: str,
    *,
    expected_uid: str | None = None,
    expected_generation: int | None = None,
) -> ProfileRemovalResult:
    """Permanently delete one Profile store, including every checkpoint."""

    canonical = validate_profile_name(name)
    with _registry_lock():
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
        if (
            registry.is_removed(target)
            and not store.exists()
            and not store.is_symlink()
        ):
            raise ProfileError(f"Profile {target.name!r} is already removed.")

        # Validate every byte tree before it is moved into the private deletion
        # batch. This prevents a recursive delete from following an unsafe link
        # or accepting an already-corrupt Profile as the reviewed target.
        inspect_store(
            store,
            allowed_virtual_currents=_read_granted_public_names(
                registry,
                target.uid,
            ),
        )
        study = _profile_study_target(registry, target)
        removed = frozenset((*registry.removed_profile_uids, target.uid))
        ordered_removed = tuple(
            profile.uid for profile in registry.profiles if profile.uid in removed
        )
        retained_grants = tuple(
            grant
            for grant in registry.grants
            if target.uid
            not in {grant.authority_profile_uid, grant.grantee_profile_uid}
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=retained_grants,
            removed_profile_uids=ordered_removed,
        )
        batch = _prepare_profile_deletion_batch((target,))
        _publish_permanent_removal(
            registry,
            updated,
            batch=batch,
            profiles=(target,),
            label=f"Profile {target.name!r}",
        )
        members = study[2] if study is not None else ()
        return ProfileRemovalResult(
            profile=target,
            study_name=study[1] if study is not None else None,
            active_profile_name=registry.active.name,
            study_profile_count=len(members),
            study_removed_count=sum(member.uid in removed for member in members),
            removed_grant_count=len(registry.grants) - len(retained_grants),
            deleted_store=store,
        )


def import_profile(
    name: str,
    source: Path,
    *,
    provenance: dict[str, object] | None = None,
) -> tuple[ProfileEntry, StoreInspection]:
    canonical = validate_profile_name(name)
    if canonical == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring profile cannot be imported.")
    source_root = _source_store(source)
    inspect_store(source_root)
    with _registry_lock():
        registry = load_profile_registry()
        if registry.by_name(canonical) is not None:
            raise ProfileError(f"Profile {canonical!r} already exists.")
        profile = ProfileEntry(
            uid=str(uuid.uuid4()),
            name=canonical,
            kind="MANAGED",
            source=provenance,
        )
        staging = profile_stores_dir() / f".{profile.uid}.staging-{uuid.uuid4().hex}"
        published = False
        try:
            inspection = _copy_store(source_root, staging)
            destination = profile_store_dir(profile)
            if destination.exists() or destination.is_symlink():
                raise ProfileError("Managed profile destination is occupied.")
            os.replace(staging, destination)
            published = True
            updated = replace(
                registry,
                generation=max(1, registry.generation + 1),
                profiles=(*registry.profiles, profile),
            )
            try:
                _write_registry(updated)
            except Exception:
                os.replace(destination, staging)
                published = False
                raise
            return profile, replace(inspection, root=destination)
        finally:
            candidate = profile_store_dir(profile) if published else staging
            if not published and candidate.exists() and not candidate.is_symlink():
                shutil.rmtree(candidate)
