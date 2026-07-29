"""Entry point for the `mem` CLI."""
from typing import Annotated

import typer

from memcommit.commands import (
    add,
    atomize,
    branch,
    checkpoint,
    chunk,
    contexts,
    delete,
    diff,
    edit,
    embed,
    find,
    find_ambiguities,
    find_conflicts,
    find_duplicates,
    forget,
    impact,
    init,
    integrate,
    list_memories,
    log,
    show,
    merge,
    query,
    rationale,
    reference,
    remove,
    review,
    revert,
    status,
    switch,
    trace,
    update,
)
from memcommit.commands.clear import cmd as clear_cmd
from memcommit.commands.config import app as config_app
from memcommit.commands.dev import app as dev_app

app = typer.Typer(no_args_is_help=True, help="mem — a git-like memory store")

# --- Core ---
app.command("init",           help="Initialize a new context and switch to it.")(init.cmd)
app.command("add",            help="Add one or more memories to the current context.")(add.cmd)
app.command("status",         help="Show current context and recent memories.")(status.cmd)
app.command("list",           help="List direct items in the current (or given) context.")(list_memories.cmd)
app.command("ls",             help="Alias for 'list'.")(list_memories.cmd)
app.command("show",           help="Show a memory, embedded context, or the current context in full.")(show.cmd)
app.command("contexts",       help="List all available contexts.")(contexts.cmd)
app.command("clear",          help="Clear all memories from the current (or given) context.")(clear_cmd)
app.command("delete",         help="Delete a context and its history; preserve descendants.")(delete.cmd)
app.command("diff",           help="Show the active staged update.")(diff.cmd)

# --- Navigation ---
app.command("switch",         help="Switch to a different context.")(switch.cmd)
app.command("branch",         help="Create a new context branched from the current one.")(branch.cmd)
app.command("merge",          help="Merge another context into the current one.")(merge.cmd)
app.command("embed",          help="Embed one context inside another.")(embed.cmd)
app.command("reference",      help="Add a read-only live reference to a memory.")(reference.cmd)
app.command("query",          help="Ask a question of a query-only Context.")(query.cmd)

# --- Editing ---
app.command("edit",           help="Replace the content of one or more direct Memories by uid.")(edit.cmd)
app.command("remove",         help="Remove a direct item from the current context by uid.")(remove.cmd)
app.command("chunk",          help="Split a memory into chunks (markdown_headers, paragraphs, sentences).")(chunk.cmd)
app.command(
    "atomize",
    help="Inspect or explicitly apply the latest saved atomize analysis.",
)(atomize.cmd)
app.command("checkpoint",     help="Save a manual checkpoint of the current context state.")(checkpoint.cmd)
app.command("revert",         help="Revert the current context to a previous checkpoint.")(revert.cmd)
app.command("log",            help="List checkpoints (history) for the current context.")(log.cmd)
app.command(
    "trace",
    help="Trace one current or historical Memory from retained origin to current descendants.",
)(trace.cmd)
app.command(
    "rationale",
    help="Explain a Memory from recorded evidence and labeled inference within its current Context.",
)(rationale.cmd)

# --- Semantic (legacy configured LLM or isolated Codex provider) ---
app.command("forget",         help="Forget memories matching a description (uses LLM).")(forget.cmd)
app.command("find",           help="Find relevant items with temporary Codex ranking.")(find.cmd)
app.command("find-duplicates", help="Find duplicate direct Memories.")(find_duplicates.cmd)
app.command("find-ambiguities", help="Find ambiguous or underspecified direct Memories.")(find_ambiguities.cmd)
app.command("find-conflicts", help="Find conflicting direct Memory pairs.")(find_conflicts.cmd)
app.command(
    "review",
    help="Create or resume a staged terminal review of semantic findings.",
)(review.cmd)
app.command(
    "impact",
    help="Preview a directional update or unary semantic operation.",
)(impact.cmd)
app.command("integrate",      help="Intelligently integrate info into the current context (uses LLM).")(integrate.cmd)
app.command("update",         help="Stage changes from the current Context to a target.")(update.cmd)

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
