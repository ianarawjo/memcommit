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
            "Remove every Grant connected to those Profiles.",
            "This cannot be undone or recovered by mem.",
        )
        command = "remove-study"
    else:
        entry = row.entry
        assert entry is not None
        effects_list = [
            f"Permanently delete only Profile {row.name!r} and its store.",
            "Delete every Memory, session, and checkpoint in that store.",
            "Remove every Grant connected to this Profile.",
            "This cannot be undone or recovered by mem.",
        ]
        if entry.study_name is not None:
            effects_list.append(
                f"Keep Study {entry.study_name!r} and its other Profile rows."
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
                "Keep both member Profile display names unchanged.",
                "Keep the same Study UID, Profile UIDs, stores, Contexts, Memories, and Grants.",
                "Keep the same active Profile selected.",
            ),
        )
    return CommandReview(
        argv=("mem", "profile", "rename", action.name, action.new_name),
        effects=(
            f"Change Profile {action.name!r}'s display name to {action.new_name!r}.",
            "Keep the same Profile UID, store directory, Contexts, Memories, and Grants.",
            "Keep the same active Profile selected when this Profile is current.",
        ),
    )


def creation_review(action: ProfilePickerAction) -> CommandReview:
    """Render the exact empty-Profile publication selected in the picker."""

    if action.kind != "CREATE_PROFILE":
        raise ValueError("Profile creation review requires an exact new name.")
    return CommandReview(
        argv=("mem", "profile", "create", action.name),
        effects=(
            f"Create empty managed Profile {action.name!r} with a fresh UID.",
            "Create a private store with no Contexts, Memories, Grants, or history.",
            "Keep the current Profile selected.",
            "Select the new Profile separately, then run mem init CONTEXT.",
        ),
    )
