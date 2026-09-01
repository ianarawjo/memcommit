"""Build and validate the console Help command inventory."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from memcommit.operation_catalog import OperationDescriptor
from memcommit.application.operations.help.application import (
    list_operation_help,
    list_operation_help_groups,
)
from memcommit.adapters.console.commands.help.localized_copy import (
    validate_help_translation_coverage,
)

COMMAND_ANNOTATIONS = {
    "config": "legacy",
}

# Exact alternate spellings stay executable but share their canonical
# operation's discovery row. Conditional compatibility commands such as
# checkout do not belong here because they route to more than one operation.
COMMAND_DISPLAY_ALIASES = {
    "delete": ("remove",),
    "list": ("ls",),
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
        "A named hierarchical workspace that contains Memories and organizes "
        "child Contexts. The / separator expresses hierarchy in names such as "
        "task-1/participant; operations with descendant scope can treat a "
        "Context and its descendant Contexts as one subtree. Commands use the "
        "current Context when none is specified.",
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
        "GRANT",
        "A permission relationship that can be given or received, selectively "
        "allowing someone without direct ownership to read or query a Context "
        "and its Memories, or run permitted operations on them, while the Grant "
        "remains valid.",
    ),
    (
        "SESSION",
        "Stores an analysis or review workflow so it can be reopened and "
        "continued. Apply results and checkpoint history separately show "
        "whether Context changes were made.",
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
        "Change Language or View, or expand and collapse command Forms.",
    ),
    ("PgUp / PgDn", "Jump 10 rows backward or forward in the scrolling Help list."),
    ("Home / End", "Move to the first Help row or the final command."),
    (
        "Tab / Shift-Tab",
        "Move focus across Language, View, and visible operation groups.",
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
    group.family.title: (
        group.family.execution_label,
        group.family.description,
    )
    for group in _HELP_APPLICATION_GROUPS
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
        "mem add (open the interactive multi-Memory editor)",
        'mem add --memory "[memory_content]" --memory "[memory_content]" (add an explicit batch)',
        "mem add --input [file] (add one Memory per non-empty line)",
        "mem add --paste (add clipboard text as one Memory per non-empty line)",
        'mem add "[memory_content]" --to [target_context] (add to an explicit Target)',
        "mem add --input [file] --to [target_context] (batch-add to an explicit Target)",
        "mem add --paste --to [target_context] (add clipboard text to an explicit Target)",
    ),
    "copy": (
        "mem copy (show the required Memory locator error)",
        "mem copy [UID] (copy one globally unique direct Memory into current)",
        "mem copy [source_context]:[UID] --into [target_context] (copy one exact Memory)",
        "mem copy [UID_A] [UID_B] --from [source_context] --to [target_context] (ordered batch)",
        "mem copy --memory [context]:[UID] --memory [context]:[UID] --into [target_context] (repeatable batch)",
        "mem copy [UID] --into [target_context] --before [item] (insert before an exact Target item)",
        "mem copy [UID] --into [target_context] --after [item] (insert after an exact Target item)",
    ),
    "audit": (
        "mem audit (audit the current Context and save a reviewable receipt)",
        "mem audit [context] (run and save all checks for one explicit Context)",
        "mem audit --select (choose one Context, run all checks, and save)",
        "mem audit --context [context] (compatibility alias for an exact Context)",
        "mem audit --context [context] --against [rules_context] (add the shared Conformance check)",
        "mem audit --context [context] --rule [rules_context] (role-named Rules alias)",
        "mem audit --context [context] --snapshot (save and print the combined report)",
    ),
    "check-conformance": (
        "mem check-conformance (show the required Ground or Rules input error)",
        "mem check-conformance --ground [ground] (replay Rules without exposing expected outputs)",
        "mem check-conformance [target_context] --against [rules_context] (check Context adherence)",
        "mem check-conformance --against [rules_context] (use the current Context as Target)",
        "mem check-conformance --rule [rules_context] --example [example_context] (role-named Contexts)",
        "mem check-conformance --rule [rules_context] --case [case_context] (Case alias for Example)",
        "mem check-conformance --from [rules_context] --to [subject_context] (generic directional aliases)",
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
        "mem resolve (decide current-Context conflicts, then apply one whole-Context UpdatePlan)",
        "mem resolve [context] (decide conflicts and update one exact Context)",
        "mem resolve [context] [memory_uid] (select one actionable Memory without narrowing the complete Context frame)",
        "mem resolve [context] --memory [memory_uid] (explicitly accept a short Memory prefix)",
        "mem resolve [context]:[memory_uid] (bind one Memory restriction to its exact Context)",
        "mem resolve --context [context] --no-create (limit the finalized UpdatePlan to existing-Memory edits)",
        'mem resolve --context [context] --allow-delete --guidance "[grounds]" (exceptionally permit grounded retirement)',
    ),
    "dedup": (
        "mem dedup (remove exact duplicates from the current Context)",
        "mem dedup [context] (remove exact duplicates from one explicit Context)",
        "mem dedup [context] -r (atomically deduplicate each local lexical Context frame)",
    ),
    "dedun": (
        "mem dedun (immediately resolve exact plus semantic DUN groups in the current Context)",
        "mem dedun [context] (immediately resolve one explicit Context)",
        "mem dedun --context [context] (compatibility alias)",
        "mem dedun -d (apply to the exact Context root; default)",
        "mem dedun -r (atomically apply independent DUN groups across a local lexical subtree)",
    ),
    "atomize": (
        "mem atomize (atomize the current Context now; inspect the saved analysis with mem review)",
        "mem atomize [target] (atomize one Context or direct Memory in place)",
        "mem atomize --context [context] (explicit Context target)",
        "mem atomize --context [context] --memory [uid] (explicit direct Memory target)",
        "mem atomize [target] --refresh (reanalyze the exact target before applying)",
    ),
    "branch": (
        "mem branch (choose a local Source, parent location, and fresh target)",
        "mem branch [new_context] (branch the current Context and switch)",
        "mem branch [new_context] --from [source_context] (branch an exact local Source)",
        "mem branch [new_context] --source-root-only (explicit Source root)",
        "mem branch [new_context] -r (branch the current Context subtree)",
    ),
    "checkout": (
        "mem checkout (enter the Git-style interactive Context picker)",
        "mem checkout [context] (switch using Git-style syntax)",
        "mem checkout -b (choose, create, and switch to a Context branch)",
        "mem checkout -b [new_context] (create and switch to a Context branch)",
        "mem checkout -b [new_context] -r (create and switch to a recursive Context branch)",
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
    "contexts": ("mem contexts (list local Contexts and granted views)",),
    "delete": (
        "mem delete [target1] [target2] (delete mixed Contexts or direct items in order)",
        "mem delete (select a Context or direct item interactively)",
        "mem delete [item1] [item2] --context [context] (scope every item to one owner)",
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
        "mem distill --from [source] -r (include descendants and embeds)",
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
        'mem edit [UID_or_CONTEXT:UID] "[new_content]" (replace one direct Memory)',
        "mem edit (choose one direct Memory and review its replacement interactively)",
        "mem edit --input [batch_file] (batch mode: UID<TAB>CONTENT records)",
        'mem edit [UID] "[new_content]" --context [context] (compatibility explicit Context)',
        "mem edit --input [batch_file] --context [context] (batch-edit an explicit Context)",
    ),
    "replace": (
        "mem replace (enter text and local scope in a compact direct-execution form)",
        'mem replace "[text]" "[replacement]" (immediately replace literal matches as one Undoable command)',
        'mem replace "[text]" --delete-match (immediately remove exact matched text)',
        'mem replace "[expression]" "[replacement]" --regex (explicit regex matching with literal replacement)',
        'mem replace "[text]" "[replacement]" --context [context1] --context [context2] --descendants (execute across multiple local roots)',
    ),
    "embed": (
        "mem embed (choose Context or Memory link, target, and insertion gap interactively)",
        "mem embed [UID] (unique direct local owner; Target defaults to current Context)",
        "mem embed [source_context]:[UID] --into [target_context] (explicit live Memory link)",
        "mem embed [child_context] --into [target_context] (append)",
        "mem embed --from [child_context] --to [target_context] (explicit Context endpoints)",
        "mem embed [child_context] --into [target_context] --before [item]",
        "mem embed [child_context] --into [target_context] --after [item]",
        "mem embed [UID] --from [source_context] --into [target_context] (compatibility live Memory link)",
        "mem embed [memory_selector] --from [source_context] --into [target_context] --before [item]",
        "mem embed [memory_selector] --from [source_context] --into [target_context] --after [item]",
    ),
    "eval": ("mem eval (show the reserved PARTIAL shell; no evaluation subcommands)",),
    "find": (
        "mem find (interactive provider-free pattern, Context scope, and complete results)",
        'mem find "[text]" (literal text in the direct current Context)',
        'mem find -i "[text]" (case-insensitive literal text)',
        'mem find --regex "[expression]" (explicit regular-expression matching)',
        'mem find -r "[text]" (lexical descendants and embedded Contexts)',
        'mem find --context [context1] --context [context2] "[text]" (multiple roots)',
        'mem find --descendants --exclude-embeds "[text]" (lexical subtrees only)',
        'mem find -a "[text]" (all readable Contexts in the active Profile)',
    ),
    "search": (
        "mem search (interactive semantic search, checked COPY/REFERENCE/EMBED, and Save Location)",
        'mem search "[query]" (semantic search in the direct current Context)',
        'mem search -r "[query]" (namespace descendants and embedded Contexts)',
        'mem search --context [context] "[query]" (direct explicit Context root)',
        'mem search --context [context1] --context [context2] --descendants "[query]" (multiple roots with lexical descendants)',
        'mem search --context-only --follow-embeds "[query]" (exact lexical roots while following embedded Contexts)',
        'mem search --descendants --exclude-embeds "[query]" (lexical subtrees without embedded traversal)',
        'mem search -d "[query]" (direct preset: context-only plus exclude-embeds)',
        'mem search -a "[query]" (all readable Contexts in the active Profile)',
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
        "mem forget (enter interactive instruction and direct-Source setup)",
        'mem forget "[instruction]" (decide and atomically apply selective forgetting)',
        'mem forget "[instruction]" --context [context] (explicit direct Source)',
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
        'mem impact forget "[instruction]" (preview complete in-place decisions)',
        'mem impact forget "[instruction]" --context [context] (preview one exact direct Source)',
        "mem impact distill --from [source] --to [target] (preview the Rules Distill would add)",
        "mem impact elaborate [UID_or_CONTEXT:UID] (preview one append-only same-UID revision)",
        "mem impact makemore --from [source] --to [target] "
        "(preview transient Distill Rules and the Cases Makemore would add)",
        "mem impact resolve --context [context] (inspect conflict decisions before any UpdatePlan exists)",
        "mem impact meld (inspect a saved Meld Impact; APPLY? opens its Apply flow)",
        "mem impact meld --session [uid] (inspect an exact saved Meld Impact; APPLY? opens its Apply flow)",
        "mem impact sever (inspect a saved Sever Impact; APPLY? opens its Apply flow)",
        "mem impact sever --session [uid] (inspect an exact saved Sever Impact; APPLY? opens its Apply flow)",
        "mem impact update (inspect the saved Update Impact; APPLY? opens its Apply flow)",
        "mem impact update [source_context] [target_context] (new directional preview)",
        "mem impact update --session [uid] (inspect the exact saved Update Impact; APPLY? opens its Apply flow)",
        "mem impact --from [source_context] --to [target_context] (directional preview)",
        "mem impact -r --from [source_context] --to [target_context] (recursive endpoints)",
        "mem impact -r --from [source_context] --to [target_context] --target-root-only (Source subtree, target root)",
        "mem impact --from [source_context] (current Context is target)",
        "mem impact --to [target_context] (current Context is source)",
    ),
    "import": (
        "mem import (choose a non-active source and import Profile, Context, or Memory)",
        "mem import profile [profile_name] --from [store] (clean baseline from an external store)",
        "mem import profile [profile_name] --from-profile [source_profile] (clean baseline from a registered Profile)",
        "mem import context [source_context] --from-profile [source_profile] (one Context root)",
        "mem import context [source_context] --from-profile [source_profile] --as [new_root] (renamed Context root)",
        "mem import context [source_context] --from-profile [source_profile] -r (Context tree)",
        "mem import memory [memory_selector] --from-profile [source_profile] --context [source_context] (into current Context)",
        "mem import memory [memory_selector] --from-profile [source_profile] --context [source_context] --into [target_context]",
        "mem import [profile_name] --from [store] (legacy clean-baseline Profile spelling)",
    ),
    "init": (
        "mem init (edit a suggested fresh Context name, create, and switch)",
        "mem init [context] (create and switch to one Context)",
        "mem init --parents (edit a suggested name and ensure its hierarchy)",
        "mem init [context] --parents (ensure its lexical hierarchy and switch)",
    ),
    "init-study": (
        "mem init-study (initialize coffee with an edited or generated Profile name)",
        "mem init-study [profile_name] (initialize coffee with an explicit Profile name)",
        "mem init-study --scenario legacy (reproduce the preserved debugging fixture)",
        "mem init-study [profile_name] --scenario legacy (name a legacy debugging run)",
    ),
    "list": (
        "mem list (list the current Context)",
        "mem list [context] (explicit Context listing)",
        "mem list -r (recursive current-Context listing; -R remains an alias)",
        "mem list [context] -R (recursive Context listing)",
        "mem list --copy (copy the current listing as plain text)",
        "mem list [context] --copy (copy an explicit listing as plain text)",
    ),
    "lock": (
        "mem lock (lock the current Context)",
        "mem lock --recursive (lock the current Context namespace)",
        "mem lock [context] (auto-classify and lock an explicit Context)",
        "mem lock [context] --recursive (lock an explicit Context namespace)",
        "mem lock [UID] (auto-classify one unique direct local Memory)",
        "mem lock [context]:[UID] (lock a Memory through its exact owner)",
        "mem lock --memory [short_prefix] --context [context] (explicit Memory)",
        "mem lock --profile (lock the active Profile)",
        "mem lock context [context] (compatibility explicit Context)",
        "mem lock memory [UID] --context [context] (compatibility direct Memory)",
        "mem lock profile (compatibility active Profile)",
    ),
    "log": (
        "mem log (print the current Context's checkpoints)",
        'mem log "[query]" (print semantic history matches)',
        "mem log --context [context] (print one explicit Context's checkpoints)",
        "mem log --memory [memory_selector] (print one compact Memory lineage)",
        "mem log --memory [memory_selector] --context [context] (print an explicit Context and Memory lineage)",
        "mem log --operations (Profile command attempts)",
        "mem log --actions (current Study Profile action events)",
    ),
    "meld": (
        "mem meld (choose mode and endpoints for a new Meld)",
        "mem meld --sessions (enter the interactive Meld session launcher)",
        "mem meld --memory [exact_text] (one process-local incoming Memory into current local Baseline)",
        "mem meld --memory [exact_text] --into [baseline_context] (one process-local incoming Memory into an explicit local Baseline)",
        "mem meld --memory [exact_text] --to [baseline_context] (shared directional Target spelling)",
        "mem meld [non_context_sentence] (unambiguous inline-Memory shorthand into current local Baseline)",
        "mem meld [incoming_context] (directional into current Baseline)",
        "mem meld [incoming_context] [baseline_context] (directional)",
        "mem meld team/proposed-changes team/current-policy (example: directional Baseline)",
        "mem meld [peer_a] [peer_b] [result_context] (symmetric Result)",
        "mem meld team/draft-a team/draft-b team/merged-draft (example: symmetric Result)",
        "mem meld [peer_a] [peer_b] --to [result_context] (symmetric Result alias)",
        "mem meld [peer_a] [peer_b] [result_context] -r (both subtrees)",
        "mem meld [peer_a] [peer_b] [result_context] -r --right-root-only (left subtree, right root)",
        "mem meld [peer_a] [peer_b] [result_context] --left-descendants --right-descendants (symmetric readable subtrees)",
        "mem meld [incoming_context] --into [baseline_context] (directional alias)",
        "mem meld [incoming_context] --left-descendants --into [baseline_context] --right-descendants (directional selected subtrees with owner-aware baseline writes)",
        "mem meld --into [baseline_context] (current Context is incoming)",
        "mem meld --from [incoming_context] (current Context is baseline)",
        "mem meld --from [incoming_context_or_sentence] --to [baseline_context] (fully named directional route)",
    ),
    "merge": (
        "mem merge (choose a readable Source, CREATE-authorized Target, and reach in a TTY)",
        "mem merge [source_context] [target_context] --direct (explicit exact roots)",
        "mem merge [source_context] [target_context] --recursive (explicit path-aligned subtrees)",
        "mem merge [source_context] --direct (exact Source root into current Context; default)",
        "mem merge [source_context] --recursive (path-aligned descendants into current Context)",
        "mem merge [source_context] --into [target_context] (compatibility alias)",
        "mem merge --from [source_context] --to [target_context] (explicit directional aliases)",
        "mem merge [source_context] --keep-target-all (resolve every structural conflict by retaining Target)",
        "mem merge [source_context] --take-source-all (resolve every structural conflict with exact Source values)",
        "mem merge [source_context] --resolve [conflict_id]=keep-target (repeat one reviewed decision per conflict)",
    ),
    "move": (
        "mem move (show the required Memory locator error)",
        "mem move [UID] (move one globally unique direct Memory into current)",
        "mem move [source_context]:[UID] --into [target_context] (move one exact Memory)",
        "mem move [UID_A] [UID_B] --from [source_context] --to [target_context] (ordered atomic batch)",
        "mem move --memory [context]:[UID] --memory [context]:[UID] --into [target_context] (repeatable batch)",
        "mem move [UID] --into [target_context] --before [item] (insert before an exact Target item)",
        "mem move [UID] --into [target_context] --after [item] (insert after an exact Target item)",
        "mem move [UID] --into [target_context] --retarget-links (atomically update local live Embeds)",
        "mem move [UID] --into [target_context] --break-links (explicitly leave live Embeds dangling)",
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
        "mem profile migrate-context [legacy_context] [portable_context] (preview a legacy Context-name migration; run its exact Apply receipt to commit)",
        "mem profile remove [profile_name] (permanently delete one Profile store)",
        "mem profile remove-study [study_name] (permanently delete Study stores)",
        "mem profile import [profile_name] --from [store] (copy a complete store)",
        "mem profile archive-study [study_name] (detach a legacy split Study)",
        "mem profile grant list (list cross-Profile views)",
        "mem profile grant create [authority_profile] [grantee_profile] [source_context] --into [attachment_context] --allow [permission]",
        "mem profile grant create [authority_profile] [grantee_profile] [source_context] --into [attachment_context] --allow [permission] --recursive (include current descendants)",
        "mem profile grant update [grant] --allow [permission]",
        "mem profile grant update [grant] --allow [permission] --refresh-scope (include all current descendants)",
        "mem profile grant update [grant] --allow [permission] --root-only (include only the root)",
        "mem profile grant delete [grant] (revoke a view)",
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
        "mem query (open the compact one-shot Scope, Question, and Answer workbench)",
        'mem query "[question]" (ask the direct current ordinary Context)',
        'mem query -r "[question]" (include descendants and embedded Contexts)',
        "mem query [context] (open the workbench with an accessible Context selected)",
        'mem query [context] "[question]" (ask an accessible Context)',
        'mem query --context [context] "[question]" (ask an explicit ordinary Context)',
        'mem query -a "[question]" (ask all readable Contexts in the active Profile)',
        "mem query [query_view] (open the workbench with a query-only View selected)",
        'mem query [query_view] "[question]" (ask a query-only view)',
        'mem query [query_view] "[question]" --language [language] (explicit source language)',
    ),
    "rationale": (
        "mem rationale (select one exact Context or Memory from the current readable subtree)",
        "mem rationale [context] (explain one exact readable Context)",
        "mem rationale [memory_selector] (explain one current or historical Memory)",
        "mem rationale --context [context] (explain one exact readable Context)",
        "mem rationale [context]:[memory_selector] (explicit Context and Memory)",
    ),
    "reference": (
        "mem reference (choose a Context or Memory snapshot and Target interactively)",
        "mem reference [UID] (unique direct local owner; Target defaults to current Context)",
        "mem reference [source_context]:[UID] --into [target_context] (explicit immutable Memory snapshot)",
        "mem reference [source_context] --direct (direct Context snapshot into current Context)",
        "mem reference [source_context] --into [target_context] --recursive (snapshot descendants and local embeds)",
        "mem reference --from [source_context] --to [target_context] --recursive (explicit Context endpoints)",
        "mem reference [UID] --from [source_context] (compatibility snapshot into current Context)",
        "mem reference [UID] --from [source_context] --into [target_context] (compatibility immutable snapshot)",
    ),
    "rename": (
        "mem rename [old_context] [new_context] (review and rename a Context namespace)",
        "mem rename [old_context] [new_context] --force (skip confirmation; retain all safety checks)",
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
        "mem review audit (open a saved finder and whole-Context Fit Audit)",
        "mem review compare (open a saved Compare report)",
        "mem review meld (open terminal evidence for an applied Meld)",
        "mem review sever (open terminal evidence for an applied Sever)",
        "mem review update (open terminal evidence for an applied Update)",
        "mem review [kind] --session [uid] (exact Audit, Compare, Meld, Sever, or Update artifact)",
        "mem review atomize (open the current Context's applied Atomize evidence)",
        "mem review atomize --context [context] (Context-bound applied Atomize evidence)",
        "mem review dedun|distill|makemore|forget|resolve --receipt [uid] (open exact applied checkpoint evidence)",
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
    "share": (
        "mem share (enter the interactive Share setup)",
        "mem share [source_context] (enter the interactive endpoint selector)",
        "mem share --to [endpoint] (enter the interactive Source selector)",
        "mem share [source_context] --to [endpoint] (explicit delivery)",
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
        "mem status --recursive (include readable descendants and embedded Contexts)",
    ),
    "pwd": ("mem pwd (print the current canonical Context name)",),
    "summarize": (
        "mem summarize (direct summary of the current Context)",
        "mem summarize [context] (direct summary of an explicit Context)",
        "mem summarize -r (recursive summary of the current Context)",
        "mem summarize [context] -r (lexical descendants and embedded Contexts)",
        "mem summarize [context] --copy (copy verified direct understanding as plain text)",
    ),
    "switch": (
        "mem switch (enter the interactive Context picker)",
        "mem switch [context] (explicit Context)",
        "mem switch --previous (move backward in Context navigation history)",
        "mem switch --next (move forward after moving backward)",
    ),
    "translate": (
        "mem translate (show/save a default-English view of the current Context)",
        "mem translate [target] (auto-type one Context or direct Memory)",
        "mem translate --to [language] (show/save a current-Context view)",
        "mem translate [target] --to [language] (show/save one Context or Memory view)",
        "mem translate --save-as [result_context] (default-English new Context and switch)",
        "mem translate [memory_selector] --save-as [result_context] (new Context replacing one Memory; switch)",
        "mem translate --to [language] --save-as [result_context] (new translated Context and switch)",
        "mem translate [memory_selector] --to [language] --save-as [result_context] (new Context replacing one Memory; switch)",
        "mem translate --in-place (add default-English sibling Memories)",
        "mem translate [memory_selector] --in-place (add one default-English sibling Memory)",
        "mem translate --to [language] --in-place (add translated sibling Memories)",
        "mem translate [memory_selector] --to [language] --in-place (add one translated sibling Memory)",
    ),
    "trace": (
        "mem trace (select one exact Context or Memory from the current local subtree)",
        "mem trace [context] (show one exact Context lineage)",
        "mem trace [memory_selector] (print the bounded retained lineage document)",
        "mem trace --context [context] (show one exact Context lineage)",
        "mem trace [context]:[memory_selector] (explicit Context and Memory)",
    ),
    "undo": ("mem undo (undo the latest recorded Context command)",),
    "unlock": (
        "mem unlock (unlock the current Context)",
        "mem unlock --recursive (unlock the current Context namespace)",
        "mem unlock [context] (auto-classify and unlock an explicit Context)",
        "mem unlock [context] --recursive (unlock an explicit Context namespace)",
        "mem unlock [UID] (auto-classify one unique direct local Memory)",
        "mem unlock [context]:[UID] (unlock a Memory through its exact owner)",
        "mem unlock --memory [short_prefix] --context [context] (explicit Memory)",
        "mem unlock --profile (unlock the active Profile)",
        "mem unlock context [context] (compatibility explicit Context)",
        "mem unlock memory [UID] --context [context] (compatibility direct Memory)",
        "mem unlock profile (compatibility active Profile)",
    ),
    "update": (
        "mem update (choose Source and Target for a new Update)",
        "mem update --sessions (enter the interactive Update session launcher)",
        "mem update [source_context] [target_context] (explicit direction)",
        "mem update [source_context] (current Context is target)",
        "mem update [non_context_sentence] --to [target_context] (one process-local Source Memory)",
        "mem update --memory [exact_text] --to [target_context] (force one process-local Source Memory)",
        "mem update --from [source_context] --to [target_context] (compatibility aliases)",
        "mem update --from [source] --to [target] --goal [context|memory|text] "
        "(bind a non-evidence relevance focus through planning and Apply)",
        "mem update -r --from [source_context] --to [target_context] (both subtrees)",
        "mem update -r --from [source_context] --to [target_context] --target-root-only (Source subtree, target root)",
        "mem update --from [source_context] --source-descendants --to [target_context] --target-descendants (include both readable subtrees)",
        "mem update --from [source_context] (current Context is target)",
        "mem update --to [target_context] (current Context is source)",
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
    validate_help_translation_coverage(visible_names)

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
    ]
