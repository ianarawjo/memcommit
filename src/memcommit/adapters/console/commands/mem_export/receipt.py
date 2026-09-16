"""Print actual exported paths and validation notices."""

import typer
from memcommit.adapters.console.terminal.core.text import display_escape_text as escape


def render_export_receipt(result):
    typer.echo(
        f"EXPORTED · {len(result.files)} file(s) → {escape(str(result.destination))}"
    )
    for path, attached in result.files:
        typer.echo(f"  {'ATTACHED' if attached else 'DOCUMENT'} · {escape(path)}")
    for issue in result.issues:
        typer.echo(
            f"  NOTICE [{escape(issue.code)}] · {escape(issue.path)}: {escape(issue.message)}"
        )


def render_export_error(error):
    typer.echo("Export failed: " + escape(str(error)), err=True)
