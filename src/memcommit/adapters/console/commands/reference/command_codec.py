"""Encode and decode Reference's exact interactive Memory command."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.console.terminal.components.command_editor import (
    CommandForm,
    CommandFormField,
    CommandReview,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointSetupDraft,
    EndpointSetupValue,
)


REFERENCE_COMMAND_FORM = CommandForm(
    command=("mem", "reference"),
    usage="mem reference MEMORY --from SOURCE_CONTEXT --into TARGET_CONTEXT",
    fields=(
        CommandFormField("MEMORY", "one exact directly owned Memory UID or prefix"),
        CommandFormField("--from SOURCE_CONTEXT", "the Memory's exact readable owner"),
        CommandFormField("--into TARGET_CONTEXT", "one existing local Target Context"),
    ),
)


def parse_endpoint_argv(argv: Sequence[str]) -> EndpointSetupDraft:
    """Decode the complete exact-Memory Reference form without nested CLI work."""

    values = tuple(argv)
    if values[:2] != ("mem", "reference"):
        raise ValueError("Editable Reference commands must start with 'mem reference'.")

    memory_selector: str | None = None
    options: dict[str, str] = {}
    index = 2
    while index < len(values):
        token = values[index]
        if token in {"--from", "--into"}:
            if token in options or index + 1 >= len(values):
                raise ValueError(f"Reference {token} requires exactly one value.")
            options[token] = values[index + 1]
            index += 2
            continue
        if token.startswith("-"):
            raise ValueError(f"Editable Reference does not accept {token}.")
        if memory_selector is not None:
            raise ValueError("Editable Reference requires exactly one Memory selector.")
        memory_selector = token
        index += 1

    if memory_selector is None:
        raise ValueError("Editable Reference requires one exact Memory selector.")
    if "--from" not in options or "--into" not in options:
        raise ValueError("Editable Reference requires both --from and --into.")
    return EndpointSetupDraft(
        "REFERENCE",
        (
            EndpointSetupValue("TARGET", options["--into"]),
            EndpointSetupValue(
                "SOURCE",
                options["--from"],
                memory_uid=memory_selector,
            ),
        ),
    )


def build_review(draft: EndpointSetupDraft) -> CommandReview:
    """Project one exact Reference draft into its runnable public command."""

    if draft.mode_uid != "REFERENCE":
        raise ValueError("Reference setup requires the exact-Memory shape.")
    target = draft.value("TARGET")
    source = draft.value("SOURCE")
    if source.memory_uid is None:
        raise ValueError("SOURCE MEMORY requires one directly owned Memory.")
    if target.create or source.create:
        raise ValueError(
            "Reference setup requires existing Source and Target Contexts."
        )
    return CommandReview(
        argv=(
            "mem",
            "reference",
            source.memory_uid,
            "--from",
            source.context_name,
            "--into",
            target.context_name,
        ),
        effects=(
            f"Only Context '{target.context_name}' changes.",
            (
                f"Memory [{source.memory_uid[:8]}] remains owned by "
                f"'{source.context_name}'; the Target retains this exact version."
            ),
            "The new snapshot is read-only and does not follow later Source edits.",
        ),
    )


__all__ = ["REFERENCE_COMMAND_FORM", "build_review", "parse_endpoint_argv"]
