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
    import_profile,
    init,
    init_study,
    integrate,
    list_memories,
    log,
    meld,
    show,
    merge,
    query,
    rationale,
    redo,
    reference,
    rename,
    remove,
    review,
    revert,
    share,
    sever,
    shell_init,
    status,
    summarize,
    switch,
    trace,
    translate,
    undo,
    update,
    write_protection,
)
from memcommit.commands.clear import cmd as clear_cmd
from memcommit.commands.config import app as config_app
from memcommit.commands.dev import app as dev_app
from memcommit.commands.semantic_eval import eval_app
from memcommit.commands.profile import app as profile_app
from memcommit.commands.provider import app as provider_app
from memcommit.commands.root_group import MemCommandGroup

app = typer.Typer(
    cls=MemCommandGroup,
    no_args_is_help=True,
    help="mem — a git-like memory store",
)

# --- Core ---
app.command("init",           help="Initialize a new context and switch to it.")(init.cmd)
app.command(
    "import",
    help="Import a Profile, Context tree, or Memory while preserving identity.",
)(import_profile.cmd)
app.command(
    "init-study",
    help="Copy one Study baseline into a complete ordinary Profile.",
)(init_study.cmd)
app.command("add",            help="Add one or more memories to the current context.")(add.cmd)
app.command("status",         help="Show current context and recent memories.")(status.cmd)
app.command(
    "summarize",
    help=(
        "Show what Mem understands from a Context's visible ordinary Memories."
    ),
)(summarize.cmd)
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
app.add_typer(
    write_protection.lock_app,
    name="lock",
    help="Lock the current Context, a recursive Context set, Memory, or Profile.",
)
app.add_typer(
    write_protection.unlock_app,
    name="unlock",
    help="Unlock the current Context, a recursive set, Memory, or Profile.",
)
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
        "Browse saved comparisons with no target, or compare the active "
        "Context with an equal-authority PEER; save no target changes."
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
        "Browse saved Meld work with no operands, combine two equal-authority "
        "Contexts into the current empty Context, or directionally use "
        "INCOMING --into BASELINE; --from INCOMING uses the current BASELINE."
    ),
)(meld.cmd)
app.command("embed",          help="Embed one context inside another.")(embed.cmd)
app.command("reference",      help="Add a read-only live reference to a memory.")(reference.cmd)
app.command(
    "query",
    help=(
        "Ask visible Context knowledge or a concealed query-only view; explicit "
        "query-only sessions retain only visible Q/A when permitted."
    ),
)(query.cmd)

# --- Editing ---
app.command("edit",           help="Replace the content of one or more direct Memories by uid.")(edit.cmd)
app.command("remove",         help="Remove a direct item from the current context by uid.")(remove.cmd)
app.command("chunk",          help="Split a memory into chunks (markdown_headers, paragraphs, sentences).")(chunk.cmd)
app.command(
    "atomize",
    help=(
        "Create or resume atomization; --evaluate runs its issue-scoped "
        "directional meld, changes require explicit acceptance, and "
        "--sessions browses saved work."
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
app.command(
    "undo",
    help="Undo the most recent recorded Context command across its affected Contexts.",
)(undo.cmd)
app.command(
    "redo",
    help="Redo the most recently undone recorded Context command.",
)(redo.cmd)
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
    help=(
        "Open adaptive operation reports or stage semantic review responses; "
        "never apply Memories."
    ),
)(review.cmd)
app.command(
    "sever",
    help=(
        "Browse saved Sever work with no operands, or review one Source root "
        "against one scoped Criteria root and create a local result that "
        "forgets selected content while leaving Source unchanged."
    ),
)(sever.cmd)
app.command(
    "share",
    help=(
        "Deliver one unchanged applied Sever output through a grant-backed "
        "receiver endpoint."
    ),
)(share.cmd)
app.command(
    "ground",
    help=(
        "Browse saved Grounds or revise one Goal–Rules–Memories workbench; "
        "use N in the picker to start a provider-backed chat."
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
app.add_typer(
    eval_app,
    name="eval",
    help="Run and inspect staged semantic evaluation campaigns.",
)
app.add_typer(config_app, name="config", help="Read and write global configuration.")
app.add_typer(
    provider_app,
    name="provider",
    help="Select and verify Codex, Ollama, or OpenRouter semantic execution.",
)
app.add_typer(
    profile_app,
    name="profile",
    help="Register and select complete local MemoryStore profiles.",
)
app.add_typer(dev_app,    name="dev",    help="Developer tools (eval, diagnostics).", hidden=True)


app.command(
    "help",
    help="Browse commands and open syntax help.",
)(help_inventory.cmd)
app.command(
    "shell-init",
    help="Print opt-in shell integration for interactive command prefill.",
)(shell_init.cmd)


# checkout: alias for switch, with -b to branch instead
@app.command(
    "checkout",
    help="Alias for switch; with -b, alias for branch.",
)
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
