"""Print actual exported paths and validation notices."""

import typer
from memcommit.adapters.console.terminal.core.text import display_escape_text as escape
from memcommit.adapters.console.terminal.core.theme import (
    semantic_action_role,
    semantic_color_rgb,
)


def render_export_receipt(result):
    typer.echo(
        f"EXPORTED · {len(result.files)} file(s) → {escape(str(result.destination))}"
    )
    for path, attached in result.files:
        effect = next(
            (
                effect
                for effect in result.effects
                if str(result.destination / effect.path) == path
            ),
            None,
        )
        action = ""
        if effect:
            role = semantic_action_role(effect.action)
            action = (
                typer.style(effect.action, fg=semantic_color_rgb(role), bold=True)
                if role
                else effect.action
            ) + " · "
        typer.echo(
            f"  {action}{'ATTACHED' if attached else 'DOCUMENT'} · {escape(path)}"
        )
    for issue in result.issues:
        typer.echo(
            f"  NOTICE [{escape(issue.code)}] · {escape(issue.path)}: {escape(issue.message)}"
        )


def render_export_error(error):
    typer.echo("Export failed: " + escape(str(error)), err=True)
