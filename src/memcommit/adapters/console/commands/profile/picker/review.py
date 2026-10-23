"""Exact command and effect projections; no mutation or terminal execution."""

from __future__ import annotations

from memcommit.adapters.console.commands.profile.picker.model import (
    ProfilePickerAction,
    ProfilePickerRow,
)
from memcommit.adapters.console.terminal.components.command_editor.model import (
    CommandReview,
)


def removal_action(
    row: ProfilePickerRow,
    *,
    registry_generation: int | None,
) -> ProfilePickerAction:
    return ProfilePickerAction(
        kind="REMOVE_STUDY" if row.kind == "STUDY" else "REMOVE_PROFILE",
        name=row.name,
        uid=row.uid,
        registry_generation=registry_generation,
    )


def removal_review(
    action: ProfilePickerAction,
    row: ProfilePickerRow,
) -> CommandReview:
    if action.kind == "REMOVE_STUDY":
        effects = (
            f"Permanently delete all {row.profile_count} Profile stores in "
            f"Study {row.name!r}.",
            "Delete every Memory, session, and checkpoint in those stores.",
            "Remove the Study and its Profiles from the registered list.",
            "Keep the project folders and their document files.",
            "This cannot be undone or recovered by mem.",
        )
        command = "remove-study"
    else:
        entry = row.entry
        assert entry is not None
        effects_list = [
            f"Permanently delete only Profile {row.name!r} and its store.",
            "Delete every Memory, session, and checkpoint in that store.",
            "Remove this Profile from the registered list.",
            "Keep the project folder and its document files.",
            "This cannot be undone or recovered by mem.",
        ]
        if entry.study_name is not None:
            effects_list.append(
                f"Keep Study {entry.study_name!r} and its remaining Profile."
                if entry.study_profile_count > 1
                else f"Remove the now-empty Study {entry.study_name!r} from the list."
            )
        effects = tuple(effects_list)
        command = "remove"
    return CommandReview(
        argv=("mem", "profile", command, action.name, "--force"),
        effects=effects,
    )


def rename_review(action: ProfilePickerAction) -> CommandReview:
    """Render the exact Profile or Study name mutation selected in the picker."""

    if action.kind not in {"RENAME_PROFILE", "RENAME_STUDY"} or action.new_name is None:
        raise ValueError("Rename review requires an exact new name.")
    if action.kind == "RENAME_STUDY":
        return CommandReview(
            argv=("mem", "profile", "rename-study", action.name, action.new_name),
            effects=(
                f"Change the Study display name from {action.name!r} to "
                f"{action.new_name!r}.",
                "Keep the member Profile display names unchanged.",
                "Keep the same Study UID, Profile UIDs, stores, Contexts, Memories.",
                "Keep the same active Profile selected.",
            ),
        )
    return CommandReview(
        argv=("mem", "profile", "rename", action.name, action.new_name),
        effects=(
            f"Change Profile {action.name!r}'s display name to {action.new_name!r}.",
            "Keep the same Profile UID, store directory, Contexts, Memories.",
            "Keep the same active Profile selected when this Profile is current.",
        ),
    )


def creation_review(action: ProfilePickerAction) -> CommandReview:
    """Render the exact project setup selected in the picker."""

    if action.kind != "CREATE_PROFILE":
        raise ValueError("Profile creation review requires an exact new name.")
    argv = ("mem", "profile", "create", action.name)
    if action.root_dir:
        argv += ("--root", action.root_dir)
    if action.import_project_files:
        argv += ("--import-files",)
    if action.select_created:
        argv += ("--use",)
    return CommandReview(
        argv=argv,
        effects=(
            f"Create managed Profile {action.name!r} with a fresh UID.",
            f"Project folder: {action.root_dir}"
            if action.root_dir
            else "Use the default project folder.",
            f"Import {action.imported_file_count} project documents recursively; exclude {action.skipped_file_count} unsupported or internal paths."
            if action.import_project_files
            else "Start with no Contexts or Memories.",
            "Keep existing project files unchanged during creation.",
            "Select the new Profile for subsequent mem commands."
            if action.select_created
            else "Keep the current Profile selected.",
        ),
    )
