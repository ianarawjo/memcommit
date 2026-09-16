"""Atomic rename and permanent removal of current Study Profile pairs."""

from __future__ import annotations

from dataclasses import replace

from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    validate_profile_name,
)
from memcommit.application.operations.profile.errors import ProfileError
from memcommit.application.operations.profile.model._storage import (
    _prepare_profile_deletion_batch,
    _publish_permanent_removal,
    _read_granted_access_names,
    _registry_lock,
    _write_registry,
    inspect_store,
)

from .model import StudyRemovalResult, StudyRenameResult
from .topology import _study_target, study_run_profile_pairs


def rename_study(
    old_name: str,
    new_name: str,
    *,
    expected_uid: str | None = None,
    expected_generation: int | None = None,
) -> StudyRenameResult:
    """Rename one complete Study without changing its stable identity.

    The shared Study label is independent of both member Profile display names.
    """

    try:
        canonical_old = validate_profile_name(old_name)
        canonical_new = validate_profile_name(new_name)
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError("Study rename name is invalid.") from error

    with _registry_lock():
        registry = load_profile_registry()
        if (
            expected_generation is not None
            and registry.generation != expected_generation
        ):
            raise ProfileError(
                "Profile registry changed after Study rename selection; review "
                "the current Profile list and try again."
            )
        study_uid, study_name, members = _study_target(registry, canonical_old)
        if expected_uid is not None and study_uid != expected_uid:
            raise ProfileError(
                f"Study {study_name!r} identity changed after rename selection; "
                "nothing was renamed."
            )
        if all(registry.is_removed(profile) for profile in members):
            raise ProfileError(f"Study {study_name!r} is already removed.")
        if study_name == canonical_new:
            return StudyRenameResult(
                uid=study_uid,
                previous_name=study_name,
                name=study_name,
                profiles=members,
                active_profile_name=registry.active.name,
                changed=False,
            )

        studies = study_run_profile_pairs(registry.profiles)
        collision = next(
            (
                study
                for study in studies
                if study.uid != study_uid
                and study.name.casefold() == canonical_new.casefold()
            ),
            None,
        )
        if collision is not None:
            raise ProfileError(f"Study {collision.name!r} already exists.")

        renamed_by_uid: dict[str, ProfileEntry] = {}
        for profile in members:
            source = profile.source
            if not isinstance(source, dict):
                raise ProfileError("Study Profile provenance is invalid.")
            renamed_source = dict(source)
            renamed_source["study_name"] = canonical_new
            renamed_by_uid[profile.uid] = replace(
                profile,
                source=renamed_source,
            )

        updated_profiles = tuple(
            renamed_by_uid.get(profile.uid, profile) for profile in registry.profiles
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=updated_profiles,
            grants=registry.grants,
            removed_profile_uids=registry.removed_profile_uids,
            grant_placements=registry.grant_placements,
        )
        try:
            _write_registry(updated)
        except Exception as error:
            try:
                visible = load_profile_registry()
            except (OSError, ProfileConfigError, ValueError) as read_error:
                raise ProfileError(
                    "Study rename registry state could not be confirmed; inspect "
                    "it with 'mem profile list'."
                ) from read_error
            if visible == updated:
                raise ProfileError(
                    f"Study {study_name!r} was renamed to {canonical_new!r}, but "
                    "registry durability could not be confirmed; it remains "
                    "renamed."
                ) from error
            if visible != registry:
                raise ProfileError(
                    "Study rename registry changed unexpectedly; inspect it "
                    "with 'mem profile list'."
                ) from error
            raise

        renamed_members = tuple(renamed_by_uid[profile.uid] for profile in members)
        return StudyRenameResult(
            uid=study_uid,
            previous_name=study_name,
            name=canonical_new,
            profiles=renamed_members,
            active_profile_name=updated.active.name,
            changed=True,
        )


def remove_study(
    name: str,
    *,
    expected_uid: str | None = None,
    expected_generation: int | None = None,
) -> StudyRemovalResult:
    """Permanently delete every Profile store in one Study."""

    with _registry_lock():
        registry = load_profile_registry()
        if (
            expected_generation is not None
            and registry.generation != expected_generation
        ):
            raise ProfileError("Profile registry changed after removal review.")
        study_uid, study_name, profiles = _study_target(registry, name)
        if expected_uid is not None and study_uid != expected_uid:
            raise ProfileError("Study identity changed after removal review.")
        member_uids = {profile.uid for profile in profiles}
        if registry.active_uid in member_uids:
            raise ProfileError(
                f"Study {study_name!r} contains the active Profile; select "
                "another Profile before removing it."
            )
        existing_removed = frozenset(registry.removed_profile_uids)
        stores_to_delete = tuple(
            profile
            for profile in profiles
            if profile_store_dir(profile).exists()
            or profile_store_dir(profile).is_symlink()
        )
        if not stores_to_delete:
            raise ProfileError(f"Study {study_name!r} is already removed.")
        for profile in stores_to_delete:
            inspect_store(
                profile_store_dir(profile),
                allowed_virtual_currents=_read_granted_access_names(
                    registry,
                    profile.uid,
                ),
            )
        removed = existing_removed | member_uids
        ordered_removed = tuple(
            profile.uid for profile in registry.profiles if profile.uid in removed
        )
        retained_grants = tuple(
            grant
            for grant in registry.grants
            if not member_uids.intersection(
                {grant.authority_profile_uid, grant.grantee_profile_uid}
            )
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=retained_grants,
            removed_profile_uids=ordered_removed,
            grant_placements=tuple(
                placement
                for placement in registry.grant_placements
                if placement.grant_uid in {grant.uid for grant in retained_grants}
            ),
        )
        batch = _prepare_profile_deletion_batch(stores_to_delete)
        _publish_permanent_removal(
            registry,
            updated,
            batch=batch,
            profiles=stores_to_delete,
            label=f"Study {study_name!r}",
        )
        return StudyRemovalResult(
            uid=study_uid,
            name=study_name,
            profiles=profiles,
            newly_removed_count=len(stores_to_delete),
            removed_grant_count=len(registry.grants) - len(retained_grants),
            deleted_stores=tuple(
                profile_store_dir(profile) for profile in stores_to_delete
            ),
            active_profile_name=registry.active.name,
        )
