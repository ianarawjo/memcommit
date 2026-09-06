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
        "mem update (--from SOURCE | --memory TEXT) --to TARGET "
        "[--source-descendants] "
        "[--target-descendants] [--source-memory UID] [--target-memory UID]"
    ),
    fields=(
        CommandFormField(
            "--from SOURCE / --memory TEXT",
            "an exact readable Context or one process-local inline Memory",
        ),
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
    value_options = {
        "--from",
        "--memory",
        "--to",
        "--source-memory",
        "--target-memory",
    }
    switch_options = {"--source-descendants", "--target-descendants"}
    index = 2
    while index < len(values):
        token = values[index]
        # Normalize option tokens only: inline Memory text must stay verbatim.
        if token == "-m":
            token = "--memory"
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
    source_options = {"--from", "--memory"} & set(options)
    if len(source_options) != 1 or "--to" not in options:
        raise ValueError(
            "Editable Update requires exactly one of --from SOURCE or "
            "--memory TEXT, plus --to TARGET."
        )
    if "--memory" in options and (
        "--source-descendants" in switches or "--source-memory" in options
    ):
        raise ValueError(
            "Editable inline Update cannot use Source descendants or focus."
        )
    source = (
        EndpointSetupValue(
            "A",
            options["--from"],
            memory_uid=options.get("--source-memory"),
            include_descendants="--source-descendants" in switches,
        )
        if "--from" in options
        else EndpointSetupValue("A", "", inline_memory_content=options["--memory"])
    )
    return EndpointSetupDraft(
        "UPDATE",
        (
            source,
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
    source_name: str | None,
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
        if source_name is None:
            raise ValueError("Context Update input requires one Source Context.")
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


__all__ = [
    "UPDATE_COMMAND_FORM",
    "build_start_review",
    "parse_endpoint_argv",
]
