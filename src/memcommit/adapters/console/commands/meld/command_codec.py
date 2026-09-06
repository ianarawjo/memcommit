"""Encode and decode Meld's exact public command forms."""

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


MELD_COMMAND_FORM = CommandForm(
    command=("mem", "meld"),
    usage=(
        "mem meld (LEFT RIGHT | --memory TEXT --into BASELINE) [--to TARGET] "
        "[--left-descendants] [--right-descendants] "
        "[--incoming-memory UID] [--baseline-memory UID]"
    ),
    fields=(
        CommandFormField(
            "LEFT RIGHT / --memory TEXT --into BASELINE",
            "Context or inline-Memory directional input",
        ),
        CommandFormField("--to TARGET", "a separate symmetric Result Context"),
        CommandFormField(
            "--left-descendants / --right-descendants",
            "independent lexical Source ranges",
        ),
        CommandFormField(
            "--incoming-memory / --baseline-memory UID",
            "an optional exact direct Memory in directional mode",
        ),
    ),
)


def parse_endpoint_argv(argv: Sequence[str]) -> EndpointSetupDraft:
    """Decode the endpoint-setup subset without invoking a nested CLI."""

    values = tuple(argv)
    if values[:2] != ("mem", "meld"):
        raise ValueError("Editable Meld commands must start with 'mem meld'.")
    positionals: list[str] = []
    options: dict[str, str] = {}
    switches: set[str] = set()
    value_options = {
        "--to",
        "--into",
        "--memory",
        "--incoming-memory",
        "--baseline-memory",
    }
    switch_options = {"--left-descendants", "--right-descendants"}
    index = 2
    while index < len(values):
        token = values[index]
        # Normalize option tokens only: inline Memory text must stay verbatim.
        if token == "-m":
            token = "--memory"
        if token in value_options:
            if token in options or index + 1 >= len(values):
                raise ValueError(f"Meld {token} requires exactly one value.")
            options[token] = values[index + 1]
            index += 2
            continue
        if token in switch_options:
            if token in switches:
                raise ValueError(f"Meld {token} may appear only once.")
            switches.add(token)
            index += 1
            continue
        if token.startswith("-"):
            raise ValueError(f"Editable Meld does not accept {token}.")
        positionals.append(token)
        index += 1
    if "--memory" in options:
        if positionals or "--into" not in options or "--to" in options:
            raise ValueError(
                "Editable inline Meld requires --memory TEXT --into BASELINE."
            )
        if "--left-descendants" in switches or "--incoming-memory" in options:
            raise ValueError(
                "Editable inline Meld cannot use INCOMING descendants or focus."
            )
        return EndpointSetupDraft(
            "DIRECTIONAL",
            (
                EndpointSetupValue("A", "", inline_memory_content=options["--memory"]),
                EndpointSetupValue(
                    "B",
                    options["--into"],
                    include_descendants="--right-descendants" in switches,
                    memory_uid=options.get("--baseline-memory"),
                ),
            ),
        )
    if "--into" in options:
        raise ValueError("Editable Context Meld does not use --into.")
    if len(positionals) != 2:
        raise ValueError("Editable Meld requires exactly LEFT and RIGHT Contexts.")
    left, right = positionals
    target = options.get("--to")
    mode = "SYMMETRIC" if target is not None else "DIRECTIONAL"
    endpoints = [
        EndpointSetupValue(
            "A",
            left,
            include_descendants="--left-descendants" in switches,
            memory_uid=options.get("--incoming-memory"),
        ),
        EndpointSetupValue(
            "B",
            right,
            include_descendants="--right-descendants" in switches,
            memory_uid=options.get("--baseline-memory"),
        ),
    ]
    if target is not None:
        endpoints.append(EndpointSetupValue("C", target))
    return EndpointSetupDraft(mode, tuple(endpoints))


def build_start_review(
    *,
    mode: str,
    left_name: str | None,
    right_name: str,
    target_name: str | None = None,
    left_descendants: bool = False,
    right_descendants: bool = False,
    left_memory_uid: str | None = None,
    right_memory_uid: str | None = None,
    incoming_text: str | None = None,
) -> CommandReview:
    if incoming_text is not None:
        if mode.upper() != "DIRECTIONAL":
            raise ValueError("Inline Memory input requires directional Meld.")
        if left_descendants or left_memory_uid is not None:
            raise ValueError(
                "Inline Memory input cannot use INCOMING descendants or focus."
            )
        argv = ["mem", "meld", "--memory", incoming_text, "--into", right_name]
    else:
        if left_name is None:
            raise ValueError("Context Meld input requires one Source Context.")
        argv = ["mem", "meld", left_name, right_name]
    if mode.upper() == "SYMMETRIC":
        if target_name is None:
            raise ValueError("Symmetric Meld requires a result Context.")
        argv.extend(("--to", target_name))
    elif mode.upper() != "DIRECTIONAL":
        raise ValueError("Unsupported Meld command mode.")
    if left_descendants:
        argv.append("--left-descendants")
    if right_descendants:
        argv.append("--right-descendants")
    if left_memory_uid is not None:
        argv.extend(("--incoming-memory", left_memory_uid))
    if right_memory_uid is not None:
        argv.extend(("--baseline-memory", right_memory_uid))
    return CommandReview(
        tuple(argv),
        (
            "Start or resume the exact Meld analysis and saved review session shown.",
            "Do not apply the Meld target; final Apply remains separate.",
        ),
    )


def build_turn_review(
    *,
    left_name: str,
    right_name: str,
    target_name: str | None,
    left_descendants: bool,
    right_descendants: bool,
    left_memory_uid: str | None,
    right_memory_uid: str | None,
    incoming_text: str | None = None,
    expected_session: str,
    issue_uid: str | None = None,
    option_number: int | None = None,
    comment: str = "",
    preserve_all: bool = False,
    defer_all: bool = False,
) -> CommandReview:
    start = build_start_review(
        mode="SYMMETRIC" if target_name is not None else "DIRECTIONAL",
        left_name=left_name,
        right_name=right_name,
        target_name=target_name,
        left_descendants=left_descendants,
        right_descendants=right_descendants,
        left_memory_uid=left_memory_uid,
        right_memory_uid=right_memory_uid,
        incoming_text=incoming_text,
    )
    argv = list(start.argv)
    if preserve_all:
        argv.append("--preserve-all")
    elif defer_all:
        argv.append("--defer-all")
    else:
        if issue_uid is not None:
            argv.extend(("--issue", issue_uid))
        if option_number is not None:
            argv.extend(("--choice", str(option_number)))
        if comment:
            argv.extend(("--comment", comment))
    argv.extend(("--expect-session", expected_session))
    return CommandReview(
        tuple(argv),
        (
            "Submit one semantic Meld turn against the exact displayed session revision.",
            "Rebuild the saved proposal; do not apply the target.",
        ),
    )


__all__ = [
    "MELD_COMMAND_FORM",
    "build_start_review",
    "build_turn_review",
    "parse_endpoint_argv",
]
