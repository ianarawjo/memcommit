"""Present the top-level CLI command inventory."""

from __future__ import annotations

import shutil
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

import typer
from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.output.defaults import create_output
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.progress import CommandProgress
from memcommit.adapters.console.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.tui.core.keybindings import (
    NavigationAccelerator,
    bind_case_insensitive_key,
)
from memcommit.adapters.console.tui.core.text_layout import (
    pad_terminal_text,
    terminal_cell_width,
    wrap_terminal_text,
)
from memcommit.adapters.console.tui.components.frame import (
    bind_focused_frame_style,
    horizontal_rule,
)
from memcommit.adapters.console.text import (
    display_escape_text,
)
from memcommit.adapters.console.tui.components.focus import (
    FocusSurface,
    SurfaceFocusController,
)
from memcommit.adapters.console.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.application.operations.operation_catalog import (
    OperationComparisonDetail,
    OperationHelp,
    OperationTextDetail,
)
from memcommit.application.operations.help.application import list_operation_help
from memcommit.application.operations.help.composer import compose_operation_help
from memcommit.application.operations.help.lookup_application import (
    HelpLookupError,
    execute_help_lookup,
    prepare_help_lookup,
)
from memcommit.providers.operation_connections import connect_help_provider
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.providers.subscription import QueryProviderError
from memcommit.adapters.interfaces.tui.operations.help.localization import (
    HELP_LANGUAGES,
    HelpLanguage,
    category_description,
    common_key_description,
    common_locator_description,
    core_concept_description,
    operation_copy,
    validate_translation_coverage,
)
from memcommit.adapters.interfaces.tui.operations.help.study_copy_guard import (
    active_profile_is_study,
    authored_study_help_fields,
    find_study_help_copy_match,
)
from memcommit.persistence.command_ledger.study_actions import (
    record_study_help_lookup_completed,
    record_study_help_lookup_submitted,
)


