"""Build and validate the console Help command inventory."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from memcommit.operation_catalog import OperationDescriptor
from memcommit.adapters.console.commands.help import study_commands
from memcommit.adapters.console.commands.help.study_commands import (
    active_profile_is_study,
)
from memcommit.application.operations.help.application import (
    list_operation_help,
    list_operation_help_groups,
)

COMMAND_ANNOTATIONS = {
    "config": "legacy",
}

# Exact alternate spellings stay executable but share their canonical
# operation's discovery row. Conditional compatibility commands such as
# checkout do not belong here because they route to more than one operation.
COMMAND_DISPLAY_ALIASES = {
}

# Related spellings can live under another command group while remaining
# visible in the canonical operation's detail. They are kept separate from
# owned forms so parser-validation and editable-command semantics stay explicit.
COMMAND_RELATED_FORMS: dict[str, tuple[str, ...]] = {}

HELP_CORE_CONCEPTS = (
    (
        "MEMORY",
        "The basic record unit stored inside a Context and independently "
        "selected, reviewed, or changed by Memory-level operations.",
    ),
    (
        "CONTEXT",
        "A named hierarchical workspace that contains only Memories and uses names to organize "
        "separate Contexts. The / separator expresses hierarchy in names such as "
        "task-1/participant; operations with descendant scope can treat a "
        "Context and its descendant Contexts as one subtree. The current Context "
        "is the working location for Context-editing commands; Find and Query "
        "read all Contexts in the active Profile.",
    ),
    (
        "PROFILE",
        "An isolated ownership and storage boundary containing Contexts; "
        "different Profiles may contain the same Context name.",
    ),
    (
        "OPERATION",
        "A reusable action that reads, analyzes, or changes selected Memories "
        "or Contexts through defined inputs and behavior.",
    ),
    (
        "CHECKPOINT",
        "A recoverable history boundary created for each applied operation and "
        "recorded per affected Context.",
    ),
)

# The primer doubles as the legend for the existing object-level color
# contract. Only the Memory type label adopts the Memory token; its explanatory
# prose remains neutral so a report sentence is not mistaken for Memory data.
HELP_CORE_CONCEPT_STYLES = {
    "MEMORY": "class:memory-object bold",
}

HELP_COMMON_LOCATORS = (
    (
        "NAME",
        "A bare existing Context name is canonical and global, never relative.",
    ),
    (
        ".",
        "The current Context captured once when the command starts.",
    ),
    (
        "..",
        "The parent of that captured current Context.",
    ),
    (
        "./CHILD",
        "A child path relative to that captured current Context.",
    ),
    (
        "../PATH",
        "A path relative to the parent of that captured current Context.",
    ),
    (
        "UID",
        "A full UID or accepted prefix. In supported direct-Memory operations, "
        "scan ordinary local Contexts; exactly one direct owner must match, or "
        "ambiguity stops and lists qualified candidates.",
    ),
    (
        "CONTEXT:UID",
        "In supported direct-Memory operations, : separates the direct owner "
        "Context from its Memory UID or prefix; the Context may be relative, "
        "as in ../3:ca562047.",
    ),
)

HELP_COMMON_KEYS = (
    ("↑/↓", "Move by row or Form; hold to accelerate through long lists."),
    (
        "←/→",
        "Change View, or expand and collapse command Forms.",
    ),
    ("PgUp / PgDn", "Jump 10 rows backward or forward in the scrolling Help list."),
    ("Home / End", "Move to the first or final command."),
    (
        "Tab / Shift-Tab",
        "Move focus across View, and visible operation groups.",
    ),
    ("Enter", "Open command Forms, then select or inspect the focused Form."),
    (
        "H",
        "Open full command help, or hide Help while exploring from a waiting session.",
    ),
    (
        "Esc / Q / Ctrl-C",
        "Close Help, cancel selection, or return to the waiting session.",
    ),
)

_HELP_APPLICATION_GROUPS = list_operation_help_groups()
HELP_CATEGORY_GROUPS = tuple(
    (
        group.family.title,
        tuple(operation.name for operation in group.operations),
    )
    for group in _HELP_APPLICATION_GROUPS
)
HELP_CATEGORY_DESCRIPTIONS = {
    group.family.title: group.family.description for group in _HELP_APPLICATION_GROUPS
}
HELP_CATEGORY_SECTIONS = {
    group.family.title: tuple(
        (
            section_group.section.title,
            tuple(operation.name for operation in section_group.operations),
        )
        for section_group in group.sections
    )
    for group in _HELP_APPLICATION_GROUPS
    if group.sections
}
HELP_CATEGORY_BY_COMMAND = {
    operation.name: group.family.title
    for group in _HELP_APPLICATION_GROUPS
    for operation in group.operations
}
HELP_SECTION_BY_COMMAND = {
    operation.name: (group.family.title, section_group.section.title)
    for group in _HELP_APPLICATION_GROUPS
    for section_group in group.sections
    for operation in section_group.operations
}
HELP_CATEGORY_ORDER = {
    group.family.title: index for index, group in enumerate(_HELP_APPLICATION_GROUPS)
}
HELP_COMMAND_ORDER = {
    operation.name: operation_index
    for group in _HELP_APPLICATION_GROUPS
    for operation_index, operation in enumerate(group.operations)
}

COMMAND_FORMS = {
    "add": (
        'mem add "[memory_content]" (add one Memory to the current Context)',
        'mem add "[memory_a]" "[memory_b]" (add one Memory per positional value)',
    ),
    "copy": (
        "mem copy (show the required Memory locator error)",
        "mem copy [UID] (copy one globally unique direct Memory into current)",
        "mem copy [source_context]:[UID] --to [target_context] (copy one exact Memory)",
        "mem copy [UID_A] [UID_B] --from [source_context] --to [target_context] (ordered batch)",
        "mem copy --memory [context]:[UID] --memory [context]:[UID] --to [target_context] (repeatable batch)",
        "mem copy [UID] --to [target_context] --before [item] (insert before an exact Target item)",
        "mem copy [UID] --to [target_context] --after [item] (insert after an exact Target item)",
    ),
    "audit": (
        "mem audit (audit the current Context and save a reviewable receipt)",
        "mem audit [context] (run and save standard checks for one explicit Context)",
        "mem audit --check dun,conflicts (run only the listed checks on current)",
        "mem audit --context [context] (compatibility alias for an exact Context)",
    ),
    "check-conformance": (
        "mem check-conformance (show the required Rules or Target input error)",
        "mem check-conformance [target_context] --against [rules_context] (check Context adherence)",
        "mem check-conformance --against [rules_context] (use the current Context as Target)",
        "mem check-conformance --rule [rules_context] --example [example_context] (role-named Contexts)",
        "mem check-conformance --rule [rules_context] --case [case_context] (Case alias for Example)",
        "mem check-conformance --from [rules_context] --to [subject_context] (include readable References and Embeds)",
        "mem check-conformance --example [example_context] (use the current Context as Rules)",
    ),
    "fit": (
        "mem fit (judge the current Context's direct Memories)",
        'mem fit "[proposition A]" "[proposition B]" (judge the complete set as YES, MAY, or NO)',
        'mem fit "[A]" "[B]" --background "[K]" (judge under one explicit background proposition)',
        "mem fit --ground [ground] (run the revision-bound Ground adapter and save its receipt)",
        "mem fit --ground [ground] --receipt [uid] (reopen one current or stale Ground receipt)",
    ),
    "resolve": (
        "mem resolve (review conflicts across the complete current Context, then Apply)",
    ),
    "dedup": (
        "mem dedup (immediately remove exact plus semantic duplicates from the current Context)",
        "mem dedup [context] (deduplicate one explicit Context)",
        "mem dedup --context [context] (explicit Context option)",
        "mem dedup -d (apply to the exact Context root; default)",
        "mem dedup [context] -r (atomically deduplicate each local lexical Context frame)",
        "mem dedup --literal (remove only same-role exact copies without semantic inference)",
        "mem dedup [context] --literal -r (atomically remove exact copies from each local lexical Context frame)",
    ),
    "atomize": (
        "mem atomize (atomize the current Context now; inspect the saved analysis with mem review)",
        "mem atomize [target] (atomize one Context or direct Memory in place)",
        "mem atomize --context [context] (explicit Context target)",
        "mem atomize --context [context] --memory [uid] (explicit direct Memory target)",
        "mem atomize [target] --refresh (reanalyze the exact target before applying)",
    ),
    "branch": (
        "mem branch [new_context] (branch the current Context and switch)",
        "mem branch [new_context] -r (branch the current Context subtree)",
    ),
    "checkout": (
        "mem checkout (enter the Git-style interactive Context picker)",
        "mem checkout [context] (switch using Git-style syntax)",
        "mem checkout -b [new_context] (create and switch to a Context branch)",
    ),
    "checkpoint": (
        "mem checkpoint (save without a message)",
        'mem checkpoint "[message]" (describe the saved checkpoint)',
        'mem checkpoint -m "[message]" (short message option for current Context)',
        'mem checkpoint --message "[message]" (long message option for current Context)',
        'mem checkpoint [context] "[message]" (checkpoint an explicit local Context)',
        'mem checkpoint [context] -m "[message]" (positionally target a Context)',
        'mem checkpoint --context [context] "[message]" (explicitly target a Context)',
        'mem checkpoint --context [context] --message "[message]" (fully named form)',
        "mem checkpoint --context [context] --direct (checkpoint only that Context)",
        "mem checkpoint --context [context] --recursive (checkpoint its local lexical subtree atomically)",
    ),
    "chunk": (
        "mem chunk (immediately split all splittable direct Memories in the current Context; Undo can restore)",
        "mem chunk [target] (auto-type one Context or direct Memory)",
        "mem chunk --context [context] (all splittable direct Memories in one Context)",
        "mem chunk [memory_selector] --context [context] --method [method] (explicit Memory owner and method)",
        "mem chunk [target] --break-on [punctuation] --min-chars 200 --max-chars 1000 (compose literal and size boundaries)",
    ),
    "clear": (
        "mem clear (immediately clear the current Context; Undo can restore)",
        "mem clear [context] (immediately clear one explicit Context; Undo can restore)",
        "mem clear [context] -r (immediately clear its local lexical subtree as one Undoable command)",
    ),
    "compare": (
        "mem compare (choose peers for a transient concise summary)",
        "mem compare --sessions (enter the interactive Compare session launcher)",
        "mem compare [peer] (summarize current Reference against one Peer)",
        "mem compare [reference] [peer] (summarize explicit peers)",
        "mem compare [reference] [peer] --ledger (run and save the exhaustive Meld basis)",
        "mem compare [reference] [peer] -r (both readable subtrees)",
        "mem compare [reference] [peer] -r --compared-root-only (Reference subtree, compared root)",
        "mem compare [reference] [peer] --reference-descendants --compared-descendants (include each readable subtree)",
        "mem compare --from [reference] --to [peer] (compatibility aliases)",
    ),
    "config": (
        "mem config (show global configuration)",
        "mem config show (show global configuration)",
        'mem config set [key] "[value]" (set one global value)',
    ),
    "contexts": ("mem contexts (list local Contexts)",),
    "delete": (
        "mem delete [UID] (delete one Memory in the current Context)",
        "mem delete --context (confirm deletion of the current Context and all descendants; -c is the same option)",
    ),
    "diff": (
        "mem diff (open the current Context's latest checkpoint in a read-only Viewer)",
        "mem diff [context_or_uid] (open that Context's latest checkpoint)",
        "mem diff [checkpoint_uid] (open that exact checkpoint revision)",
        "mem diff --raw (print the exact unified diff)",
        "mem diff --stat (print the checkpoint summary only)",
        "mem diff --verbose (include unchanged Memories and complete UIDs)",
    ),
    "distill": (
        "mem distill (distill current and add Rules back to current)",
        "mem distill --to [target] (distill current into an existing target)",
        "mem distill --from [source] (distill a source into current)",
        "mem distill --from [source] --to [target] (explicit existing endpoints)",
        "mem distill --from [source] --goal [context|memory|text] "
        "(guide Rule relevance without adding evidence)",
        "mem distill --from [source] -r (include lexical descendants)",
        "mem distill --ground [name] "
        "(inspect read-only Rules from its exact Goal and working-candidate frame)",
        "mem distill --ground [name] --adopt "
        "(atomically add the complete proposal to the physical /rules lane)",
    ),
    "makemore": (
        "mem makemore (Distill current into transient Rules, then add Cases to current)",
        "mem makemore --from [source] --to [target] "
        "(Distill Source transiently, then add Cases to Target)",
        "mem makemore --from [source] --as rules "
        "(treat its direct Memories as existing Rules without Distill)",
        "mem makemore --from [source] --as goal (treat its one direct Memory as a Goal)",
        "mem makemore --goal [context|memory|text] "
        "(use it as Goal Source and add candidate Rules to current)",
        'mem makemore --rule "[rule]" --to [target] (add concrete Cases)',
        'mem makemore --rule "[rule1]" --rule "[rule2]" '
        "(add concrete Cases across explicit Rules to current)",
        "mem makemore --ground [name] --from-goal "
        "(use the exact Ground Goal through the same application)",
        "mem makemore --ground [name] --from-rules "
        "(use the exact active Ground Rules through the same application)",
        "mem makemore --ground [name] --from-goal --adopt "
        "(atomically add the complete proposal to physical /rules)",
        "mem makemore --ground [name] --from-rules --adopt "
        "(atomically add the complete proposal to physical /examples)",
    ),
    "elaborate": (
        "mem elaborate [UID_or_CONTEXT:UID] "
        "(append supported detail after one directly owned Memory)",
        "mem elaborate [UID] --context [context] "
        "(append within one explicit existing owner)",
    ),
    "edit": (
        'mem edit [UID] "[new_content]" (replace a Memory in the current Context)',
    ),
    "replace": (
        "mem replace (enter text and local scope in a compact direct-execution form)",
        'mem replace "[text]" "[replacement]" (immediately replace literal matches as one Undoable command)',
        'mem replace "[text]" --delete-match (immediately remove exact matched text)',
        'mem replace "[expression]" "[replacement]" --regex (explicit regex matching with literal replacement)',
        'mem replace "[text]" "[replacement]" --context [context1] --context [context2] --descendants (execute across multiple local roots)',
    ),
    "dev-eval": (
        "mem dev-eval (list registered scenarios)",
        "mem dev-eval [scenario] (run the scenario and verify its results)",
    ),
    "find": (
        'mem find "[search description]" (semantic search across the active Profile; up to 5 matches)',
    ),
    "find-ambiguities": (
        "mem find-ambiguities (current Context; no changes)",
        "mem find-ambiguities [context] (explicit Context; no changes)",
        "mem find-ambiguities --context [context] (compatibility alias)",
        "mem find-ambiguities --select (interactive readable target selection)",
        "mem find-ambiguities -a (all readable Contexts in the active Profile)",
    ),
    "find-conflicts": (
        "mem find-conflicts (current Context; no changes)",
        "mem find-conflicts [context] (explicit Context; no changes)",
        "mem find-conflicts --context [context] (compatibility alias)",
        "mem find-conflicts --select (interactive readable target selection)",
        "mem find-conflicts -a (all readable Contexts in the active Profile)",
    ),
    "find-duplicates": (
        "mem find-duplicates (report exact duplicates in the current Context)",
        "mem find-duplicates [context] (report exact duplicates in one explicit Context)",
        "mem find-duplicates [context] -r (report each readable lexical Context independently)",
        "mem find-duplicates --context [context] (compatibility alias)",
    ),
    "find-redundancies": (
        "mem find-redundancies (report DUP + semantic DUN in the current Context)",
        "mem find-redundancies [context] (one-shot complete redundancy report)",
        "mem find-redundancies --context [context] (compatibility alias)",
        "mem find-redundancies -d (inspect the exact Context root; default)",
        "mem find-redundancies -r (inspect each readable lexical Context independently)",
    ),
    "forget": (
        'mem forget "KEYWORDS OR CONTENT TO FORGET" (apply edits and removals in the current Context)',
    ),
    "ground": (
        "mem ground (enter the interactive Ground workspace launcher)",
        "mem ground [ground_name] (create or open one physical Ground workspace)",
        'mem ground "[request]" (start a physical Ground draft with an initial request)',
        'mem ground --request "[request]" (start a physical Ground draft with an explicit request)',
        "mem ground --sessions (enter the interactive Ground workspace launcher; TTY required)",
    ),
    "help": ("mem help (enter the interactive command browser)",),
    "impact": (
        "mem impact --sessions (browse every durable artifact inspectable through Impact)",
        "mem impact atomize (preview atomization of the current Context)",
        "mem impact atomize [target] (auto-type one Context or direct Memory)",
        "mem impact atomize --context [context] (compatibility alias)",
        "mem impact atomize --sessions (browse saved Atomize analyses)",
        "mem impact atomize --session [uid] (reopen one exact saved Atomize analysis)",
        "mem impact distill --from [source] --to [target] (preview the Rules Distill would add)",
        "mem impact elaborate [UID_or_CONTEXT:UID] (preview one append-only same-UID revision)",
        "mem impact makemore --from [source] --to [target] "
        "(preview transient Distill Rules and the Cases Makemore would add)",
        "mem impact sever (inspect a saved Sever Impact; APPLY? opens its Apply flow)",
        "mem impact sever --session [uid] (inspect an exact saved Sever Impact; APPLY? opens its Apply flow)",
    ),
    "sync": (
        "mem sync (discover and synchronize all documents and Contexts in the active Profile’s project folder)",
    ),
    "init": (
        "mem init [context] (create missing Contexts in its hierarchy and switch)",
    ),
    "init-study": (
        "mem init-study (initialize coffee with an edited or generated Profile name)",
        "mem init-study [profile_name] (initialize coffee with an explicit Profile name)",
    ),
    "list": ("mem list (list the current Context)",),
    "log": (
        "mem log (print the current Context's checkpoints)",
        'mem log "[query]" (print semantic history matches)',
        "mem log --context [context] (print one explicit Context's checkpoints)",
        "mem log --memory [memory_selector] (print one compact Memory lineage)",
        "mem log --memory [memory_selector] --context [context] (print an explicit Context and Memory lineage)",
        "mem log --operations (Profile command attempts)",
        "mem log --actions (current Study Profile action events)",
    ),
    "merge": (
        "mem merge (choose Semantic or Literal, Source, and Target; Continue to review)",
        "mem merge [source_context] (semantic Merge into the current Context)",
        "mem merge [source_context] [target_context] (semantic Merge of two exact Contexts)",
        "mem merge --from [source_context] --to [target_context] (explicit Source and Target)",
        "mem merge --to [target_context] (open Setup with this Target)",
        "mem merge --literal (open the same Setup with Literal selected)",
        "mem merge --literal [source_context] [target_context] (merge direct stored items)",
        "mem merge --literal [source_context] --keep-target-all (retain Target for every structural conflict)",
        "mem merge --literal [source_context] --take-source-all (take Source for every structural conflict)",
        "mem merge --literal [source_context] --keep-both-all (retain both versions of every Memory conflict)",
    ),
    "move": (
        "mem move (show the required Memory locator error)",
        "mem move [UID] (move one globally unique direct Memory into current)",
        "mem move [source_context]:[UID] --to [target_context] (move one exact Memory)",
        "mem move [UID_A] [UID_B] --from [source_context] --to [target_context] (ordered atomic batch)",
        "mem move --memory [context]:[UID] --memory [context]:[UID] --to [target_context] (repeatable batch)",
        "mem move [UID] --to [target_context] --before [item] (insert before an exact Target item)",
        "mem move [UID] --to [target_context] --after [item] (insert after an exact Target item)",
        "mem move [UID] --to [target_context] --retarget-links (atomically update local live Embeds)",
        "mem move [UID] --to [target_context] --break-links (explicitly leave live Embeds dangling)",
    ),
    "profile": (
        "mem profile (enter the interactive Profile selector in a TTY; list otherwise)",
        "mem profile [profile_name] (select through the concise alias)",
        "mem profile use [profile_name] (select explicitly)",
        "mem profile list (list registered Profiles)",
        "mem profile current (show the active Profile)",
        "mem profile rename [new_name] (rename the active Profile)",
        "mem profile rename [profile_name] [new_name] (rename an explicit Profile)",
        "mem profile rename-study [study_name] [new_name] (rename a Study heading)",
        "mem profile remove [profile_name] (permanently delete one Profile store)",
        "mem profile remove-study [study_name] (permanently delete Study stores)",
    ),
    "provider": (
        "mem provider (print the active Profile route overview without editing)",
        "mem provider status (inspect the selection without connecting)",
        "mem provider use codex_chatgpt (select managed Codex defaults)",
        "mem provider use ollama --model [model] (select a local model)",
        "mem provider use openrouter --model [model] (select a routed model)",
        "mem provider reset --operation [operation] (return to the inherited route)",
        "mem provider probe (test the current selection)",
    ),
    "query": (
        'mem query "[question]" (ask all Contexts in the active Profile)',
    ),
    "rationale": (
        "mem rationale (select one exact Context or Memory from the current readable subtree)",
        "mem rationale [context] (explain one exact readable Context)",
        "mem rationale [memory_selector] (explain one current or historical Memory)",
        "mem rationale --context [context] (explain one exact readable Context)",
        "mem rationale [context]:[memory_selector] (explicit Context and Memory)",
    ),
    "rename": (
        "mem rename [OLD_CONTEXT_NAME] [NEW_CONTEXT_NAME] (rename a Context and its descendants)",
    ),
    "redo": ("mem redo (redo the most recently undone Context command)",),
    "revert": (
        "mem revert (open the current Context's checkpoint revision and history-policy review)",
        "mem revert --context [context] (open one Context's checkpoint and history-policy review)",
        "mem revert [checkpoint] (globally resolve and restore one complete checkpoint unit)",
        "mem revert [checkpoint] --context [context] (resolve a checkpoint at one exact history location)",
        "mem revert [checkpoint] --discard-newer (restore exact and remove newer active checkpoints)",
        "mem revert [checkpoint] --keep (explicit compatibility spelling for the keep-all default)",
        'mem revert "[description]" (semantic lookup; keep all by default when applied)',
    ),
    "review": (
        "mem review (enter the interactive Review session)",
        "mem review audit (planned Audit receipt review; not implemented)",
        "mem review compare (open a saved Compare report)",
        "mem review sever (open terminal evidence for an applied Sever)",
        "mem review [kind] --session [uid] (exact Audit, Atomize, Compare, or Sever artifact)",
        "mem review atomize (open the current Context's applied Atomize evidence)",
        "mem review atomize --context [context] (Context-bound applied Atomize evidence)",
        "mem review atomize --session [analysis_uid] (open one current or retained applied Atomize run)",
        "mem review dedun|distill|makemore|resolve --receipt [uid] (open exact applied checkpoint evidence)",
        "mem review ambiguities (analyze current-Context ambiguities)",
        "mem review ambiguities --context [context] (Context-bound Ambiguity review)",
    ),
    "sever": (
        "mem sever (choose Source and Criteria for an in-place Sever)",
        "mem sever --sessions (enter the interactive Sever session launcher)",
        "mem sever [source_context] [criteria_context] (update Source in place)",
        "mem sever [source_context] [criteria_context] -r (include both descendant scopes)",
        "mem sever [source_context] [criteria_context] --source-descendants (include Source descendants)",
        "mem sever [source_context] [criteria_context] --criteria-descendants (include Criteria descendants)",
        "mem sever --source [source] --criteria [criteria] (compatibility role aliases)",
        "mem sever --from [source] --against [criteria] (directional role aliases)",
        "mem sever --criteria [criteria_context] (current Context is Source)",
        "mem sever --resume [uid] (open an exact saved Sever session)",
    ),
    "show": (
        "mem show (show the direct contents of the current Context)",
        "mem show [target] (auto-type one Context or direct item)",
        "mem show --context [context] (show an explicit Context's direct contents)",
        "mem show [item] --context [context] (show an item in an explicit Context)",
    ),
    "status": (
        "mem status (detailed current-Context status)",
        "mem status --short (one-line status)",
        "mem status --branch (include Profile and Context lineage)",
        "mem status --recursive (include readable lexical descendants)",
    ),
    "pwd": ("mem pwd (print the current canonical Context name)",),
    "summarize": (
        "mem summarize (direct summary of the current Context)",
        "mem summarize [context] (direct summary of an explicit Context)",
        "mem summarize -r (recursive summary of the current Context)",
        "mem summarize [context] -r (lexical descendants)",
        "mem summarize [context] --copy (copy verified direct understanding as plain text)",
    ),
    "switch": (
        "mem switch (enter the interactive Context picker)",
        "mem switch [context] (explicit Context)",
    ),
    "trace": (
        "mem trace (select one exact Context or Memory from the current local subtree)",
        "mem trace [context] (show one exact Context lineage)",
        "mem trace [memory_selector] (print the bounded retained lineage document)",
        "mem trace --context [context] (show one exact Context lineage)",
        "mem trace [context]:[memory_selector] (explicit Context and Memory)",
    ),
    "undo": ("mem undo (undo the latest recorded Context command)",),
    "update": (
        'mem update "Instruction" (apply to the current Context)',
        'mem update "Instruction" -r (include the current Context\'s lexical descendants)',
    ),
}


@dataclass(frozen=True)
class CommandEntry:
    """One visible command and the inventory metadata used to present it."""

    name: str
    annotation: str | None
    description: str
    command: object
    forms: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    operation_help: OperationDescriptor | None = None
    maturity: str | None = None


@dataclass(frozen=True)
class HelpSelection:
    """One selected command template or request for its complete help."""

    command_name: str
    command_line: str
    show_help: bool = False


def _selectable_form_line(form: str) -> str:
    """Remove explanatory syntax while retaining an editable command template."""
    command_line = form.partition(" (")[0]
    return command_line


def _default_command_forms(name: str, command: object) -> tuple[str, ...]:
    """Build one conservative canonical form from registered operands."""
    if callable(getattr(command, "list_commands", None)):
        return (f"mem {name} [command]",)
    operands: list[str] = []
    has_required_operand = False
    for parameter in getattr(command, "params", ()):
        if getattr(parameter, "param_type_name", "") != "argument":
            continue
        has_required_operand = has_required_operand or bool(
            getattr(parameter, "required", False)
        )
        label = str(
            getattr(parameter, "metavar", None)
            or getattr(parameter, "human_readable_name", "VALUE")
        ).lower()
        if getattr(parameter, "nargs", 1) != 1:
            label += "..."
        operands.append(f"[{label}]")
    operand_form = f"mem {name} " + " ".join(operands)
    if not operands:
        return (f"mem {name}",)
    if not has_required_operand:
        # An omitted optional operand is often a distinct public route (for
        # example, current-target operation or an interactive picker), not
        # merely abbreviated parser syntax.
        return (f"mem {name}", operand_form)
    return (operand_form,)


def _visible_commands(ctx: typer.Context) -> list[tuple[str, object]]:
    """Return visible root commands in case-insensitive alphabetical order."""
    group = ctx.command
    if not (
        callable(getattr(group, "list_commands", None))
        and callable(getattr(group, "get_command", None))
    ):
        raise RuntimeError("The root CLI is not a command group.")

    commands: list[tuple[str, object]] = []
    for name in group.list_commands(ctx):
        command = group.get_command(ctx, name)
        if command is None or getattr(command, "hidden", False):
            continue
        commands.append((name, command))
    # Registration order reflects the source file's conceptual sections, but
    # this surface is a lookup inventory: alphabetical order makes an exact
    # command substantially easier to find in both plain output and the TUI.
    return sorted(commands, key=lambda item: (item[0].casefold(), item[0]))


def command_entries(root: typer.Context) -> list[CommandEntry]:
    """Build the one shared visible command inventory for every Help surface."""

    commands = _visible_commands(root)
    visible_names = {name for name, _ in commands}
    operation_help_by_name = {
        operation.name: operation for operation in list_operation_help()
    }
    configured_names = (
        COMMAND_ANNOTATIONS.keys()
        | COMMAND_DISPLAY_ALIASES.keys()
        | COMMAND_FORMS.keys()
        | COMMAND_RELATED_FORMS.keys()
        | HELP_CATEGORY_BY_COMMAND.keys()
    )
    stale = sorted(configured_names - visible_names)
    if stale:
        typer.secho(
            "Help inventory error: annotated command not registered: "
            + ", ".join(stale),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    commands_by_name = dict(commands)
    group = root.command
    for name, aliases in COMMAND_DISPLAY_ALIASES.items():
        command = commands_by_name[name]
        command_callback = getattr(command, "callback", None)
        command_target = getattr(command_callback, "__wrapped__", command_callback)
        for alias in aliases:
            alias_command = group.get_command(root, alias)
            alias_callback = getattr(alias_command, "callback", None)
            alias_target = getattr(alias_callback, "__wrapped__", alias_callback)
            if (
                alias_command is None
                or not getattr(alias_command, "hidden", False)
                or alias_target is not command_target
            ):
                typer.secho(
                    "Help inventory error: displayed alias must be a hidden "
                    f"exact callback spelling: {name} ({alias})",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
    uncategorized = sorted(visible_names - HELP_CATEGORY_BY_COMMAND.keys())
    if uncategorized:
        typer.secho(
            "Help inventory error: command category missing: "
            + ", ".join(uncategorized),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    missing_operation_help = sorted(visible_names - operation_help_by_name.keys())
    stale_operation_help = sorted(operation_help_by_name.keys() - visible_names)
    if missing_operation_help or stale_operation_help:
        details = []
        if missing_operation_help:
            details.append("missing: " + ", ".join(missing_operation_help))
        if stale_operation_help:
            details.append("not registered: " + ", ".join(stale_operation_help))
        typer.secho(
            "Help inventory error: Operation Help coverage mismatch ("
            + "; ".join(details)
            + ")",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    description_mismatches = sorted(
        name
        for name, command in commands
        if " ".join((getattr(command, "help", None) or "").split())
        != operation_help_by_name[name].summary
    )
    if description_mismatches:
        typer.secho(
            "Help inventory error: registered summary differs from Operation "
            "Help: " + ", ".join(description_mismatches),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    # Validate the complete registered catalog before applying Help's Study list;
    # hiding a row must not conceal missing or inconsistent operation metadata.
    discoverable_names = visible_names
    if active_profile_is_study():
        unknown_names = (
            study_commands.STUDY_VISIBLE_COMMAND_NAMES - operation_help_by_name.keys()
        )
        if unknown_names:
            typer.secho(
                "Help error: unknown Study command names: "
                + ", ".join(sorted(unknown_names)),
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        discoverable_names = visible_names & study_commands.STUDY_VISIBLE_COMMAND_NAMES
    return [
        CommandEntry(
            name=name,
            annotation=COMMAND_ANNOTATIONS.get(name),
            description=" ".join(
                (getattr(command, "help", None) or "No description.").split()
            ),
            command=command,
            forms=(
                COMMAND_FORMS.get(name, _default_command_forms(name, command))
                + COMMAND_RELATED_FORMS.get(name, ())
            ),
            aliases=COMMAND_DISPLAY_ALIASES.get(name, ()),
            operation_help=operation_help_by_name[name],
            maturity=operation_help_by_name[name].maturity,
        )
        for name, command in commands
        if name in discoverable_names
    ]
