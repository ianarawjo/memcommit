"""Entry point for the `mem` CLI."""
from typing import Annotated

import typer

from memcommit.commands import (
    add,
    atomize,
    branch,
    checkpoint,
    chunk,
    compare,
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
    ground,
    help_inventory,
    impact,
    init,
    integrate,
    list_memories,
    log,
    meld,
    show,
    merge,
    query,
    rationale,
    reference,
    rename,
    remove,
    review,
    revert,
    shell_init,
    status,
    switch,
    trace,
    translate,
    undo,
    update,
)
from memcommit.commands.clear import cmd as clear_cmd
from memcommit.commands.config import app as config_app
from memcommit.commands.dev import app as dev_app
from memcommit.commands.profile import app as profile_app

app = typer.Typer(no_args_is_help=True, help="mem — a git-like memory store")

# --- Core ---
app.command("init",           help="Initialize a new context and switch to it.")(init.cmd)
app.command("add",            help="Add one or more memories to the current context.")(add.cmd)
app.command("status",         help="Show current context and recent memories.")(status.cmd)
app.command(
    "list",
    help="List child Contexts and direct items in the current (or given) Context.",
)(list_memories.cmd)
app.command(
    "ls",
    help="List child Contexts and direct items in the current (or given) Context.",
)(list_memories.cmd)
app.command("show",           help="Show a memory, embedded context, or the current context in full.")(show.cmd)
app.command("contexts",       help="List all available contexts.")(contexts.cmd)
app.command("clear",          help="Clear all memories from the current (or given) context.")(clear_cmd)
app.command("delete",         help="Delete a context and its history; preserve descendants.")(delete.cmd)
app.command(
    "diff",
    help=(
        "Render the active staged or locally applied update; not an "
        "arbitrary Context diff."
    ),
)(diff.cmd)
app.command(
    "compare",
    help=(
        "Compare the active Context with an equal-authority PEER; save no "
        "target changes."
    ),
)(compare.cmd)

# --- Navigation ---
app.command("switch",         help="Switch to a different context.")(switch.cmd)
app.command(
    "rename",
    help="Rename an ordinary Context namespace and all lexical descendants.",
)(rename.cmd)
app.command("branch",         help="Create a new context branched from the current one.")(branch.cmd)
app.command(
    "merge",
    help="Add UID-new direct items from another Context; no semantic reconciliation.",
)(merge.cmd)
app.command(
    "meld",
    help=(
        "Interactively combine two equal-authority Contexts into the current "
        "empty Context, or meld INCOMING into an existing BASELINE with "
        "--into."
    ),
)(meld.cmd)
app.command("embed",          help="Embed one context inside another.")(embed.cmd)
app.command("reference",      help="Add a read-only live reference to a memory.")(reference.cmd)
app.command(
    "query",
    help="Ask a query-only Context; the question and answer are not saved.",
)(query.cmd)

# --- Editing ---
app.command("edit",           help="Replace the content of one or more direct Memories by uid.")(edit.cmd)
app.command("remove",         help="Remove a direct item from the current context by uid.")(remove.cmd)
app.command("chunk",          help="Split a memory into chunks (markdown_headers, paragraphs, sentences).")(chunk.cmd)
app.command(
    "atomize",
    help=(
        "Create or resume atomization; --evaluate runs its issue-scoped "
        "directional meld, with changes only after explicit acceptance."
    ),
)(atomize.cmd)
app.command("checkpoint",     help="Save a manual checkpoint of the current context state.")(checkpoint.cmd)
app.command(
    "revert",
    help="Restore an exact, interactively chosen, or semantically found checkpoint.",
)(revert.cmd)
app.command(
    "log",
    help="Inspect or semantically search checkpoint history for the current Context.",
)(log.cmd)
app.command("undo",           help="Restore the previous distinct Context state.")(undo.cmd)
app.command(
    "trace",
    help="Trace one current or historical Memory from retained origin to current descendants.",
)(trace.cmd)
app.command(
    "rationale",
    help="Show recorded evidence and optional labeled inference for a Memory.",
)(rationale.cmd)
app.command(
    "translate",
    help=(
        "Show and save a reusable translation view; materialize only when "
        "explicitly requested."
    ),
)(translate.cmd)

# --- Semantic (legacy configured LLM or isolated Codex provider) ---
app.command("forget",         help="Forget memories matching a description (uses LLM).")(forget.cmd)
app.command(
    "find",
    help="Find current items or explicitly temporal Memory history.",
)(find.cmd)
app.command("find-duplicates", help="Find duplicate direct Memories.")(find_duplicates.cmd)
app.command("find-ambiguities", help="Find ambiguous or underspecified direct Memories.")(find_ambiguities.cmd)
app.command("find-conflicts", help="Find conflicting direct Memory pairs.")(find_conflicts.cmd)
app.command(
    "review",
    help="Stage ambiguity or atomize-workbench responses without editing Memories.",
)(review.cmd)
app.command(
    "ground",
    help=(
        "Open or revise a Goal–Rules–Memories Ground; blank or plain named "
        "TTY use starts a provider-backed chat."
    ),
)(ground.cmd)
app.command(
    "impact",
    help="Preview a directional update or atomization; no Context changes.",
)(impact.cmd)
app.command("integrate",      help="Intelligently integrate info into the current context (uses LLM).")(integrate.cmd)
app.command(
    "update",
    help="Apply a directional plan to a local target; no shared publication.",
)(update.cmd)

# --- Sub-apps ---
app.add_typer(config_app, name="config", help="Read and write global configuration.")
app.add_typer(
    profile_app,
    name="profile",
    help="Register and select complete local MemoryStore profiles.",
)
app.add_typer(dev_app,    name="dev",    help="Developer tools (eval, diagnostics).", hidden=True)


app.command(
    "help",
    help="Browse commands with implementation levels and syntax help.",
)(help_inventory.cmd)
app.command(
    "shell-init",
    help="Print opt-in shell integration for interactive command prefill.",
)(shell_init.cmd)


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
