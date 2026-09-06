"""Profile picker orchestration and reviewed action dispatch."""

from __future__ import annotations

from typing import Callable

import typer

from memcommit.adapters.console.commands.profile._support import _fail
from memcommit.adapters.console.commands.profile.inventory import (
    _profile_rows,
    _study_memberships,
)
from memcommit.adapters.console.commands.profile.lifecycle import _use_profile
from memcommit.adapters.console.commands.profile.picker import (
    ProfilePickerAction,
    ProfilePickerEntry,
    ProfilePickerRefresh,
    choose_profile,
)
from memcommit.adapters.console.commands.profile.presentation import (
    _print_profile_creation,
    _print_profile_removal,
    _print_profile_rename,
    _print_study_removal,
    _print_study_rename,
    _profile_creation_status,
    _profile_removal_status,
    _profile_rename_status,
    _study_removal_status,
    _study_rename_status,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.application.operations.profile.model.lifecycle import (
    create_profile,
    remove_profile,
    rename_profile,
)
from memcommit.application.operations.profile.model.study import (
    remove_study,
    rename_study,
)


def _pick_profile(
    *,
    initial_status: str = "",
    initial_row_index: int | None = None,
    apply_removal: Callable[[ProfilePickerAction], str] | None = None,
) -> ProfilePickerAction | ProfilePickerRefresh | None:
    registry, inspections = _profile_rows()
    memberships = _study_memberships(registry)
    entries = tuple(
        ProfilePickerEntry(
            name=profile.name,
            context_count=len(inspection.context_names),
            memory_count=inspection.ordinary_memory_count,
            current_context=inspection.current_context,
            granted_context_count=inspection.granted_context_count,
            granted_memory_count=inspection.granted_memory_count,
            query_source_count=inspection.query_source_count,
            query_source_names=inspection.query_source_names,
            uid=profile.uid,
            study_uid=(
                memberships[profile.uid].uid if profile.uid in memberships else None
            ),
            study_name=(
                memberships[profile.uid].name if profile.uid in memberships else None
            ),
            study_created_at=(
                memberships[profile.uid].created_at
                if profile.uid in memberships
                else None
            ),
            study_task=(
                memberships[profile.uid].task if profile.uid in memberships else None
            ),
            study_role=(
                memberships[profile.uid].role if profile.uid in memberships else None
            ),
            study_profile_count=(
                memberships[profile.uid].profile_count
                if profile.uid in memberships
                else 0
            ),
            study_removed_count=(
                memberships[profile.uid].removed_count
                if profile.uid in memberships
                else 0
            ),
            removal_block=(
                "The fixed authoring Profile cannot be removed"
                if profile.kind == "AUTHORING"
                else None
            ),
            rename_block=(
                "The fixed authoring Profile cannot be renamed"
                if profile.kind == "AUTHORING"
                else (
                    "Legacy Study members cannot be renamed individually"
                    if profile.uid in memberships
                    and memberships[profile.uid].task is not None
                    else None
                )
            ),
        )
        for profile, inspection in zip(
            registry.visible_profiles,
            inspections,
            strict=True,
        )
    )
    try:
        picker_kwargs = {"initial_status": initial_status} if initial_status else {}
        if apply_removal is not None:
            picker_kwargs["apply_removal"] = apply_removal
        if initial_row_index is not None:
            picker_kwargs["initial_row_index"] = initial_row_index
        selected = choose_profile(
            entries,
            current=registry.active.name,
            registry_generation=registry.generation,
            **picker_kwargs,
        )
        # Compatibility for narrow tests and callers that supplied the former
        # name-only picker result while the typed action contract rolled out.
        if isinstance(selected, str):
            target = registry.by_name(selected)
            return ProfilePickerAction(
                kind="USE",
                name=selected,
                uid=target.uid if target is not None else None,
                registry_generation=registry.generation,
            )
        return selected
    except ValueError as error:
        _fail(ProfileError(str(error)))


def _apply_profile_picker_action(
    action: ProfilePickerAction,
    *,
    print_receipt: bool = True,
    propagate_errors: bool = False,
) -> str | None:
    if action.kind == "USE":
        _use_profile(action.name)
        return None
    try:
        if action.kind == "CREATE_PROFILE":
            result = create_profile(
                action.name,
                expected_generation=action.registry_generation,
            )
        elif action.kind == "RENAME_PROFILE":
            if action.new_name is None:
                raise ProfileError("Profile picker rename is missing its new name.")
            result = rename_profile(
                action.new_name,
                old_name=action.name,
                expected_uid=action.uid,
                expected_generation=action.registry_generation,
            )
        elif action.kind == "RENAME_STUDY":
            if action.new_name is None:
                raise ProfileError(
                    "Profile picker Study rename is missing its new name."
                )
            result = rename_study(
                action.name,
                action.new_name,
                expected_uid=action.uid,
                expected_generation=action.registry_generation,
            )
        elif action.kind == "REMOVE_PROFILE":
            result = remove_profile(
                action.name,
                expected_uid=action.uid,
                expected_generation=action.registry_generation,
            )
        else:
            result = remove_study(
                action.name,
                expected_uid=action.uid,
                expected_generation=action.registry_generation,
            )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        if propagate_errors:
            raise
        _fail(error)
    if action.kind == "CREATE_PROFILE":
        if print_receipt:
            _print_profile_creation(result)
        return _profile_creation_status(result)
    if action.kind == "RENAME_PROFILE":
        if print_receipt:
            _print_profile_rename(result)
        return _profile_rename_status(result)
    if action.kind == "RENAME_STUDY":
        if print_receipt:
            _print_study_rename(result)
        return _study_rename_status(result)
    if action.kind == "REMOVE_PROFILE":
        if print_receipt:
            _print_profile_removal(result)
        return _profile_removal_status(result)
    if print_receipt:
        _print_study_removal(result)
    return _study_removal_status(result)


def _run_profile_selector() -> None:
    """Keep the selector open after mutations and reload its frozen catalog."""

    status = ""
    preferred_row_index: int | None = None
    completed_mutation = False
    while True:
        action = _pick_profile(
            initial_status=status,
            initial_row_index=preferred_row_index,
            apply_removal=lambda reviewed: (
                _apply_profile_picker_action(
                    reviewed,
                    print_receipt=False,
                    propagate_errors=True,
                )
                or "Profile deletion completed"
            ),
        )
        if action is None:
            if not completed_mutation:
                typer.echo("Profile selection cancelled.")
            return
        if isinstance(action, ProfilePickerRefresh):
            if action.error is not None:
                _fail(action.error)
            status = action.status
            preferred_row_index = action.preferred_row_index
            completed_mutation = True
            if action.close_requested:
                return
            continue
        if action.kind == "USE":
            _apply_profile_picker_action(action)
            return
        # A completed destructive action must never reuse the catalog or
        # registry generation that was frozen for its review. Re-entering the
        # picker reloads both while keeping the person in the selector flow.
        status = (
            _apply_profile_picker_action(
                action,
                print_receipt=False,
                propagate_errors=False,
            )
            or "Profile mutation completed"
        )
        preferred_row_index = action.row_index
        completed_mutation = True
