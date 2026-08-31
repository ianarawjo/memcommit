"""Console entry point for the ``mem`` executable."""

import typer

from memcommit.adapters.console.commands.browse_navigate import (
    checkout,
    contexts,
    list as list_command,
    pwd,
    rename,
    show,
    status,
    switch,
)
from memcommit.adapters.console.commands.create_copy_connect import (
    add,
    branch,
    copy,
    embed,
    init,
    reference,
    resource_import,
)
from memcommit.adapters.console.commands.ground_workbench import ground
from memcommit.adapters.console.commands.profiles import profile
from memcommit.adapters.console.commands.sharing_protection import (
    lock,
    share,
    unlock,
)
from memcommit.adapters.console.commands.system_study_tools import (
    config,
    eval,
    help,
    init_study,
    provider,
)
from memcommit.adapters.console.commands.direct_changes import (
    chunk,
    clear,
    delete,
    edit,
    merge,
    move,
    remove,
    replace,
)
from memcommit.adapters.console.commands.history_recovery.inspection import (
    diff,
    log,
    rationale,
    trace,
)
from memcommit.adapters.console.commands.history_recovery.recovery import (
    checkpoint,
    redo,
    revert,
    undo,
)
from memcommit.adapters.console.commands.operation_lifecycle import impact, review
from memcommit.adapters.console.commands.quality_resolution.diagnose import (
    audit,
    find_ambiguities,
    find_conflicts,
    find_duplicates,
    find_redundancies,
)
from memcommit.adapters.console.commands.quality_resolution.repair import (
    dedun,
    dedup,
    resolve,
)
from memcommit.adapters.console.commands.quality_resolution.validate import (
    check_conformance,
    fit,
)
from memcommit.adapters.console.commands.search_explain.retrieve_answer import (
    find,
    query,
    search,
)
from memcommit.adapters.console.commands.search_explain.synthesize import (
    compare,
    summarize,
)
from memcommit.adapters.console.commands.semantic_updates.curate_integrate import (
    forget,
    meld,
    sever,
)
from memcommit.adapters.console.commands.semantic_updates.derive import (
    atomize,
    distill,
    elaborate,
    makemore,
)
from memcommit.adapters.console.commands.semantic_updates.foundation import update
from memcommit.adapters.console.commands.translation import translate
from memcommit.adapters.console.coordination.root_group import MemCommandGroup
from memcommit.adapters.console.diagnostics import dev
from memcommit.operation_catalog import operation_summary

_HELP_CONTEXT_SETTINGS = {
    # Click child Contexts inherit this root setting, so aliases and nested
    # subcommands keep the same help spellings without command-local options.
    "help_option_names": ["-h", "--help"],
}

app = typer.Typer(
    cls=MemCommandGroup,
    context_settings=_HELP_CONTEXT_SETTINGS,
    no_args_is_help=True,
    help="mem — a git-like memory store",
)

# --- Core ---
app.command(
    "init",
    help=operation_summary("init"),
)(init.cmd)
app.command(
    "import",
    help=operation_summary("import"),
)(resource_import.cmd)
app.command(
    "init-study",
    help=operation_summary("init-study"),
)(init_study.cmd)
app.command(
    "add",
    help=operation_summary("add"),
)(add.cmd)
app.command(
    "copy",
    help=operation_summary("copy"),
)(copy.cmd)
app.command(
    "status",
    help=operation_summary("status"),
)(status.cmd)
app.command(
    "pwd",
    help=operation_summary("pwd"),
)(pwd.cmd)
app.command(
    "summarize",
    help=operation_summary("summarize"),
)(summarize.cmd)
app.command(
    "list",
    help=operation_summary("list"),
)(list_command.cmd)
# Keep the compact spelling executable without presenting it as a second
# operation in command discovery.
app.command("ls", hidden=True)(list_command.cmd)
app.command(
    "show",
    help=operation_summary("show"),
    epilog=(
        "The positional target auto-types an existing Context, UUID-shaped "
        "direct item, or CONTEXT:UID. --context remains the explicit Context "
        "route and also qualifies a direct-item selector."
    ),
)(show.cmd)
app.command(
    "contexts",
    help=operation_summary("contexts"),
)(contexts.cmd)
app.add_typer(
    lock.app,
    name="lock",
    help=operation_summary("lock"),
)
app.add_typer(
    unlock.app,
    name="unlock",
    help=operation_summary("unlock"),
)
app.command(
    "clear",
    help=operation_summary("clear"),
)(clear.cmd)
app.command(
    "delete",
    help=operation_summary("delete"),
)(delete.cmd)
app.command(
    "move",
    help=operation_summary("move"),
)(move.cmd)
app.command(
    "diff",
    help=operation_summary("diff"),
)(diff.cmd)
app.command(
    "compare",
    help=operation_summary("compare"),
    epilog=(
        "Positional endpoints auto-type Context, UUID-shaped Memory, and "
        "CONTEXT:MEMORY. One PEER uses the current REFERENCE; REFERENCE PEER "
        "names both sides. --from and --to remain explicitly Context-typed "
        "compatibility aliases."
    ),
)(compare.cmd)

