"""Shared exact-name review for save-as materialization previews."""

from __future__ import annotations

from collections.abc import Callable

import typer

from memcommit.commands.resolution_workbench_shell import _boxed_lines
from memcommit.commands.tui_primitives import display_escape_text


def render_save_location(name: str, *, detail: str) -> None:
    """Render one neutral report card immediately before Apply."""

    for line in _boxed_lines(
        "SAVE LOCATION",
        f"{display_escape_text(name)}\n{detail}",
        width=72,
    ):
        typer.echo(f" {line}")


def review_save_location(
    name: str,
    *,
    validate: Callable[[str], None],
    apply_label: str,
) -> str | None:
    """Let a person edit one fresh Context name or approve/abort Apply."""

    # Validate before rendering or using the value as an interactive default;
    # display escaping alone must not turn an invalid CLI operand into a name.
    validate(name)
    current = name
    while True:
        typer.echo()
        render_save_location(
            current,
            detail="E edits this exact new Context name before Apply.",
        )
        typer.secho(
            f"  y = {apply_label}    e = edit save location    n = abort",
            dim=True,
        )
        decision = typer.prompt(">", default="", show_default=False).strip().lower()
        if decision in {"y", "yes"}:
            try:
                validate(current)
            except (OSError, TypeError, ValueError) as error:
                typer.secho(f"Save location error: {error}", fg=typer.colors.RED)
                continue
            return current
        if decision in {"n", "no"}:
            return None
        if decision not in {"e", "edit"}:
            continue
        candidate = typer.prompt(
            "SAVE LOCATION · EDIT DIRECTLY",
            default=current,
            show_default=True,
        ).strip()
        try:
            validate(candidate)
        except (OSError, TypeError, ValueError) as error:
            typer.secho(f"Save location error: {error}", fg=typer.colors.RED)
            continue
        current = candidate
