"""Entry point for the `mem` CLI."""
from typing import Annotated

import typer

from memcommit.commands import (
    add,
    branch,
    checkpoint,
    checkpoints,
    contexts,
    embed,
    find,
    find_conflicts,
    forget,
    init,
    integrate,
    merge,
    remove,
    status,
    switch,
)
from memcommit.commands.config import app as config_app
from memcommit.commands.dev import app as dev_app

app = typer.Typer(no_args_is_help=True, help="mem — a git-like memory store")

# --- Core ---
app.command("init",           help="Initialize a new context and switch to it.")(init.cmd)
app.command("add",            help="Add a memory to the current context.")(add.cmd)
app.command("status",         help="Show current context and recent memories.")(status.cmd)
app.command("contexts",       help="List all available contexts.")(contexts.cmd)

# --- Navigation ---
app.command("switch",         help="Switch to a different context.")(switch.cmd)
app.command("branch",         help="Create a new context branched from the current one.")(branch.cmd)
app.command("merge",          help="Merge another context into the current one.")(merge.cmd)
app.command("embed",          help="Embed one context inside another.")(embed.cmd)

# --- Editing ---
app.command("remove",         help="Remove a memory from the current context by uid.")(remove.cmd)
app.command("checkpoint",     help="Save a checkpoint of the current context state.")(checkpoint.cmd)
app.command("checkpoints",    help="List checkpoints for the current context.")(checkpoints.cmd)

# --- Semantic (require mem config set llm <model>) ---
app.command("forget",         help="Forget memories matching a description (uses LLM).")(forget.cmd)
app.command("find",           help="[stub] Find memories matching a natural language query.")(find.cmd)
app.command("find-conflicts", help="[stub] Find memories that conflict with given info.")(find_conflicts.cmd)
app.command("integrate",      help="[stub] Intelligently integrate info into the current context.")(integrate.cmd)

# --- Sub-apps ---
app.add_typer(config_app, name="config", help="Read and write global configuration.")
app.add_typer(dev_app,    name="dev",    help="Developer tools (eval, diagnostics).", hidden=True)


# checkout: alias for switch, with -b to branch instead
@app.command("checkout", help="Switch to a context; with -b, branch from the current one.")
def _checkout(
    name: Annotated[str, typer.Argument(help="Context to switch to, or name of new branch")],
    b: Annotated[bool, typer.Option("-b", "--branch", help="Create a new branch from the current context")] = False,
) -> None:
    """Alias for 'switch'; with -b, alias for 'branch'."""
    if b:
        branch.cmd(name)
    else:
        switch.cmd(name)


if __name__ == "__main__":
    app()
