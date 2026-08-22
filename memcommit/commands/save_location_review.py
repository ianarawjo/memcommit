"""Shared exact-name review for save-as materialization previews."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import typer

from memcommit.commands.save_location_control import (
    SaveLocationView,
    save_location_card_lines,
)


def render_save_location(name: str, *, detail: str) -> None:
    """Render one neutral report card immediately before Apply."""

    location = SaveLocationView(
        value=name,
        state="CREATE ON APPLY",
        detail=detail,
    )
    for line in save_location_card_lines(location):
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
    location = SaveLocationView(
        value=name,
        state="CREATE ON APPLY",
        detail="E edits this exact new Context name before Apply.",
        validate=validate,
    )
    location.validate_value(name)
    while True:
        typer.echo()
        for line in save_location_card_lines(location):
            typer.echo(f" {line}")
        typer.secho(
            f"  y = {apply_label}    e = edit save location    n = abort",
            dim=True,
        )
        decision = typer.prompt(">", default="", show_default=False).strip().lower()
        if decision in {"y", "yes"}:
            try:
                location.validate_value(location.value)
            except (OSError, TypeError, ValueError) as error:
                typer.secho(f"Save location error: {error}", fg=typer.colors.RED)
                continue
            return location.value
        if decision in {"n", "no"}:
            return None
        if decision not in {"e", "edit"}:
            continue
        candidate = typer.prompt(
            "SAVE LOCATION · EDIT DIRECTLY",
            default=location.value,
            show_default=True,
        ).strip()
        try:
            location.validate_value(candidate)
        except (OSError, TypeError, ValueError) as error:
            typer.secho(f"Save location error: {error}", fg=typer.colors.RED)
            continue
        location = replace(location, value=candidate)
