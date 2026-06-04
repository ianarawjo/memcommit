"""Entry point for the `mem` CLI."""
from typing import Annotated

import typer

from memcommit.commands import (
    add,
    checkpoint,
    checkpoints,
    contexts,
    embed,
    find,
    forget,
    init,
    remove,
    status,
    switch,
)

app = typer.Typer(no_args_is_help=True, help="mem — a git-like memory store")

app.command("init", help="Initialize a new context and switch to it.")(init.cmd)
app.command("add", help="Add a memory to the current context.")(add.cmd)
app.command("checkpoint", help="Save a checkpoint of the current context state.")(checkpoint.cmd)
app.command("checkpoints", help="List checkpoints for the current context.")(checkpoints.cmd)
app.command("switch", help="Switch to a different context.")(switch.cmd)
app.command("contexts", help="List all available contexts.")(contexts.cmd)
app.command("embed", help="Embed one context inside another.")(embed.cmd)
app.command("remove", help="Remove a memory from the current context by uid.")(remove.cmd)
app.command("status", help="Show current context and recent memories.")(status.cmd)
app.command("forget", help="[stub] Find and remove memories matching a description.")(forget.cmd)
app.command("find", help="[stub] Find memories matching a natural language query.")(find.cmd)


# checkout is an alias for switch
def _checkout(name: Annotated[str, typer.Argument(help="Name of the context to switch to")]) -> None:
    """Alias for 'switch'."""
    switch.cmd(name)


app.command("checkout", help="Switch to a different context (alias for 'switch').")(_checkout)

if __name__ == "__main__":
    app()
