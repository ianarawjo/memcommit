"""Print the application's completed Import result without rereading storage."""

import typer
from memcommit.adapters.console.terminal.core.text import display_escape_text as escape


def render_import_receipt(result):
    typer.echo(
        f"IMPORTED · {len(result.target_contexts)} Context(s) · {result.memory_count} Memory(s)"
    )
    typer.echo(
        "Contexts: " + ", ".join(escape(name) for name in result.target_contexts)
    )
    for path, kind, context in result.files:
        typer.echo(f"  {kind} · {escape(path)} → {escape(context)}")
    for issue in result.issues:
        typer.echo(
            f"  NOTICE [{escape(issue.code)}] · {escape(issue.path)}: {escape(issue.message)}"
        )
    typer.echo(f"Checkpoints: {len(result.checkpoints)}")


def render_import_error(error):
    typer.echo("Import failed: " + escape(str(error)), err=True)
