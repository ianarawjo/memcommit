"""Reserved console shell for the future Eval operation."""

from __future__ import annotations

import typer

from memcommit.adapters.console.coordination.command_group import CanonicalCommandGroup


RESERVED_EVAL_MESSAGE = (
    "Eval is reserved for a future evaluation workflow. "
    "No evaluation commands are currently available."
)


app = typer.Typer(
    cls=CanonicalCommandGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    help="Reserved shell for a future evaluation workflow.",
)


@app.callback(invoke_without_command=True)
def eval_shell(ctx: typer.Context) -> None:
    """Keep the public Eval route stable while its application is undefined."""

    if ctx.invoked_subcommand is None:
        typer.echo(RESERVED_EVAL_MESSAGE)


__all__ = ["RESERVED_EVAL_MESSAGE", "app", "eval_shell"]