COMMAND_ANNOTATIONS = {
    "config": "legacy",
    "eval": "legacy",
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
# owned forms so parser-validation and shell-prefill semantics stay explicit.
COMMAND_RELATED_FORMS = {}

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

HELP_CATEGORY_GROUPS = (
    (
        "BROWSE & NAVIGATE",
        (
            "status",
            "pwd",
            "contexts",
            "list",
            "show",
            "switch",
            "checkout",
            "rename",
        ),
    ),
    (
        "CREATE, COPY & CONNECT",
        (
            "init",
            "add",
            "copy",
            "branch",
            "import",
            "reference",
            "embed",
        ),
    ),
    (
        "SEARCH & EXPLAIN",
        (
            "find",
            "search",
            "query",
            "summarize",
        ),
    ),
    (
        "DETERMINISTIC CONTENT CHANGES",
        (
            "edit",
            "move",
            "replace",
            "chunk",
            "delete",
            "clear",
            "merge",
            "dedup",
        ),
    ),
    (
        "SEMANTIC TRANSFORMATIONS",
        (
            "atomize",
            "distill",
            "elaborate",
            "translate",
            "forget",
            "resolve",
            "dedun",
            "update",
            "meld",
            "sever",
        ),
    ),
    (
        "CHECK, COMPARE & REVIEW",
        (
            "compare",
            "find-duplicates",
            "find-redundancies",
            "find-ambiguities",
            "find-conflicts",
            "audit",
            "impact",
            "review",
            "fit",
            "check-conformance",
        ),
    ),
    (
        "GROUND WORKBENCH",
        ("ground",),
    ),
    (
        "HISTORY & RECOVERY",
        (
            "log",
            "diff",
            "trace",
            "rationale",
            "checkpoint",
            "undo",
            "redo",
            "revert",
        ),
    ),
    (
        "PROFILES",
        ("profile",),
    ),
    (
        "SHARING & PROTECTION",
        ("share", "lock", "unlock"),
    ),
    (
        "SYSTEM & STUDY TOOLS",
        ("help", "provider", "shell-init", "config", "init-study", "eval"),
    ),
)

# Category copy explains the user's intended activity. Execution labels remain
# concise orientation rather than a promise that every form has one route.
HELP_CATEGORY_DESCRIPTIONS = {
    "BROWSE & NAVIGATE": (
        "NO LLM",
        "Inspect the current location and available Contexts, then move through "
        "the Context namespace.",
    ),
    "CREATE, COPY & CONNECT": (
        "NO LLM",
        "Create Contexts or Memories, copy or import resources, or connect "
        "existing material.",
    ),
    "SEARCH & EXPLAIN": (
        "MIXED",
        "Find exact text directly, or use LLM-based semantic retrieval, answering, "
        "and summarization within the selected authorized scope.",
    ),
    "DETERMINISTIC CONTENT CHANGES": (
        "NO LLM",
        "Apply explicit inputs and reviewed choices through deterministic program "
        "logic to change content.",
    ),
    "SEMANTIC TRANSFORMATIONS": (
        "LLM-BASED",
        "Uses LLM semantic analysis to restructure, derive, translate, curate, or "
        "reconcile content.",
    ),
    "CHECK, COMPARE & REVIEW": (
        "MIXED",
        "Check compatibility, differences, quality, or expected impact. Review "
        "saved reports or evidence from operations that already completed.",
    ),
    "GROUND WORKBENCH": (
        "LLM-BASED",
        "Turn abstract ideas into reviewable common ground by developing a Goal, "
        "Rules, and example Memories together.",
    ),
    "HISTORY & RECOVERY": (
        "MIXED",
        "Inspect provenance and recorded changes. Restore an earlier state through "
        "explicit history operations.",
    ),
    "PROFILES": (
        "NO LLM",
        "Select and administer complete local Profile stores and their managed names.",
    ),
    "SHARING & PROTECTION": (
        "NO LLM",
        "Deliver owned Contexts and protect Memory, Context, or Profile writes.",
    ),
    "SYSTEM & STUDY TOOLS": (
        None,
        "Configure MemCommit and prepare or run study and evaluation utilities.",
    ),
}

HELP_CATEGORY_BY_COMMAND = {
    command_name: category
    for category, command_names in HELP_CATEGORY_GROUPS
    for command_name in command_names
}
HELP_CATEGORY_ORDER = {
    category: index for index, (category, _commands) in enumerate(HELP_CATEGORY_GROUPS)
}
HELP_COMMAND_ORDER = {
    command_name: command_index
    for _category, command_names in HELP_CATEGORY_GROUPS
    for command_index, command_name in enumerate(command_names)
}

COMMAND_FORMS = {
    "add": (
        'mem add "[memory_content]" (add one Memory to the current Context)',
        "mem add (open the interactive multi-Memory editor)",
        'mem add --memory "[memory_content]" --memory "[memory_content]" (add an explicit batch)',
        "mem add --input [file] (add one Memory per non-empty line)",
        "mem add --paste (paste one or more Memories)",
        'mem add "[memory_content]" --to [target_context] (add to an explicit Target)',
        "mem add --input [file] --to [target_context] (batch-add to an explicit Target)",
        "mem add --paste --to [target_context] (paste into an explicit Target)",
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
        "mem resolve (automatically apply one grounded full-frame plan, or show a non-applicable outcome)",
        "mem resolve [context] --plain (apply a grounded plan or print ASSUMED / ALREADY_FIT)",
        "mem resolve [context] [memory_uid] (auto-classify one Context and optional edit restrictions)",
        "mem resolve [context] --memory [memory_uid] (explicitly accept a short Memory prefix)",
        "mem resolve [context]:[memory_uid] (bind one Memory restriction to its exact Context)",
        "mem resolve --context [context] --no-create (limit the automatic plan to existing-Memory edits)",
        'mem resolve --context [context] --allow-delete --guidance "[grounds]" (exceptionally permit grounded retirement)',
        "mem resolve --context [context] --candidate [full_id] --expected-revision [revision] --apply (replay an externally reviewed exact plan)",
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
        "mem atomize [target] (auto-type one Context or direct Memory)",
        "mem atomize --context [context] (compatibility alias)",
        "mem atomize --sessions (enter the interactive Atomize session launcher)",
        'mem atomize --evaluate "[issue]" (directional atomic review)',
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
        "mem diff (select a Context, then inspect its checkpoints)",
        "mem diff [context] (inspect that Context's checkpoints directly)",
        "mem diff --raw (exact unified diff)",
        "mem diff --stat (summary only)",
        "mem diff --verbose (complete UIDs and source/target fingerprints)",
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
    "elaborate": (
        "mem elaborate (elaborate current direct Memories as Rules and add Cases to current)",
        "mem elaborate --from [source] --to [target] (explicit existing endpoints)",
        "mem elaborate --from [source] --as goal (treat its one direct Memory as a Goal)",
        "mem elaborate --goal [context|memory|text] "
        "(use it as Goal Source and add candidate Rules to current)",
        'mem elaborate --rule "[rule]" --to [target] (add concrete Cases)',
        'mem elaborate --rule "[rule1]" --rule "[rule2]" '
        "(add concrete Cases across explicit Rules to current)",
        "mem elaborate --ground [name] --from-goal "
        "(use the exact Ground Goal through the same application)",
        "mem elaborate --ground [name] --from-rules "
        "(use the exact active Ground Rules through the same application)",
        "mem elaborate --ground [name] --from-goal --adopt "
        "(atomically add the complete proposal to physical /rules)",
        "mem elaborate --ground [name] --from-rules --adopt "
        "(atomically add the complete proposal to physical /examples)",
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
        'mem replace "[text]" "[replacement]" --tui (edit the complete request in the compact Replace form)',
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
    "eval": (
        "mem eval semantic status (show retained semantic campaign status)",
        "mem eval semantic run [campaign] (run a semantic evaluation campaign)",
    ),
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
        "mem search (interactive semantic search, checked COPY/REFERENCE, and Save Location)",
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
        "mem ground (enter the interactive Ground session)",
        "mem ground [ground_name] (enter an interactive named Ground session)",
        'mem ground "[request]" (enter an interactive Ground session with an initial request)',
        'mem ground --request "[request]" (enter an interactive Ground session with an initial request)',
        "mem ground --sessions (enter the interactive Ground session launcher; TTY required)",
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
        "mem impact elaborate --from [source] --to [target] (preview the Memories Elaborate would add)",
        "mem impact resolve --context [context] (preview one automatic full-frame interpretation plan)",
        "mem impact resolve --context [context] --candidate [full_id] (preview its exact effect set)",
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
        "mem list --copy (copy and stage the current listing)",
        "mem list [context] --copy (copy and stage an explicit listing)",
        "mem list --paste (reopen the copied result)",
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
        "mem rationale (open Recents or select a Memory from the current readable Context)",
        "mem rationale [memory_selector] (explain one current or historical Memory)",
        "mem rationale --context [context] (start Memory selection in one readable Context)",
        "mem rationale [memory_selector] --context [context] (explicit Context and Memory)",
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
        "mem review audit (open a saved three-finder Audit)",
        "mem review compare (open a saved Compare report)",
        "mem review meld (open terminal evidence for an applied Meld)",
        "mem review sever (open terminal evidence for an applied Sever)",
        "mem review update (open terminal evidence for an applied Update)",
        "mem review [kind] --session [uid] (exact Audit, Compare, Meld, Sever, or Update artifact)",
        "mem review atomize (open the current Context's applied Atomize evidence)",
        "mem review atomize --context [context] (Context-bound applied Atomize evidence)",
        "mem review dedun|distill|elaborate|forget|resolve --receipt [uid] (open exact applied checkpoint evidence)",
        "mem review ambiguities (analyze current-Context ambiguities)",
        "mem review ambiguities --context [context] (Context-bound Ambiguity review)",
    ),
    "sever": (
        "mem sever (choose Source, Criteria, and Result for a new Sever)",
        "mem sever --sessions (enter the interactive Sever session launcher)",
        "mem sever [source_context] [criteria_context] (self-save into Source)",
        "mem sever [source_context] [criteria_context] [fresh_result_context] (save as a separate Result)",
        "mem sever [source_context] [criteria_context] [result_context] -r",
        "mem sever [source_context] [criteria_context] [result_context] -r --source-root-only",
        "mem sever --source [source] --criteria [criteria] --save-as [result] (compatibility aliases)",
        "mem sever --from [source] --against [criteria] --to [result] (directional aliases)",
        "mem sever --criteria [criteria_context] (current Context is Source and self-save target)",
        "mem sever --resume [uid] (open an exact saved Sever session)",
    ),
    "share": (
        "mem share (enter the interactive Share setup)",
        "mem share [source_context] (enter the interactive endpoint selector)",
        "mem share --to [endpoint] (enter the interactive Source selector)",
        "mem share [source_context] --to [endpoint] (explicit delivery)",
    ),
    "shell-init": (
        "mem shell-init (print zsh integration)",
        "mem shell-init zsh (explicit equivalent)",
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
        "mem summarize --tui (choose a Recent report or readable Context and range)",
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
        "mem trace (open Recents or select a Memory from the current Context)",
        "mem trace [memory_selector] (interactively inspect the lineage printed by mem log --memory)",
        "mem trace --context [context] (start Memory selection in one local Context)",
        "mem trace [memory_selector] --context [context] (explicit Context and Memory)",
        "mem trace [memory_selector] --plain (print the bounded lineage "
        "document instead of opening its read-only Viewer)",
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
    operation_help: OperationHelp | None = None
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
    validate_translation_coverage(visible_names)

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


def _entry_label(entry: CommandEntry) -> str:
    label = entry.name
    if entry.aliases:
        label += f" ({', '.join(entry.aliases)})"
    if entry.annotation:
        label += f" ({entry.annotation})"
    if entry.maturity:
        label += f" [{entry.maturity}]"
    return label


_HELP_SPLIT_COMMAND_LABEL_MIN = 14


def _entry_label_lines(entry: CommandEntry) -> tuple[str, ...]:
    """Project one exact command label into at most two display-only rows."""

    suffixes: list[str] = []
    if entry.aliases:
        suffixes.append(f"({', '.join(entry.aliases)})")
    if entry.annotation:
        suffixes.append(f"({entry.annotation})")
    if entry.maturity:
        suffixes.append(f"[{entry.maturity}]")
    if suffixes:
        return entry.name, " ".join(suffixes)
    if len(entry.name) >= _HELP_SPLIT_COMMAND_LABEL_MIN and "-" in entry.name:
        head, tail = entry.name.rsplit("-", 1)
        if head and tail:
            return head + "-", tail
    return (entry.name,)


def _entry_line(
    entry: CommandEntry,
    *,
    name_width: int,
) -> str:
    label = _entry_label(entry)
    return f"{label:<{name_width}} - {entry.description}"


_HELP_USE_WHEN_LABEL = "WHEN"
_HELP_USE_WHEN_PREFIX = _HELP_USE_WHEN_LABEL + " · "


def _wrap_prefixed_terminal_text(
    prefix: str,
    value: str,
    *,
    width: int,
) -> list[str]:
    """Wrap translated prose after one stable terminal-cell prefix."""

    prefix_width = terminal_cell_width(prefix)
    value_width = max(1, width - prefix_width)
    value_lines = wrap_terminal_text(display_escape_text(value), value_width)
    continuation = " " * prefix_width
    return [
        (prefix if index == 0 else continuation) + line
        for index, line in enumerate(value_lines)
    ]


def _help_command_rows(
    entry: CommandEntry,
    *,
    command_prefixes: tuple[str, ...],
    content_width: int,
    language: HelpLanguage = "EN",
) -> list[tuple[str, str, str, int | None]]:
    """Project one command as a connected Description/When record."""

    prefix_width = terminal_cell_width(command_prefixes[0])
    if any(terminal_cell_width(prefix) != prefix_width for prefix in command_prefixes):
        raise ValueError("Help command prefixes must share one display width.")
    # The two-cell connector belongs to the record rather than either text
    # column. This preserves the previous row count while making the command,
    # description, and use case read as one connected unit.
    connector_width = 2
    body_width = max(1, content_width - prefix_width - connector_width)
    english_use_when = (
        "" if entry.operation_help is None else entry.operation_help.best_for
    )
    localized = operation_copy(
        language,
        entry.name,
        english_description=entry.description,
        english_use_when=english_use_when,
    )
    summary_lines = wrap_terminal_text(
        display_escape_text(localized.description),
        body_width,
    )
    body_rows: list[tuple[str, int | None, bool]] = [
        (pad_terminal_text(line, body_width), None, False) for line in summary_lines
    ]
    if not localized.use_when:
        best_for_lines: list[str] = []
    else:
        best_for_lines = _wrap_prefixed_terminal_text(
            _HELP_USE_WHEN_PREFIX,
            localized.use_when,
            width=body_width,
        )
        body_rows.extend(
            (
                pad_terminal_text(line, body_width),
                0 if index == 0 else None,
                True,
            )
            for index, line in enumerate(best_for_lines)
        )

    row_count = max(len(body_rows), len(command_prefixes))
    semantic_row_count = len(body_rows)
    has_when = any(is_when for _body, _offset, is_when in body_rows)

    def connector(index: int) -> str:
        if index >= semantic_row_count:
            return " " * connector_width
        if not has_when:
            return "─ " if index == 0 else " " * connector_width
        if index == 0:
            return "┬ "
        if body_rows[index][2] and not body_rows[index - 1][2]:
            return "└ "
        if body_rows[index][2]:
            return " " * connector_width
        return "│ "

    return [
        (
            (
                command_prefixes[index]
                if index < len(command_prefixes)
                else " " * prefix_width
            ),
            connector(index),
            body_rows[index][0] if index < semantic_row_count else " " * body_width,
            body_rows[index][1] if index < semantic_row_count else None,
        )
        for index in range(row_count)
    ]


def _render_plain_inventory(entries: list[CommandEntry]) -> None:
    typer.secho("mem command inventory", bold=True)
    typer.echo()

    name_width = max(len(_entry_label(entry)) for entry in entries)
    for entry in entries:
        typer.echo(
            _entry_line(
                entry,
                name_width=name_width,
            )
        )


def render_help_lookup_entries(
    entries: list[CommandEntry],
    *,
    content_width: int = 100,
    language: HelpLanguage = "EN",
) -> str:
    """Render only matched operations as their existing collapsed Help rows."""

    if not entries:
        return "No Help candidates available."
    width = max(40, content_width)
    rendered: list[str] = []
    for entry in entries:
        rows = _help_command_rows(
            entry,
            command_prefixes=(f"mem {entry.name} ",),
            content_width=width,
            language=language,
        )
        rendered.append(
            "\n".join(
                (prefix + connector + body).rstrip()
                for prefix, connector, body, _label_offset in rows
            )
        )
    return "\n\n".join(rendered)


def _help_group_fragments(
    entries: list[tuple[int, CommandEntry]],
    *,
    title: str,
    width: int,
    focused: bool,
    selected_index: int,
    expanded_index: int | None,
    selected_form: int | None,
    viewport_height: int | None = None,
    language: HelpLanguage = "EN",
) -> list[tuple[str, str]]:
    """Render one discovery kind and its command records in a single box."""
    if not entries:
        return []
    width = max(36, width)
    inner_width = width - 2
    content_width = inner_width - 2
    title_label = f" {display_escape_text(title)} "[:inner_width]
    border_style = "class:help-group.focused" if focused else "class:help-group"
    horizontal = "━" if focused else "─"
    fragments: list[tuple[str, str]] = [
        (border_style, "┏" if focused else "┌"),
        (border_style + " bold", title_label),
        (
            border_style,
            horizontal * max(0, inner_width - len(title_label))
            + ("┓" if focused else "┐")
            + "\n",
        ),
    ]
    vertical = "┃" if focused else "│"
    category_copy = HELP_CATEGORY_DESCRIPTIONS.get(title)
    if category_copy is not None:
        classification, description = category_copy
        prefix = f"{classification} · " if classification is not None else ""
        lines = _wrap_prefixed_terminal_text(
            prefix,
            category_description(
                language,
                title,
                description,
            ),
            width=content_width,
        )
        for line in lines:
            fragments.extend([(border_style, vertical), ("", " ")])
            fragments.append(("class:help-category-description bold", line))
            fragments.extend(
                [
                    (
                        "",
                        " " * (content_width - terminal_cell_width(line) + 1),
                    ),
                    (border_style, vertical + "\n"),
                ]
            )
    label_lines = {
        index: tuple(display_escape_text(line) for line in _entry_label_lines(entry))
        for index, entry in entries
    }
    for index, entry in entries:
        expanded = index == expanded_index
        owns_selection = index == selected_index
        command_focused = focused and owns_selection and selected_form is None
        marker = "▾" if expanded else "▸"
        first_label = label_lines[index][0]
        # Each operation owns its junction. Keeping it next to that operation
        # prevents a category-wide prose column from visually overpowering the
        # command list. A display-only continuation still reserves enough
        # left-side width, but the branch always begins on the first row.
        connector_name_width = max(len(line) for line in label_lines[index])
        first_command_prefix = f"{marker} mem {first_label} " + "─" * (
            connector_name_width - len(first_label) + 1
        )
        # Four cells keeps a continuation visibly subordinate while pulling it
        # two cells left of the old post-"mem " alignment. Pad on the right so
        # every label row still reaches the first-row junction.
        continuation_indent = " " * 4
        command_prefixes = (
            first_command_prefix,
            *(
                pad_terminal_text(
                    continuation_indent + line,
                    terminal_cell_width(first_command_prefix),
                )
                for line in label_lines[index][1:]
            ),
        )
        for prefix, connector, body, label_offset in _help_command_rows(
            entry,
            command_prefixes=command_prefixes,
            content_width=content_width,
            language=language,
        ):
            fragments.append((border_style, vertical))
            body_style = "class:help-command.selected" if command_focused else ""
            prefix_style = (
                "class:help-command.selected bold"
                if command_focused
                else "class:help-command"
            )
            fragments.append((prefix_style, f" {prefix}"))
            connector_style = body_style if command_focused else "class:help-connector"
            fragments.append((connector_style, connector))
            if label_offset is None:
                fragments.append((body_style, f"{body} "))
            else:
                label = _HELP_USE_WHEN_LABEL
                label_end = label_offset + len(label)
                fragments.extend(
                    [
                        (body_style, body[:label_offset]),
                        (body_style, body[label_offset:label_end]),
                        (body_style, body[label_end:] + " "),
                    ]
                )
            fragments.append((border_style, vertical + "\n"))
        if command_focused:
            # Anchor after the complete connected record. Prompt-toolkit only
            # guarantees visibility through the cursor row; anchoring before
            # a two-line record let the final WHEN row (and the closing border
            # after `mem eval`) fall below the viewport at the end of Help.
            fragments.append(("[SetCursorPosition]", ""))
        if expanded:
            if entry.operation_help is not None:
                composed = compose_operation_help(
                    entry.operation_help,
                    cli_forms=entry.forms,
                )
                detail_label_width = max(len(row.label) for row in composed.overview)
                for row in composed.overview:
                    # The use case is already visible in every command row,
                    # even before expansion; do not duplicate it in the detail.
                    if row.label == "BEST FOR":
                        continue
                    prefix = f"  {row.label:<{detail_label_width}} · "
                    lines = textwrap.wrap(
                        display_escape_text(row.value),
                        width=content_width,
                        initial_indent=prefix,
                        subsequent_indent=" " * len(prefix),
                        break_long_words=True,
                        break_on_hyphens=False,
                    ) or [prefix]
                    for line in lines:
                        fragments.extend(
                            [
                                (border_style, vertical),
                                (
                                    "",
                                    f" {line:<{content_width}} ",
                                ),
                                (border_style, vertical + "\n"),
                            ]
                        )
            details = (
                () if entry.operation_help is None else entry.operation_help.details
            )
            for detail in details:
                detail_lines: list[tuple[str, str]] = []
                title_prefix = "  "
                for line in textwrap.wrap(
                    display_escape_text(detail.title),
                    width=content_width,
                    initial_indent=title_prefix,
                    subsequent_indent=title_prefix,
                    break_long_words=True,
                    break_on_hyphens=False,
                ) or [title_prefix]:
                    detail_lines.append(("bold", line))
                if isinstance(detail, OperationComparisonDetail):
                    for line in textwrap.wrap(
                        display_escape_text(detail.explanation),
                        width=content_width,
                        initial_indent="  ",
                        subsequent_indent="  ",
                        break_long_words=True,
                        break_on_hyphens=False,
                    ) or ["  "]:
                        detail_lines.append(("", line))
                    for option in detail.options:
                        # Terminal Help uses a literal hyphen rather than relying on
                        # renderer-specific Markdown bullet projection.
                        value = f"{option.label} · {option.guidance}"
                        for line in textwrap.wrap(
                            display_escape_text(value),
                            width=content_width,
                            initial_indent="  - ",
                            subsequent_indent="    ",
                            break_long_words=True,
                            break_on_hyphens=False,
                        ) or ["  -"]:
                            detail_lines.append(("", line))
                elif isinstance(detail, OperationTextDetail):
                    for line in textwrap.wrap(
                        display_escape_text(detail.body),
                        width=content_width,
                        initial_indent="  ",
                        subsequent_indent="  ",
                        break_long_words=True,
                        break_on_hyphens=False,
                    ) or ["  "]:
                        detail_lines.append(("", line))
                else:  # pragma: no cover - catalog validation closes the union
                    raise TypeError("Unsupported Operation Help detail type.")
                for style, line in detail_lines:
                    fragments.extend(
                        [
                            (border_style, vertical),
                            (style, f" {line:<{content_width}} "),
                            (border_style, vertical + "\n"),
                        ]
                    )
            for form_index, form in enumerate(entry.forms):
                form_focused = (
                    focused and owns_selection and selected_form == form_index
                )
                prefix = f"  FORM {form_index + 1} · "
                lines = textwrap.wrap(
                    display_escape_text(form),
                    width=content_width,
                    initial_indent=prefix,
                    subsequent_indent=" " * len(prefix),
                    break_long_words=True,
                    break_on_hyphens=False,
                ) or [prefix]
                for line in lines:
                    fragments.extend(
                        [
                            (border_style, vertical),
                            (
                                "class:selected" if form_focused else "class:form",
                                f" {line:<{content_width}} ",
                            ),
                            (border_style, vertical + "\n"),
                        ]
                    )
                if form_focused:
                    # Wrapped Forms follow the same whole-record visibility
                    # rule as collapsed commands.
                    fragments.append(("[SetCursorPosition]", ""))
    if viewport_height is not None:
        # A–Z owns one box, so keep spare viewport rows inside that box instead
        # of implying that more unboxed content exists below the final command.
        rendered_rows = sum(text.count("\n") for _style, text in fragments)
        blank_rows = max(0, viewport_height - rendered_rows - 1)
        for _row in range(blank_rows):
            fragments.extend(
                [
                    (border_style, vertical),
                    ("", " " * inner_width),
                    (border_style, vertical + "\n"),
                ]
            )
    fragments.append(
        (
            border_style,
            ("┗" if focused else "└")
            + horizontal * inner_width
            + ("┛" if focused else "┘")
            + ("" if viewport_height is not None else "\n"),
        )
    )
    return fragments


def _help_group_width(terminal_columns: int) -> int:
    """Use the complete Help viewport except its one-column scrollbar."""
    return max(36, terminal_columns - 1)


def _help_list_viewport_height(terminal_rows: int) -> int:
    """Return rows left after Help's fixed header, controls, rule, and footer."""

    return max(2, terminal_rows - 9)


def _help_information_box_fragments(
    *,
    width: int,
    by_kind: bool,
    focused_concept_index: int | None = None,
    focused: bool = False,
    language: HelpLanguage = "EN",
) -> list[tuple[str, str]]:
    """Render the BY KIND primer as focusable concepts plus key reference."""
    if not by_kind:
        return []
    width = max(36, width)
    inner_width = width - 2
    content_width = inner_width - 2
    guide_focused = focused and focused_concept_index is not None
    border_style = (
        "class:help-guide.border.focused"
        if guide_focused
        else "class:help-guide.border"
    )
    label_style = "class:help-guide.label"
    fragments: list[tuple[str, str]] = []

    def border(title: str, *, middle: bool) -> None:
        title_label = f" {title} "[:inner_width]
        if guide_focused:
            left, right = ("┣", "┫") if middle else ("┏", "┓")
        else:
            left, right = ("├", "┤") if middle else ("┌", "┐")
        horizontal = "━" if guide_focused else "─"
        fragments.append(
            (
                border_style,
                left
                + title_label
                + horizontal * max(0, inner_width - len(title_label))
                + right
                + "\n",
            )
        )

    def rows(
        items: tuple[tuple[str, str], ...],
        *,
        selectable: bool,
        label_styles: dict[str, str] | None = None,
    ) -> None:
        label_width = max(terminal_cell_width(label) for label, _description in items)
        for item_index, (label, description) in enumerate(items):
            row_focused = selectable and focused and focused_concept_index == item_index
            prefix = pad_terminal_text(label, label_width) + "  "
            lines = wrap_terminal_text(
                display_escape_text(description),
                max(1, content_width - terminal_cell_width(prefix)),
            )
            for line_index, line in enumerate(lines):
                if row_focused and line_index == 0:
                    fragments.append(("[SetCursorPosition]", ""))
                row_prefix = prefix if line_index == 0 else " " * len(prefix)
                padding = " " * max(
                    0,
                    content_width
                    - terminal_cell_width(row_prefix)
                    - terminal_cell_width(line),
                )
                fragments.extend(
                    [
                        (border_style, "┃" if guide_focused else "│"),
                        (
                            (
                                "class:selected" if row_focused else "",
                                " " + row_prefix + line + padding + " ",
                            )
                            if row_focused
                            else ("", " ")
                        ),
                    ]
                )
                if not row_focused:
                    fragments.extend(
                        [
                            (
                                (
                                    (label_styles or {}).get(label, label_style)
                                    if line_index == 0
                                    else ""
                                ),
                                row_prefix,
                            ),
                            ("", line + padding + " "),
                        ]
                    )
                fragments.append((border_style, ("┃" if guide_focused else "│") + "\n"))

    border("CORE CONCEPTS", middle=False)
    rows(
        tuple(
            (
                label,
                core_concept_description(language, label, description),
            )
            for label, description in HELP_CORE_CONCEPTS
        ),
        selectable=True,
        label_styles=HELP_CORE_CONCEPT_STYLES,
    )
    border("COMMON LOCATORS", middle=True)
    rows(
        tuple(
            (
                locator,
                common_locator_description(language, locator, description),
            )
            for locator, description in HELP_COMMON_LOCATORS
        ),
        selectable=False,
    )
    border("COMMON KEYS", middle=True)
    rows(
        tuple(
            (
                key,
                common_key_description(language, key, description),
            )
            for key, description in HELP_COMMON_KEYS
        ),
        selectable=False,
    )
    fragments.append(
        (
            border_style,
            ("┗" if guide_focused else "└")
            + ("━" if guide_focused else "─") * inner_width
            + ("┛" if guide_focused else "┘")
            + "\n",
        )
    )
    return fragments


def _ordered_help_entries(
    entries: list[CommandEntry],
    *,
    by_kind: bool,
) -> list[CommandEntry]:
    """Keep workflow order for kinds and reserve lexical order for A–Z."""
    if not by_kind:
        return sorted(entries, key=lambda entry: (entry.name.casefold(), entry.name))
    return sorted(
        entries,
        key=lambda entry: (
            HELP_CATEGORY_ORDER.get(
                HELP_CATEGORY_BY_COMMAND.get(entry.name, "OTHER"),
                len(HELP_CATEGORY_ORDER),
            ),
            HELP_COMMAND_ORDER.get(entry.name, 0),
            entry.name.casefold(),
            entry.name,
        ),
    )


def _help_section_heading_fragments(
    *,
    title: str,
    width: int,
) -> list[tuple[str, str]]:
    """Mark a semantic section without nesting the category frames below it."""

    width = max(36, width)
    displayed = display_escape_text(title)[:width]
    return [("class:category", displayed + " " * (width - len(displayed)) + "\n")]


def run_help_selector(
    entries: list[CommandEntry],
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    mode: Literal["SELECT", "EXPLORE"] = "SELECT",
    status_supplier: Callable[[], str] | None = None,
    on_explore_action: Callable[[str, str | None], None] | None = None,
    on_ready: Callable[[], None] | None = None,
    explore_title: str = "mem help · explore while work continues",
    explore_return_label: str = "waiting",
) -> HelpSelection | None:
    """Select a command, or browse the same inventory without shell effects."""
    if not entries:
        return None
    if mode not in {"SELECT", "EXPLORE"}:
        raise ValueError("Help mode must be SELECT or EXPLORE.")
    if not explore_title.strip() or not explore_return_label.strip():
        raise ValueError("Help exploration labels must be nonblank.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive help requires a terminal.")
    language_state = HorizontalChoiceState(
        tuple(
            HorizontalChoiceOption(language, language) for language in HELP_LANGUAGES
        ),
        selected_uid="EN",
    )
    view_state = HorizontalChoiceState(
        (
            HorizontalChoiceOption("CATEGORY", "BY KIND"),
            HorizontalChoiceOption("A_Z", "A–Z"),
        ),
        selected_uid="CATEGORY",
    )

    def ordered_entries() -> list[CommandEntry]:
        return _ordered_help_entries(
            entries,
            by_kind=view_state.selected_uid == "CATEGORY",
        )

    visible_entries = {"value": ordered_entries()}
    selected_index = {"value": 0}
    selected_concept_index: dict[str, int | None] = {"value": None}
    expanded_index: dict[str, int | None] = {"value": None}
    selected_form: dict[str, int | None] = {"value": None}
    category_cursors: dict[str, int] = {}
    bindings = KeyBindings()
    navigation_accelerator = NavigationAccelerator()
    app_ref: dict[str, Application[HelpSelection | None]] = {}

    def emit_explore_action(action: str, command_name: str | None = None) -> None:
        if mode == "EXPLORE" and on_explore_action is not None:
            on_explore_action(action, command_name)

    def selected_language() -> HelpLanguage:
        return language_state.selected_uid  # type: ignore[return-value]

    def select_language(delta: int) -> None:
        """Change only process-local Help prose; never mutate study data."""

        if language_state.move(delta):
            emit_explore_action("LANGUAGE", language_state.selected_uid)

    def select_view(delta: int) -> None:
        selected_name = visible_entries["value"][selected_index["value"]].name
        if not view_state.move(delta):
            return
        visible_entries["value"] = ordered_entries()
        selected_index["value"] = next(
            index
            for index, entry in enumerate(visible_entries["value"])
            if entry.name == selected_name
        )
        expanded_index["value"] = None
        selected_form["value"] = None
        selected_concept_index["value"] = None

    def concept_focus_active() -> bool:
        return (
            view_state.selected_uid == "CATEGORY"
            and selected_concept_index["value"] is not None
        )

    def visible_groups() -> list[tuple[str, list[tuple[int, CommandEntry]]]]:
        """Project the current rows into the same boxes the renderer shows."""

        indexed_entries = list(enumerate(visible_entries["value"]))
        if view_state.selected_uid != "CATEGORY":
            return [("A–Z", indexed_entries)]
        groups: list[tuple[str, list[tuple[int, CommandEntry]]]] = []
        for index, entry in indexed_entries:
            category = HELP_CATEGORY_BY_COMMAND.get(entry.name, "OTHER")
            if not groups or groups[-1][0] != category:
                groups.append((category, []))
            groups[-1][1].append((index, entry))
        return groups

    def selected_group_index(
        groups: list[tuple[str, list[tuple[int, CommandEntry]]]],
    ) -> int | None:
        if concept_focus_active():
            return None
        selected = selected_index["value"]
        return next(
            (
                group_index
                for group_index, (_title, rows) in enumerate(groups)
                if any(index == selected for index, _entry in rows)
            ),
            None,
        )

    def focus_group(
        group: tuple[str, list[tuple[int, CommandEntry]]],
    ) -> None:
        """Enter one visible kind at its last retained command cursor."""

        title, rows = group
        row_indexes = {index for index, _entry in rows}
        retained = category_cursors.get(title)
        selected_index["value"] = retained if retained in row_indexes else rows[0][0]
        selected_concept_index["value"] = None
        expanded_index["value"] = None
        selected_form["value"] = None

    def move_tab(event, direction: int) -> None:
        """Traverse VIEW and every visible BY KIND box in screen order."""

        navigation_accelerator.reset()
        if view_state.selected_uid != "CATEGORY":
            surface_focus.focus_relative(event.app, direction, wrap=True)
            event.app.invalidate()
            return

        groups = visible_groups()
        if event.app.layout.has_focus(language_control):
            if direction > 0:
                event.app.layout.focus(view_control)
            else:
                focus_group(groups[-1])
                event.app.layout.focus(list_control)
            event.app.invalidate()
            return
        if event.app.layout.has_focus(view_control):
            if direction < 0:
                event.app.layout.focus(language_control)
            else:
                focus_group(groups[0])
                event.app.layout.focus(list_control)
            event.app.invalidate()
            return

        group_index = selected_group_index(groups)
        if group_index is not None:
            title, _rows = groups[group_index]
            category_cursors[title] = selected_index["value"]
        target_index = (
            0
            if group_index is None and direction > 0
            else group_index + direction
            if group_index is not None
            else -1
        )
        if 0 <= target_index < len(groups):
            focus_group(groups[target_index])
        else:
            expanded_index["value"] = None
            selected_form["value"] = None
            surface_focus.focus_relative(
                event.app,
                direction,
                # VIEW is declared before the scrolling list, so moving
                # forward from the final kind crosses the layout boundary by
                # wrapping once; reverse movement reaches VIEW directly.
                wrap=True,
            )
        event.app.invalidate()

    def render_entries():
        fragments: list[tuple[str, str]] = []
        app = app_ref.get("app")
        list_focused = app is not None and app.layout.has_focus(list_control)
        terminal_columns = app.output.get_size().columns if app is not None else 80
        terminal_rows = app.output.get_size().rows if app is not None else 24
        card_width = _help_group_width(terminal_columns)
        by_kind = view_state.selected_uid == "CATEGORY"
        fragments.extend(
            _help_information_box_fragments(
                width=card_width,
                by_kind=by_kind,
                focused_concept_index=selected_concept_index["value"],
                focused=list_focused,
                language=selected_language(),
            )
        )
        if fragments:
            fragments.append(("", "\n"))
        fragments.extend(
            _help_section_heading_fragments(
                title="OPERATIONS",
                width=card_width,
            )
        )
        groups = visible_groups()
        for group_index, (title, group_entries) in enumerate(groups):
            group_focused = (
                list_focused
                and any(
                    index == selected_index["value"] for index, _entry in group_entries
                )
                and not concept_focus_active()
            )
            fragments.extend(
                _help_group_fragments(
                    group_entries,
                    title=title,
                    width=card_width,
                    focused=group_focused,
                    selected_index=selected_index["value"],
                    expanded_index=expanded_index["value"],
                    selected_form=selected_form["value"],
                    viewport_height=(
                        None if by_kind else _help_list_viewport_height(terminal_rows)
                    ),
                    language=selected_language(),
                )
            )
            if group_index < len(groups) - 1:
                fragments.append(("", "\n"))
        return fragments

    list_control = FormattedTextControl(
        text=render_entries,
        focusable=True,
        show_cursor=False,
    )
    language_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            language_state,
            title="LANGUAGE",
            focused=(
                app_ref.get("app") is not None
                and app_ref["app"].layout.has_focus(language_control)
            ),
            inline_boxed=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    view_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            view_state,
            title="VIEW",
            focused=(
                app_ref.get("app") is not None
                and app_ref["app"].layout.has_focus(view_control)
            ),
            inline_boxed=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    surface_focus = SurfaceFocusController(
        (
            FocusSurface("language", language_control),
            FocusSurface("view", view_control),
            FocusSurface("commands", list_control),
        )
    )

    def move_one(direction: int) -> None:
        concept_index = selected_concept_index["value"]
        if concept_focus_active() and concept_index is not None:
            candidate = concept_index + direction
            if candidate >= len(HELP_CORE_CONCEPTS):
                selected_concept_index["value"] = None
                selected_index["value"] = 0
            else:
                selected_concept_index["value"] = max(0, candidate)
            return
        form_index = selected_form["value"]
        if form_index is not None:
            forms = visible_entries["value"][selected_index["value"]].forms
            candidate = form_index + direction
            if candidate < 0:
                selected_form["value"] = None
            elif candidate < len(forms):
                selected_form["value"] = candidate
            else:
                selected_form["value"] = None
                expanded_index["value"] = None
                selected_index["value"] = min(
                    selected_index["value"] + 1,
                    len(visible_entries["value"]) - 1,
                )
            return
        if (
            direction < 0
            and selected_index["value"] == 0
            and view_state.selected_uid == "CATEGORY"
        ):
            expanded_index["value"] = None
            selected_concept_index["value"] = len(HELP_CORE_CONCEPTS) - 1
            return
        previous = selected_index["value"]
        selected_index["value"] = max(
            0,
            min(
                selected_index["value"] + direction,
                len(visible_entries["value"]) - 1,
            ),
        )
        if selected_index["value"] != previous:
            expanded_index["value"] = None

    @bindings.add("down", filter=has_focus(list_control))
    def _next_command(event) -> None:
        navigation_accelerator.move(
            1,
            app=event.app,
            move_one=move_one,
        )

    @bindings.add("up", filter=has_focus(list_control))
    def _previous_command(event) -> None:
        if concept_focus_active() and selected_concept_index["value"] == 0:
            navigation_accelerator.reset()
            surface_focus.focus_relative(
                event.app,
                -1,
                wrap=False,
            )
            event.app.invalidate()
            return
        if (
            selected_index["value"] == 0
            and selected_form["value"] is None
            and view_state.selected_uid != "CATEGORY"
        ):
            navigation_accelerator.reset()
            surface_focus.focus_relative(
                event.app,
                -1,
                wrap=False,
            )
            event.app.invalidate()
            return
        navigation_accelerator.move(
            -1,
            app=event.app,
            move_one=move_one,
        )

    @bindings.add("pagedown", filter=has_focus(list_control))
    def _next_page(event) -> None:
        navigation_accelerator.reset()
        selected_form["value"] = None
        expanded_index["value"] = None
        concept_count = (
            len(HELP_CORE_CONCEPTS) if view_state.selected_uid == "CATEGORY" else 0
        )
        position = (
            selected_concept_index["value"]
            if concept_focus_active()
            else concept_count + selected_index["value"]
        )
        target = min(
            int(position) + 10,
            concept_count + len(visible_entries["value"]) - 1,
        )
        if target < concept_count:
            selected_concept_index["value"] = target
        else:
            selected_concept_index["value"] = None
            selected_index["value"] = target - concept_count
        event.app.invalidate()

    @bindings.add("pageup", filter=has_focus(list_control))
    def _previous_page(event) -> None:
        navigation_accelerator.reset()
        selected_form["value"] = None
        expanded_index["value"] = None
        concept_count = (
            len(HELP_CORE_CONCEPTS) if view_state.selected_uid == "CATEGORY" else 0
        )
        position = (
            selected_concept_index["value"]
            if concept_focus_active()
            else concept_count + selected_index["value"]
        )
        target = max(int(position) - 10, 0)
        if target < concept_count:
            selected_concept_index["value"] = target
        else:
            selected_concept_index["value"] = None
            selected_index["value"] = target - concept_count
        event.app.invalidate()

    @bindings.add("home", filter=has_focus(list_control))
    def _first_command(event) -> None:
        navigation_accelerator.reset()
        selected_form["value"] = None
        expanded_index["value"] = None
        if view_state.selected_uid == "CATEGORY":
            selected_concept_index["value"] = 0
        else:
            selected_index["value"] = 0
        event.app.invalidate()

    @bindings.add("end", filter=has_focus(list_control))
    def _last_command(event) -> None:
        navigation_accelerator.reset()
        selected_form["value"] = None
        expanded_index["value"] = None
        selected_concept_index["value"] = None
        selected_index["value"] = len(visible_entries["value"]) - 1
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(list_control))
    def _select_row(event) -> None:
        navigation_accelerator.reset()
        if concept_focus_active():
            return
        index = selected_index["value"]
        form_index = selected_form["value"]
        if form_index is None:
            # Keep the first Enter inside the browser. If it returned to zsh,
            # a user's second confirmation Enter could execute a placeholder
            # template before they had a chance to edit it.
            expanded_index["value"] = index
            selected_form["value"] = 0
            emit_explore_action(
                "EXPAND",
                visible_entries["value"][index].name,
            )
            event.app.invalidate()
            return
        entry = visible_entries["value"][index]
        if mode == "EXPLORE":
            # A waiting Help session is a read-only learning surface. Enter
            # may inspect a form, but it must never return a shell template or
            # execute a second command while the frozen operation is running.
            emit_explore_action("FORM", entry.name)
            event.app.invalidate()
            return
        command_line = _selectable_form_line(entry.forms[form_index])
        event.app.exit(
            result=HelpSelection(
                command_name=entry.name,
                command_line=command_line,
            )
        )

    @bindings.add("right", filter=has_focus(list_control))
    def _expand(event) -> None:
        navigation_accelerator.reset()
        if concept_focus_active():
            return
        index = selected_index["value"]
        if expanded_index["value"] != index:
            expanded_index["value"] = index
            selected_form["value"] = 0
            emit_explore_action(
                "EXPAND",
                visible_entries["value"][index].name,
            )
        elif selected_form["value"] is None:
            selected_form["value"] = 0
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(list_control))
    def _collapse(event) -> None:
        navigation_accelerator.reset()
        if concept_focus_active():
            return
        if selected_form["value"] is not None:
            selected_form["value"] = None
        elif expanded_index["value"] == selected_index["value"]:
            expanded_index["value"] = None
        event.app.invalidate()

    def _handle_help_key(event) -> None:
        navigation_accelerator.reset()
        if mode == "EXPLORE":
            # The command-wait shell presents Help by default. H therefore
            # means the same thing on both sides of that shell: hide the
            # visible inventory here, and reopen it from the waiting surface.
            emit_explore_action("HIDE")
            event.app.exit(result=None)
            return
        if concept_focus_active():
            return
        entry = visible_entries["value"][selected_index["value"]]
        event.app.exit(
            result=HelpSelection(
                command_name=entry.name,
                command_line=f"mem {entry.name}",
                show_help=True,
            )
        )

    if mode == "EXPLORE":
        bind_case_insensitive_key(
            bindings,
            "h",
            eager=True,
        )(_handle_help_key)
    else:
        bind_case_insensitive_key(
            bindings,
            "h",
            filter=has_focus(list_control),
        )(_handle_help_key)

    @bindings.add("left", filter=has_focus(view_control), eager=True)
    def _previous_view(event) -> None:
        navigation_accelerator.reset()
        select_view(-1)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(language_control), eager=True)
    def _previous_language(event) -> None:
        navigation_accelerator.reset()
        select_language(-1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(language_control), eager=True)
    def _next_language(event) -> None:
        navigation_accelerator.reset()
        select_language(1)
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(language_control), eager=True)
    def _leave_language(event) -> None:
        surface_focus.focus_relative(
            event.app,
            1,
            wrap=False,
        )
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(view_control), eager=True)
    def _enter_language(event) -> None:
        surface_focus.focus_relative(
            event.app,
            -1,
            wrap=False,
        )
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(view_control), eager=True)
    def _next_view(event) -> None:
        navigation_accelerator.reset()
        select_view(1)
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(view_control), eager=True)
    def _leave_view(event) -> None:
        surface_focus.focus_relative(
            event.app,
            1,
            wrap=False,
        )
        event.app.invalidate()

    @bindings.add("tab")
    def _next_surface(event) -> None:
        move_tab(event, 1)

    @bindings.add("s-tab")
    def _previous_surface(event) -> None:
        move_tab(event, -1)

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def header_fragments() -> list[tuple[str, str]]:
        title = (
            " " + explore_title
            if mode == "EXPLORE"
            else " mem help · command inventory"
        )
        status = status_supplier() if status_supplier is not None else ""
        fragments = [("class:title", title)]
        if status:
            fragments.append(("", f" · {display_escape_text(status)}"))
        return fragments

    header = Window(
        FormattedTextControl(header_fragments),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    body = Window(
        list_control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    view = Window(
        view_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    language = Window(
        language_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    language_frame = Frame(language, title="HELP LANGUAGE")
    bind_focused_frame_style(
        language_frame,
        is_focused=lambda: (
            app_ref.get("app") is not None
            and app_ref["app"].layout.has_focus(language_control)
        ),
    )
    view_frame = Frame(view, title="INVENTORY VIEW")
    bind_focused_frame_style(
        view_frame,
        is_focused=lambda: (
            app_ref.get("app") is not None
            and app_ref["app"].layout.has_focus(view_control)
        ),
    )

    def footer_text() -> str:
        return_label = (
            f"return to {explore_return_label}" if mode == "EXPLORE" else "cancel"
        )
        if app_ref.get("app") is not None and app_ref["app"].layout.has_focus(
            language_control
        ):
            return " LANGUAGE: ←/→ choose · ↓ view · Tab next · Q " + return_label
        if app_ref.get("app") is not None and app_ref["app"].layout.has_focus(
            view_control
        ):
            toggle = " · H hide Help" if mode == "EXPLORE" else ""
            tab_hint = (
                "Tab first kind"
                if view_state.selected_uid == "CATEGORY"
                else "Tab list"
            )
            return f" VIEW: ←/→ choose · ↓ list · {tab_hint}{toggle} · Q {return_label}"
        if concept_focus_active():
            toggle = (
                f" H hide Help · Q return to {explore_return_label}"
                if mode == "EXPLORE"
                else ""
            )
            return f" ↑/↓ move (hold accelerates)  Tab first kind {toggle}"
        enter_action = (
            "Enter open forms"
            if selected_form["value"] is None
            else (
                "Enter inspect form"
                if mode == "EXPLORE"
                else "Enter prefill command line"
            )
        )
        detail_action = (
            f"H hide Help  Q return to {explore_return_label}"
            if mode == "EXPLORE"
            else "H full help  Q/Esc close"
        )
        tab_hint = (
            "Tab next kind" if view_state.selected_uid == "CATEGORY" else "Tab surface"
        )
        return (
            " ↑/↓ move (hold accelerates)  → expand/forms  ← back  "
            f"{enter_action}  {tab_hint}  {detail_action} "
        )

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    application: Application[HelpSelection | None] = Application(
        layout=Layout(
            HSplit(
                [
                    header,
                    language_frame,
                    view_frame,
                    body,
                    horizontal_rule(right_gutter=1),
                    footer,
                ]
            ),
            focused_element=list_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        refresh_interval=(0.35 if status_supplier is not None else None),
        style=merge_styles(
            [
                MEMCOMMIT_TUI_STYLE,
                SEMANTIC_VIEWER_STYLE,
                Style.from_dict(
                    {
                        "title": "bold",
                        "selected": "fg:#10242f bg:#8bd5ff bold",
                        "help-command.selected": "fg:#10242f bg:#8bd5ff",
                        "help-connector": "fg:#6e738d",
                        "form": "fg:#cad3f5",
                        "category": "bold",
                        "help-command": "bold",
                        "help-group": "",
                        "help-group.focused": "fg:#8bd5ff bold",
                        "help-guide.border": "",
                        "help-guide.border.focused": "fg:#8bd5ff bold",
                        "help-guide.label": "bold",
                    }
                ),
            ]
        ),
    )
    app_ref["app"] = application
    try:
        return application.run(pre_run=on_ready)
    except (EOFError, KeyboardInterrupt):
        return None


def _show_selected_command_help(
    root: typer.Context,
    entry: CommandEntry,
) -> None:
    """Render syntax help without invoking the selected command callback."""
    typer.secho(f"Command: mem {entry.name}", bold=True)
    typer.echo()

    if entry.operation_help is not None:
        composed = compose_operation_help(
            entry.operation_help,
            cli_forms=entry.forms,
        )
        typer.secho("Overview", bold=True)
        label_width = max(len(row.label) for row in composed.overview)
        for row in composed.overview:
            typer.echo(f"  {row.label:<{label_width}}  {row.value}")
        typer.echo()
        typer.secho("Command line", bold=True)
        for form in composed.cli_forms:
            typer.echo(f"  {form}")
        typer.echo()

    # Use a display-only root so Usage always names the installed `mem`
    # executable, including when this is exercised through CliRunner.
    # New Typer releases use their own Click-compatible Context, while older
    # releases expose Click's class directly. Reusing the active Context class
    # keeps help rendering compatible across both without a second, mismatched
    # runtime Click dependency.
    context_type = type(root)
    display_root = context_type(
        root.command,
        info_name="mem",
        color=root.color,
        terminal_width=root.terminal_width,
        max_content_width=root.max_content_width,
    )
    command_context = context_type(
        entry.command,
        info_name=entry.name,
        parent=display_root,
        color=root.color,
        terminal_width=root.terminal_width,
        max_content_width=root.max_content_width,
    )
    try:
        rendered = entry.command.get_help(command_context)
        # Typer's Rich help writes directly to its console and returns an
        # empty string; plain Click commands return the text for us to emit.
        if rendered:
            typer.echo(rendered)
    finally:
        command_context.close()
        display_root.close()


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _selection_terminal() -> bool:
    return sys.stdin.isatty() and sys.stderr.isatty()


def _selection_output() -> Output:
    # stdout is reserved for the one-line selection consumed by shell
    # integration, so the full-screen interface must stay on the TTY stream.
    return create_output(stdout=sys.stderr)


def cmd(
    ctx: typer.Context,
    request: Annotated[
        str | None,
        typer.Argument(
            show_default=False,
            help=(
                "Natural-language operation request; when supplied, return "
                "up to three matching Help rows and exit"
            ),
        ),
    ] = None,
    emit_selection: Annotated[
        bool,
        typer.Option(
            "--emit-selection",
            hidden=True,
            help="Emit one selected command for shell integration.",
        ),
    ] = False,
) -> None:
    """Enter the command browser and open syntax help for a selection."""
    root = ctx.parent
    if root is None:
        typer.secho(
            "Help error: no root command context.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    entries = command_entries(root)
    if request is not None:
        if emit_selection:
            typer.secho(
                "Help error: a natural-language request cannot be combined "
                "with shell selection.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            # Freeze and preflight the complete catalog before provider access.
            catalog_operations = tuple(
                entry.operation_help
                for entry in entries
                if entry.operation_help is not None
            )
            plan = prepare_help_lookup(
                request,
                operations=catalog_operations,
            )
            # Focused Help wording is a declared Study instrument. The recorder
            # is a no-op outside the current Participant Profile, so ordinary
            # Help adds no typed Study event beyond its generic command record.
            record_study_help_lookup_submitted(plan.request)
            if (
                active_profile_is_study()
                and find_study_help_copy_match(
                    plan.request,
                    authored_study_help_fields(plan.operations),
                )
                is not None
            ):
                typer.secho(
                    "Help error: Study lookup requires original task wording; "
                    "the request exactly matches at least 50% of one Help "
                    "Description/WHEN entry.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            # Bare Help is local and deterministic. Start liveness feedback only
            # after focused lookup preflight so invalid or Study-blocked input
            # never looks like provider work has begun.
            with CommandProgress("help", "thinking", total=1):
                provider = connect_help_provider()
                operations = execute_help_lookup(plan, provider)
            record_study_help_lookup_completed(
                tuple(operation.name for operation in operations)
            )
        except (
            HelpLookupError,
            ProfileConfigError,
            QueryProviderError,
            OSError,
        ) as error:
            typer.secho(
                f"Help error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1) from error
        entries_by_name = {entry.name: entry for entry in entries}
        matched_entries = [entries_by_name[operation.name] for operation in operations]
        typer.echo(
            render_help_lookup_entries(
                matched_entries,
                content_width=(
                    root.terminal_width
                    or shutil.get_terminal_size(fallback=(100, 24)).columns
                ),
            )
        )
        return

    if emit_selection:
        if not _selection_terminal():
            typer.secho(
                "Error: shell selection requires an interactive terminal.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        selection = run_help_selector(
            entries,
            app_output=_selection_output(),
            require_tty=False,
        )
        if selection is not None:
            typer.echo(selection.command_line)
        return

    if not _interactive_terminal():
        _render_plain_inventory(entries)
        return

    selection = run_help_selector(entries)
    if selection is None:
        return
    if not selection.show_help:
        typer.echo(selection.command_line)
        return
    selected = next(entry for entry in entries if entry.name == selection.command_name)
    _show_selected_command_help(root, selected)
