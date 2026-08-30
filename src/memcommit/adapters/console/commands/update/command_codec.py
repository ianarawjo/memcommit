"""Encode and decode Update's exact public command forms."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.console.terminal.components.command_editor import (
    CommandForm,
    CommandFormField,
    CommandReview,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.model import (
    EndpointSetupDraft,
    EndpointSetupValue,
)


UPDATE_COMMAND_FORM = CommandForm(
    command=("mem", "update"),
    usage=(
        "mem update --from SOURCE --to TARGET [--source-descendants] "
        "[--target-descendants] [--source-memory UID] [--target-memory UID]"
    ),
    fields=(
        CommandFormField("--from SOURCE", "the exact readable Source Context"),
        CommandFormField("--to TARGET", "the exact mutable Target Context"),
        CommandFormField(
            "--source-descendants / --target-descendants",
            "independent lexical endpoint ranges",
        ),
        CommandFormField(
            "--source-memory / --target-memory UID",
            "an optional exact direct Memory at either endpoint",
        ),
    ),
)


def parse_endpoint_argv(argv: Sequence[str]) -> EndpointSetupDraft:
    """Decode the endpoint-setup subset without invoking a nested CLI."""

    values = tuple(argv)
    if values[:2] != ("mem", "update"):
        raise ValueError("Editable Update commands must start with 'mem update'.")
    options: dict[str, str] = {}
    switches: set[str] = set()
    value_options = {"--from", "--to", "--source-memory", "--target-memory"}
    switch_options = {"--source-descendants", "--target-descendants"}
    index = 2
    while index < len(values):
        token = values[index]
        if token in value_options:
            if token in options or index + 1 >= len(values):
                raise ValueError(f"Update {token} requires exactly one value.")
            options[token] = values[index + 1]
            index += 2
            continue
        if token in switch_options:
            if token in switches:
                raise ValueError(f"Update {token} may appear only once.")
            switches.add(token)
            index += 1
            continue
        raise ValueError(f"Editable Update does not accept {token}.")
    if "--from" not in options or "--to" not in options:
        raise ValueError("Editable Update requires --from SOURCE and --to TARGET.")
    return EndpointSetupDraft(
        "UPDATE",
        (
            EndpointSetupValue(
                "A",
                options["--from"],
                include_descendants="--source-descendants" in switches,
                memory_uid=options.get("--source-memory"),
            ),
            EndpointSetupValue(
                "B",
                options["--to"],
                include_descendants="--target-descendants" in switches,
                memory_uid=options.get("--target-memory"),
            ),
        ),
    )


def build_start_review(
    *,
    source_name: str,
    target_name: str,
    source_descendants: bool = False,
    target_descendants: bool = False,
    source_memory_uid: str | None = None,
    target_memory_uid: str | None = None,
    inline_source_content: str | None = None,
) -> CommandReview:
    if inline_source_content is not None:
        if source_descendants or source_memory_uid is not None:
            raise ValueError(
                "Inline Update input cannot use Source descendants or focus."
            )
        argv = [
            "mem",
            "update",
            "--memory",
            inline_source_content,
            "--to",
            target_name,
        ]
    else:
        argv = ["mem", "update", "--from", source_name, "--to", target_name]
    if source_descendants:
        argv.append("--source-descendants")
    if target_descendants:
        argv.append("--target-descendants")
    if source_memory_uid is not None:
        argv.extend(("--source-memory", source_memory_uid))
    if target_memory_uid is not None:
        argv.extend(("--target-memory", target_memory_uid))
    return CommandReview(
        tuple(argv),
        (
            "Start or resume the exact Update plan and saved review session shown.",
            "Do not apply target changes; final Apply remains separate.",
        ),
    )


def build_turn_review(
    *,
    source_name: str,
    target_name: str,
    source_descendants: bool,
    target_descendants: bool,
    source_memory_uid: str | None,
    target_memory_uid: str | None,
    comment: str,
    expected_session: str,
    inline_source_content: str | None = None,
) -> CommandReview:
    start = build_start_review(
        source_name=source_name,
        target_name=target_name,
        source_descendants=source_descendants,
        target_descendants=target_descendants,
        source_memory_uid=source_memory_uid,
        target_memory_uid=target_memory_uid,
        inline_source_content=inline_source_content,
    )
    return CommandReview(
        (*start.argv, "--comment", comment, "--expect-session", expected_session),
        (
            "Submit one semantic Update revision against the exact displayed session.",
            "Replace the staged plan; do not apply target changes.",
        ),
    )


__all__ = [
    "UPDATE_COMMAND_FORM",
    "build_start_review",
    "build_turn_review",
    "parse_endpoint_argv",
]