# --- Navigation ---
app.command(
    "switch",
    help=operation_summary("switch"),
)(switch.cmd)
app.command(
    "rename",
    help=operation_summary("rename"),
)(rename.cmd)
app.command(
    "branch",
    help=operation_summary("branch"),
)(branch.cmd)
app.command(
    "merge",
    help=operation_summary("merge"),
    epilog=(
        "Positional form: 'mem merge SOURCE TARGET'. Omitting TARGET uses the "
        "command-start current Context. --from selects Source; --to and --into "
        "select Target."
    ),
)(merge.cmd)
app.command(
    "meld",
    help=operation_summary("meld"),
    epilog=(
        "Positional forms: 'mem meld INCOMING' uses the current BASELINE; "
        "'mem meld INCOMING BASELINE' is directional; and "
        "'mem meld PEER_A PEER_B RESULT_C' is symmetric. With fewer than two "
        "positional sources, --to names the directional BASELINE; after two "
        "peers it names symmetric RESULT C. Quote multiword inline text so the "
        "shell passes it as one operand."
    ),
)(meld.cmd)
app.command(
    "embed",
    help=operation_summary("embed"),
)(embed.cmd)
app.command(
    "reference",
    help=operation_summary("reference"),
)(reference.cmd)
app.command(
    "query",
    help=operation_summary("query"),
)(query.cmd)

# --- Editing ---
app.command(
    "edit",
    help=operation_summary("edit"),
)(edit.cmd)
app.command(
    "replace",
    help=operation_summary("replace"),
)(replace.cmd)
app.command(
    "remove",
    help=operation_summary("delete"),
    hidden=True,
)(remove.cmd)
app.command(
    "chunk",
    help=operation_summary("chunk"),
)(chunk.cmd)
app.command(
    "atomize",
    help=operation_summary("atomize"),
    epilog=(
        "Positional TARGET accepts an existing Context, direct Memory UID, or "
        "CONTEXT:UID. Omitting it uses the current Context; --context and "
        "--memory remain explicit aliases."
    ),
)(atomize.cmd)
app.command(
    "distill",
    help=operation_summary("distill"),
)(distill.cmd)
app.command(
    "elaborate",
    help=operation_summary("elaborate"),
)(elaborate.cmd)
app.command(
    "makemore",
    help=operation_summary("makemore"),
)(makemore.cmd)
app.command(
    "check-conformance",
    help=operation_summary("check-conformance"),
)(check_conformance.cmd)
app.command(
    "fit",
    help=operation_summary("fit"),
)(fit.cmd)
app.command(
    "resolve",
    help=operation_summary("resolve"),
)(resolve.cmd)
app.command(
    "dedup",
    help=operation_summary("dedup"),
)(dedup.cmd)
app.command(
    "dedun",
    help=operation_summary("dedun"),
    epilog=(
        "Positional form: 'mem dedun [CONTEXT]'. Omitting CONTEXT uses the "
        "current Context; --context remains a compatibility alias."
    ),
)(dedun.cmd)
app.command(
    "checkpoint",
    help=operation_summary("checkpoint"),
)(checkpoint.cmd)
app.command(
    "revert",
    help=operation_summary("revert"),
)(revert.cmd)
app.command(
    "log",
    help=operation_summary("log"),
)(log.cmd)
app.command(
    "undo",
    help=operation_summary("undo"),
)(undo.cmd)
app.command(
    "redo",
    help=operation_summary("redo"),
)(redo.cmd)
app.command(
    "trace",
    help=operation_summary("trace"),
)(trace.cmd)
app.command(
    "rationale",
    help=operation_summary("rationale"),
)(rationale.cmd)
app.command(
    "translate",
    help=operation_summary("translate"),
)(translate.cmd)

