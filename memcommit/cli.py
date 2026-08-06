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
app.command(
    "init",
    help="Create, or with --parents ensure, a Context and switch to it.",
)(init.cmd)
app.command(
    "import",
    help=(
        "Import a clean-baseline Profile, Context tree, or Memory by value "
        "while preserving resource identity."
    ),
)(import_profile.cmd)
app.command(
    "init-study",
    help="Copy one Study baseline into an isolated participant/authority Profile pair.",
)(init_study.cmd)
app.command(
    "add",
    help="Add one or more Memories to the current or explicit Context.",
)(add.cmd)
app.command(
    "status",
    help="Show current Context counts, recent Memories, and checkpoints.",
)(status.cmd)
app.command(
    "summarize",
    help=(
        "Show what Mem understands from a Context's visible ordinary Memories."
    ),
)(summarize.cmd)
app.command(
    "list",
    help=(
        "Enter the interactive Context browser for the current Context in a "
        "TTY, or print child Contexts and direct items."
    ),
)(list_memories.cmd)
app.command(
    "ls",
    help=(
        "Enter the interactive Context browser for the current Context in a "
        "TTY, or print child Contexts and direct items."
    ),
)(list_memories.cmd)
app.command(
    "show",
    help=(
        "Show a Memory, reference, embedded Context, or the direct contents "
        "of a current/explicit Context."
    ),
)(show.cmd)
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
app.command(
    "clear",
    help=(
        "Remove all direct items from the current or explicit Context after "
        "confirmation."
    ),
)(clear_cmd)
app.command(
    "delete",
    help=(
        "Select a Context or direct item to delete, or name it by locator, "
        "name, or UID."
    ),
)(delete.cmd)
app.command(
    "diff",
    help=(
        "Select or name a Context and browse its checkpoint changes in a TTY, "
        "or render the active Update record outside a TTY."
    ),
)(diff.cmd)
app.command(
    "compare",
    help=(
        "Enter the interactive Compare session launcher with no endpoints, or compare "
        "the active "
        "Context with an equal-authority PEER; save no target changes."
    ),
)(compare.cmd)

# --- Navigation ---
app.command(
    "switch",
    help="Enter the interactive Context picker, or switch to an explicit Context.",
)(switch.cmd)
app.command(
    "rename",
    help="Rename an ordinary Context namespace and all lexical descendants.",
)(rename.cmd)
app.command(
    "branch",
    help="Create and switch to a new Context branched from the current one.",
)(branch.cmd)
app.command(
    "merge",
    help="Add UID-new direct items from another Context; no semantic reconciliation.",
)(merge.cmd)
app.command(
    "meld",
    help=(
        "Enter the interactive Meld session launcher with no operands, combine two "
        "equal-authority "
        "Contexts into the current empty Context, or directionally use "
        "INCOMING --into authoritative BASELINE; --from INCOMING uses the "
        "current authoritative BASELINE and is normalized to INCOMING "
        "--into BASELINE."
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
app.command(
    "edit",
    help=(
        "Replace direct Memory content by UID or prefix in the current or "
        "explicit Context."
    ),
)(edit.cmd)
app.command(
    "remove",
    help=(
        "Select a Context or direct item to delete, or name it by locator, "
        "name, or UID."
    ),
)(remove.cmd)
app.command(
    "chunk",
    help=(
        "Preview and, after confirmation, split one direct current-Context "
        "Memory by headers, paragraphs, or sentences."
    ),
)(chunk.cmd)
app.command(
    "atomize",
    help=(
        "Enter an interactive Atomize session; --evaluate runs its issue-scoped "
        "directional meld, changes require explicit acceptance, and "
        "--sessions enters the interactive cross-Context session launcher."
    ),
)(atomize.cmd)
app.command("checkpoint",     help="Save a manual checkpoint of the current context state.")(checkpoint.cmd)
app.command(
    "revert",
    help=(
        "Enter the interactive checkpoint picker when no selector is given, or "
        "restore an exact or semantically found checkpoint; discard newer "
        "checkpoints unless --keep is used."
    ),
)(revert.cmd)
app.command(
    "log",
    help=(
        "Select a Context and browse its checkpoints in a TTY, search current-"
        "Context history, or list Profile command attempts."
    ),
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
    help=(
        "Enter the interactive Memory picker when no Memory is given, or trace "
        "one retained origin through its current descendants."
    ),
)(trace.cmd)
app.command(
    "rationale",
    help=(
        "Enter the interactive Memory picker when no Memory is given, or show "
        "recorded evidence and optional labeled contextual inference; no Context changes."
    ),
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
app.command(
    "find-duplicates",
    help=(
        "Report duplicate direct Memories in the current or explicit Context; "
        "no Context changes."
    ),
)(find_duplicates.cmd)
app.command(
    "find-ambiguities",
    help=(
        "Report ambiguous direct Memories in the current or explicit Context; "
        "no Context changes."
    ),
)(find_ambiguities.cmd)
app.command(
    "find-conflicts",
    help=(
        "Report conflicting direct Memory pairs in the current or explicit "
        "Context; no Context changes."
    ),
)(find_conflicts.cmd)
app.command(
    "review",
    help=(
        "Enter an interactive Review session or stage semantic review responses; "
        "never apply Memories."
    ),
)(review.cmd)
app.command(
    "sever",
    help=(
        "Enter the interactive Sever session launcher with no operands, or review one "
        "Source root "
        "against one scoped Criteria root and create a local result that "
        "forgets selected content while leaving Source unchanged."
    ),
)(sever.cmd)
app.command(
    "share",
    help=(
        "Enter interactive Source and endpoint setup when operands are incomplete, "
        "or send one ordinary Context through a grant-backed receiver endpoint."
    ),
)(share.cmd)
app.command(
    "ground",
    help=(
        "Enter an interactive Ground session, or open one named "
        "Goal–Rules–Memories workbench; --sessions enters its launcher."
    ),
)(ground.cmd)
app.command(
    "impact",
    help=(
        "Preview a directional Update or Atomize analysis, or inspect a saved "
        "Meld, Sever, or Update Impact; no Context changes occur in the Impact "
        "view, and APPLY? hands saved work to its normal Apply flow."
    ),
)(impact.cmd)
app.command("integrate",      help="Intelligently integrate info into the current context (uses LLM).")(integrate.cmd)
app.command(
    "update",
    help=(
        "Enter the interactive Update session launcher with no endpoints, or apply a "
        "directional plan to a local target; no shared publication."
    ),
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
    help=(
        "Enter the interactive Profile selector, or manage complete local "
        "MemoryStore Profiles."
    ),
)
app.add_typer(dev_app,    name="dev",    help="Developer tools (eval, diagnostics).", hidden=True)


app.command(
    "help",
    help="Enter the interactive command browser and open syntax help.",
)(help_inventory.cmd)
app.command(
    "shell-init",
    help="Print opt-in shell integration for interactive command prefill.",
)(shell_init.cmd)


# checkout: alias for switch, with -b to branch instead
@app.command(
    "checkout",
    help="Alias for explicit switch; with -b, alias for branch.",
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
