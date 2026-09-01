"""Encode and decode Forget's exact interactive command form."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.console.terminal.components.command_editor import (
    CommandForm,
    CommandFormField,
    CommandReview,
)


FORGET_COMMAND_FORM = CommandForm(
    command=("mem", "forget"),
    usage="mem forget INSTRUCTION --from SOURCE",
    fields=(
        CommandFormField("INSTRUCTION", "one process-local Forget criterion"),
        CommandFormField(
            "--from SOURCE",
            "one exact readable direct Source Context",
        ),
    ),
)


def parse_forget_command_argv(argv: Sequence[str]) -> tuple[str, str]:
    """Return ``(source, instruction)`` from the interactive command subset."""

    values = tuple(argv)
    if values[:2] != ("mem", "forget"):
        raise ValueError("Editable Forget commands must start with 'mem forget'.")
    instruction: str | None = None
    source: str | None = None
    index = 2
    while index < len(values):
        token = values[index]
        if token in {"--from", "--context", "-c"}:
            if source is not None or index + 1 >= len(values):
                raise ValueError("Forget accepts exactly one --from SOURCE.")
            source = values[index + 1]
            index += 2
            continue
        if token.startswith("-"):
            raise ValueError(f"Editable Forget does not accept {token}.")
        if instruction is not None:
            raise ValueError(
                "Editable Forget requires one quoted INSTRUCTION and --from SOURCE."
            )
        instruction = token
        index += 1
    if instruction is None or not instruction.strip() or source is None or not source:
        raise ValueError(
            "Editable Forget requires one quoted INSTRUCTION and --from SOURCE."
        )
    return source, instruction.strip()


def build_forget_review(*, source_name: str, instruction: str) -> CommandReview:
    """Project one complete setup as the exact command that starts Forget."""

    if not isinstance(source_name, str) or not source_name:
        raise ValueError("Forget requires one direct Source Context.")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError("Forget requires one nonblank instruction.")
    return CommandReview(
        ("mem", "forget", instruction.strip(), "--from", source_name),
        (
            "Analyze the complete direct Source with one process-local instruction.",
            "Do not change the Source until the reviewed result is applied.",
        ),
    )


__all__ = [
    "FORGET_COMMAND_FORM",
    "build_forget_review",
    "parse_forget_command_argv",
]