# --- Semantic (legacy configured LLM or isolated Codex provider) ---
app.command(
    "forget",
    help=operation_summary("forget"),
)(forget.cmd)
app.command(
    "search",
    help=operation_summary("search"),
)(search.cmd)
app.command(
    "find",
    help=operation_summary("find"),
)(find.cmd)
app.command(
    "find-redundancies",
    help=operation_summary("find-redundancies"),
    epilog=(
        "Positional form: 'mem find-redundancies [CONTEXT]'. Omitting CONTEXT "
        "uses the current Context; --context remains a compatibility alias."
    ),
)(find_redundancies.cmd)
app.command(
    "find-duplicates",
    help=operation_summary("find-duplicates"),
    epilog=(
        "Positional form: 'mem find-duplicates [CONTEXT]'. Omitting CONTEXT "
        "uses the current Context; --context remains a compatibility alias."
    ),
)(find_duplicates.cmd)
app.command(
    "find-ambiguities",
    help=operation_summary("find-ambiguities"),
    epilog=(
        "Positional form: 'mem find-ambiguities [CONTEXT]'. Omitting CONTEXT "
        "uses the current Context; --context remains a compatibility alias."
    ),
)(find_ambiguities.cmd)
app.command(
    "find-conflicts",
    help=operation_summary("find-conflicts"),
    epilog=(
        "Positional form: 'mem find-conflicts [CONTEXT]'. Omitting CONTEXT "
        "uses the current Context; --context remains a compatibility alias."
    ),
)(find_conflicts.cmd)
app.command(
    "audit",
    help=operation_summary("audit"),
    epilog=(
        "Positional form: 'mem audit [CONTEXT]'. Omitting CONTEXT uses the "
        "current Context; --context remains a compatibility alias."
    ),
)(audit.cmd)
app.command(
    "review",
    help=operation_summary("review"),
)(review.cmd)
app.command(
    "sever",
    help=operation_summary("sever"),
    epilog=(
        "Positional form: 'mem sever SOURCE CRITERIA [RESULT]'. Omitting "
        "RESULT self-saves into SOURCE; an explicit fresh RESULT saves "
        "elsewhere. --source/--from, --criteria/--against, and "
        "--save-as/--to are equivalent role aliases."
    ),
)(sever.cmd)
app.command(
    "share",
    help=operation_summary("share"),
)(share.cmd)
app.command(
    "ground",
    help=operation_summary("ground"),
)(ground.cmd)
app.command(
    "update",
    help=operation_summary("update"),
    epilog=(
        "Positional forms: 'mem update SOURCE' uses the current Target and "
        "'mem update SOURCE TARGET' is fully explicit. An unambiguous sentence "
        "may supply one process-local Source Memory; --memory forces text. Zero "
        "operands opens setup, and --from/--to retain role-named routes. Quote "
        "multiword inline text so the shell passes it as one operand."
    ),
)(update.cmd)

# --- Sub-apps ---
app.add_typer(
    impact.app,
    name="impact",
    help=operation_summary("impact"),
)
app.add_typer(
    eval.app,
    name="eval",
    help=operation_summary("eval"),
)
app.add_typer(config.app, name="config", help=operation_summary("config"))
app.add_typer(
    provider.app,
    name="provider",
    help=operation_summary("provider"),
)
app.add_typer(
    profile.app,
    name="profile",
    help=operation_summary("profile"),
)
app.add_typer(
    dev.app, name="dev", help="Developer diagnostics and fixture utilities.", hidden=True
)


app.command(
    "help",
    help=operation_summary("help"),
)(help.cmd)


app.command(
    "checkout",
    help=operation_summary("checkout"),
)(checkout.cmd)


if __name__ == "__main__":
    app()
