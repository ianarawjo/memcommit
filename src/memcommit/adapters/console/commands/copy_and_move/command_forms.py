"""Explicit editable command forms for direct-Memory Copy and Move."""

from memcommit.adapters.console.terminal.components.command_editor.form import (
    CommandForm,
    CommandFormField,
)


COPY_COMMAND_FORM = CommandForm(
    command=("mem", "copy"),
    usage="mem copy MEMORY... --into TARGET [--before ITEM | --after ITEM]",
    fields=(
        CommandFormField(
            "MEMORY... | -m MEMORY...",
            "choose one or more direct Memory locators in transfer order",
        ),
        CommandFormField(
            "--from SOURCE",
            "apply one direct owner to every unqualified Memory selector",
        ),
        CommandFormField(
            "--into TARGET",
            "choose the one local Context whose direct order changes",
        ),
        CommandFormField(
            "--before ITEM | --after ITEM",
            "choose one adjacent direct-item gap; omit to append",
        ),
    ),
)


MOVE_COMMAND_FORM = CommandForm(
    command=("mem", "move"),
    usage=(
        "mem move MEMORY... --into TARGET [--before ITEM | --after ITEM] "
        "[--break-links]"
    ),
    fields=(
        CommandFormField(
            "MEMORY... | -m MEMORY...",
            "choose one or more directly owned Memories in transfer order",
        ),
        CommandFormField(
            "--from SOURCE",
            "apply one direct owner to every unqualified Memory selector",
        ),
        CommandFormField(
            "--into TARGET",
            "choose the new local direct owner",
        ),
        CommandFormField(
            "--before ITEM | --after ITEM",
            "choose one adjacent direct-item gap; omit to append",
        ),
        CommandFormField(
            "--break-links",
            "advanced opt-in: leave inbound live Memory Embeds dangling",
        ),
    ),
)


__all__ = ["COPY_COMMAND_FORM", "MOVE_COMMAND_FORM"]
