"""Encode and decode Sever's exact public command forms."""

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


SEVER_COMMAND_FORM = CommandForm(
    command=("mem", "sever"),
    usage=(
        "mem sever SOURCE CRITERIA [--source-descendants] " "[--criteria-descendants]"
    ),
    fields=(
        CommandFormField("SOURCE CRITERIA", "the two exact readable inputs"),
        CommandFormField(
            "--source-descendants / --criteria-descendants",
            "independent lexical input ranges",
        ),
    ),
)


def parse_endpoint_argv(argv: Sequence[str]) -> EndpointSetupDraft:
    """Decode the endpoint-setup subset without invoking a nested CLI."""

    values = tuple(argv)
    if values[:2] != ("mem", "sever"):
        raise ValueError("Editable Sever commands must start with 'mem sever'.")
    positionals: list[str] = []
    switches: set[str] = set()
    allowed = {"--source-descendants", "--criteria-descendants"}
    for token in values[2:]:
        if token in allowed:
            if token in switches:
                raise ValueError(f"Sever {token} may appear only once.")
            switches.add(token)
        elif token.startswith("-"):
            raise ValueError(f"Editable Sever does not accept {token}.")
        else:
            positionals.append(token)
    if len(positionals) != 2:
        raise ValueError("Editable Sever requires exactly SOURCE and CRITERIA.")
    source, criteria = positionals
    return EndpointSetupDraft(
        "SEVER",
        (
            EndpointSetupValue(
                "SOURCE",
                source,
                include_descendants="--source-descendants" in switches,
            ),
            EndpointSetupValue(
                "CRITERIA",
                criteria,
                include_descendants="--criteria-descendants" in switches,
            ),
        ),
    )


def build_start_review(
    *,
    source_name: str,
    criteria_name: str,
    source_descendants: bool = False,
    criteria_descendants: bool = False,
) -> CommandReview:
    argv = ["mem", "sever", source_name, criteria_name]
    if source_descendants:
        argv.append("--source-descendants")
    if criteria_descendants:
        argv.append("--criteria-descendants")
    return CommandReview(
        tuple(argv),
        (
            "Start or resume the exact Sever analysis and saved review session shown.",
            "Do not change Source owners yet; final in-place Apply remains separate.",
        ),
    )


def build_turn_review(
    *,
    session_uid: str,
    candidate_uid: str,
    choice: str,
    expected_session: str,
    comment: str = "",
) -> CommandReview:
    argv = [
        "mem",
        "sever",
        "--resume",
        session_uid,
        "--candidate",
        candidate_uid,
        "--choice",
        choice,
    ]
    if comment:
        argv.extend(("--comment", comment))
    argv.extend(("--expect-session", expected_session))
    return CommandReview(
        tuple(argv),
        (
            "Save one Sever candidate decision against the exact displayed session revision.",
            "Do not update Source owners; final Apply remains separate.",
        ),
    )


__all__ = [
    "SEVER_COMMAND_FORM",
    "build_start_review",
    "build_turn_review",
    "parse_endpoint_argv",
]
