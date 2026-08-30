"""Encode and decode Branch's exact public command form."""

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


BRANCH_COMMAND_FORM = CommandForm(
    command=("mem", "branch"),
    usage=(
        "mem branch TARGET --from SOURCE "
        "(--source-descendants | --source-root-only)"
    ),
    fields=(
        CommandFormField("TARGET", "one exact new Branch Context"),
        CommandFormField("--from SOURCE", "one exact existing Source Context"),
        CommandFormField(
            "--source-descendants | --source-root-only",
            "the frozen lexical Source range",
        ),
    ),
)


def build_review(draft: EndpointSetupDraft) -> CommandReview:
    """Project one Branch setup draft to its canonical public command."""

    source = draft.value("A")
    target = draft.value("B")
    if not target.create:
        raise ValueError("TO must be one exact new Context name.")
    argv = (
        "mem",
        "branch",
        target.context_name,
        "--from",
        source.context_name,
        (
            "--source-descendants"
            if source.include_descendants
            else "--source-root-only"
        ),
    )
    scope = (
        "the frozen local Source root and lexical descendants"
        if source.include_descendants
        else "the frozen local Source root only"
    )
    return CommandReview(
        argv,
        (
            f"Create the exact new Branch target from {scope}.",
            "Switch the current Context to the new target root after publication.",
        ),
    )


def parse_endpoint_argv(argv: Sequence[str]) -> EndpointSetupDraft:
    """Decode the exact interactive Branch subset."""

    values = tuple(argv)
    if values[:2] != ("mem", "branch"):
        raise ValueError("Editable Branch commands must start with 'mem branch'.")
    if len(values) != 6:
        raise ValueError(
            "Editable Branch requires TARGET --from SOURCE and one Source range."
        )
    target, from_flag, source, range_flag = values[2:]
    if from_flag != "--from":
        raise ValueError("Editable Branch requires --from SOURCE.")
    if range_flag not in {"--source-descendants", "--source-root-only"}:
        raise ValueError(
            "Editable Branch requires --source-descendants or --source-root-only."
        )
    return EndpointSetupDraft(
        "BRANCH",
        (
            EndpointSetupValue(
                "A",
                source,
                include_descendants=range_flag == "--source-descendants",
            ),
            EndpointSetupValue("B", target, create=True),
        ),
    )


__all__ = ["BRANCH_COMMAND_FORM", "build_review", "parse_endpoint_argv"]
