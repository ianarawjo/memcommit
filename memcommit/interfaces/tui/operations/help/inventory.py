"""Present the top-level CLI command inventory."""

from __future__ import annotations

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

from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.core.keybindings import (
    NavigationAccelerator,
    bind_case_insensitive_key,
)
from memcommit.interfaces.tui.components.frame import (
    bind_focused_frame_style,
    horizontal_rule,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceFocusController,
)
from memcommit.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.help_catalog import (
    OperationComparisonDetail,
    OperationHelp,
    OperationTextDetail,
    compose_operation_help,
)
from memcommit.help_application import list_operation_help


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
COMMAND_RELATED_FORMS = {
    "rename": (
        "mem profile rename [new_name] (explicit equivalent for the active Profile)",
        "mem profile rename [profile_name] [new_name] (explicit equivalent for a named Profile)",
    ),
}

HELP_CORE_CONCEPTS = (
    (
        "MEMORY",
        "An atomic unit of information stored in a Context.",
    ),
    (
        "CONTEXT",
        "A named workspace that organizes Memories and other Contexts.",
    ),
    (
        "PROFILE",
        "An ownership and storage boundary for Contexts.",
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
        "A saved record of an analysis or review workflow that can be reopened "
        "and continued; it does not itself mean Context changes were applied.",
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
    "MEMORY": "class:memory-object",
}

HELP_COMMON_KEYS = (
    ("↑/↓", "Move or scroll within the focused surface."),
    (
        "←/→",
        "Change a horizontal choice, expand, or go back according to focus.",
    ),
    ("Tab / Shift-Tab", "Move focus between visible surfaces."),
    ("Enter", "Open, select, or submit the focused action."),
    (
        "H",
        "Open or hide Help from a session's read-only navigation surface.",
    ),
    (
        "Esc / Backspace",
        "Go back one layer; Backspace edits text in writable fields.",
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
        ),
    ),
    (
        "CREATE, COPY & CONNECT",
        (
            "init",
            "add",
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
        ("profile", "rename"),
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
        "saved analysis and decide what should happen next.",
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
        'mem add "[memory]" (add one Memory to the current Context)',
        "mem add (open the interactive multi-Memory editor)",
        'mem add --memory "[memory]" --memory "[memory]" (add an explicit batch)',
        "mem add --input [file] (add one Memory per non-empty line)",
        "mem add --paste (paste one or more Memories)",
        'mem add "[memory]" --context [context] (add to an explicit Context)',
        "mem add --input [file] --context [context] (batch-add to an explicit Context)",
        "mem add --paste --context [context] (paste into an explicit Context)",
    ),
    "audit": (
        "mem audit (choose one Context, run Duplicate + Ambiguity + Conflict, save, and review)",
        "mem audit --context [context] (run and save all three finders for one exact Context)",
        "mem audit --context [context] --against [rules_context] (add the shared Conformance check)",
        "mem audit --context [context] --snapshot (save and print the combined report)",
    ),
    "check-conformance": (
        "mem check-conformance (show the required Ground or Rules input error)",
        "mem check-conformance --ground [ground] (replay Rules without exposing expected outputs)",
        "mem check-conformance [target_context] --against [rules_context] (check Context adherence)",
        "mem check-conformance --against [rules_context] (use the current Context as Target)",
    ),
    "fit": (
        "mem fit (show the required two-proposition input error)",
        'mem fit "[proposition A]" "[proposition B]" (judge the complete set as YES, MAY, or NO)',
        'mem fit "[A]" "[B]" --background "[K]" (judge under one explicit background proposition)',
        "mem fit --ground [ground] (run the revision-bound Ground adapter and save its receipt)",
        "mem fit --ground [ground] --receipt [uid] (reopen one current or stale Ground receipt)",
    ),
    "resolve": (
        "mem resolve (analyze the current direct-Memory frame and open review)",
        "mem resolve --context [context] --plain (propose verified UPDATE-only Fit repairs)",
        "mem resolve [memory_uid] --context [context] (restrict mutation to exact direct Memories)",
        "mem resolve --context [context] --allow-create (also permit CREATE candidates)",
        'mem resolve --context [context] --allow-delete --guidance "[grounds]" (permit grounded DELETE candidates)',
        "mem resolve --context [context] --candidate [full_id] --expected-revision [revision] --apply (regenerate, verify, and apply one exact candidate)",
    ),
    "dedup": (
        "mem dedup (show the required find-duplicates handoff error)",
        "mem dedup --finding-handoff '[json]' (review confirmed duplicate components)",
        "mem dedup --finding-handoff '[json]' --plain (print deterministic survivor recommendations)",
        "mem dedup --finding-handoff '[json]' --survivor [component]=[memory] --expected-revision [revision] --apply (apply one exact complete survivor set)",
    ),
    "atomize": (
        "mem atomize (enter the current Context's interactive Atomize session)",
        "mem atomize --context [context] (enter that Context's interactive Atomize session)",
        "mem atomize --sessions (enter the interactive Atomize session launcher)",
        'mem atomize --evaluate "[issue]" (directional atomic review)',
    ),
    "branch": (
        "mem branch (choose a local Source, parent location, and fresh target)",
        "mem branch [new_context] (branch the current Context and switch)",
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
    ),
    "chunk": (
        "mem chunk (preview sentence splits for all splittable direct Memories in the current Context, then confirm)",
        "mem chunk [memory_selector] (split one direct Memory by sentences)",
        "mem chunk --context [context] (all splittable direct Memories in one Context)",
        "mem chunk [memory_selector] --context [context] --method [method] (sentences, clauses, paragraphs, or markdown_headers)",
        "mem chunk [memory_selector] --break-on [punctuation] --min-chars 200 --max-chars 1000 (compose literal and size boundaries)",
    ),
    "clear": (
        "mem clear (clear the current Context after confirmation)",
        "mem clear [context] (clear an explicit Context after confirmation)",
    ),
    "compare": (
        "mem compare (enter the interactive Compare session launcher)",
        "mem compare --sessions (enter the interactive Compare session launcher)",
        "mem compare --to [context2] (current Context is context1)",
        "mem compare --from [context1] --to [context2] (explicit Contexts)",
        "mem compare --from [context1] --to [context2] -r (both readable subtrees)",
        "mem compare --from [context1] --to [context2] --reference-descendants --compared-descendants (include each readable subtree)",
    ),
    "config": (
        "mem config show (show global configuration)",
        'mem config set [key] "[value]" (set one global value)',
    ),
    "contexts": ("mem contexts (list local Contexts and granted views)",),
    "delete": (
        "mem delete [item] (delete a Context or current direct item)",
        "mem delete (select a Context or direct item interactively)",
        "mem delete [item] --context [context] (explicit direct-item scope)",
    ),
    "diff": (
        "mem diff (select a Context, then inspect its checkpoints)",
        "mem diff [context] (inspect that Context's checkpoints directly)",
        "mem diff --raw (exact unified diff)",
        "mem diff --stat (summary only)",
        "mem diff --verbose (complete UIDs and source/target fingerprints)",
    ),
    "distill": (
        "mem distill (review Rules distilled from the current Context)",
        "mem distill [context] (review Rules from one explicit Context)",
        'mem distill [context] --goal "[goal]" (guide Rule relevance with a Goal)',
        "mem distill [context] -r (include descendants and embedded Contexts)",
        "mem distill [context] --save-as [result_context] "
        "(review without creating the Result)",
        "mem distill [context] --save-as [result_context] --apply "
        "(create the exact reviewed Rule Context)",
        "mem distill --ground [name] "
        "(review Rules from its exact Goal and working-candidate frame)",
    ),
    "elaborate": (
        'mem elaborate --goal "[goal]" (propose candidate Rules)',
        'mem elaborate --rule "[rule]" (propose concrete Cases)',
        'mem elaborate --rule "[rule1]" --rule "[rule2]" '
        "(propose concrete Cases across explicit Rules)",
        "mem elaborate --ground [name] --from-goal "
        "(use the exact Ground Goal through the same application)",
        "mem elaborate --ground [name] --from-rules "
        "(use the exact active Ground Rules through the same application)",
    ),
    "edit": (
        'mem edit [memory] "[new_content]" (replace one direct Memory)',
        "mem edit --input [file] (replace Memories from a batch file)",
        'mem edit [memory] "[new_content]" --context [context] (explicit Context)',
        "mem edit --input [file] --context [context] (batch-edit an explicit Context)",
    ),
    "replace": (
        "mem replace (choose text, local scope, and review exact changes interactively)",
        'mem replace "[text]" "[replacement]" --plain (preview literal replacements)',
        'mem replace "[text]" --delete-match --plain (preview exact text removal)',
        'mem replace "[expression]" "[replacement]" --regex --plain (explicit regex matching with literal replacement)',
        'mem replace "[text]" "[replacement]" --context [context1] --context [context2] --descendants (multiple local roots)',
        'mem replace "[text]" "[replacement]" --apply [plan_digest] (re-freeze and atomically Apply the reviewed plan)',
    ),
    "embed": (
        "mem embed (choose Context or Memory link, target, and insertion gap interactively)",
        "mem embed [child_context] --into [target_context] (append)",
        "mem embed [child_context] --into [target_context] --before [item]",
        "mem embed [child_context] --into [target_context] --after [item]",
        "mem embed [memory] --from [source_context] --into [target_context] (live Memory link)",
        "mem embed [memory] --from [source_context] --into [target_context] --before [item]",
        "mem embed [memory] --from [source_context] --into [target_context] --after [item]",
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
    ),
    "search": (
        "mem search (interactive semantic search, checked COPY/REFERENCE, and Save Location)",
        'mem search "[query]" (semantic search in the direct current Context)',
        'mem search -r "[query]" (namespace descendants and embedded Contexts)',
        'mem search "[temporal_query]" (retained history when the query explicitly asks about time)',
        'mem search --context [context] "[query]" (direct explicit Context root)',
        'mem search --context [context1] --context [context2] --descendants "[query]" (multiple roots with lexical descendants)',
        'mem search --context-only --follow-embeds "[query]" (exact lexical roots while following embedded Contexts)',
        'mem search --descendants --exclude-embeds "[query]" (lexical subtrees without embedded traversal)',
        'mem search -d "[query]" (direct preset: context-only plus exclude-embeds)',
    ),
    "find-ambiguities": (
        "mem find-ambiguities (current Context; no changes)",
        "mem find-ambiguities --context [context] (explicit Context; no changes)",
    ),
    "find-conflicts": (
        "mem find-conflicts (current Context; no changes)",
        "mem find-conflicts --context [context] (explicit Context; no changes)",
    ),
    "find-duplicates": (
        "mem find-duplicates (current Context; no changes)",
        "mem find-duplicates --context [context] (explicit Context; no changes)",
    ),
    "forget": (
        "mem forget (enter interactive instruction and direct-Source setup)",
        'mem forget "[instruction]" (review and apply selective forgetting)',
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
        "mem impact atomize (preview atomization of the current Context)",
        "mem impact atomize --context [context] (preview atomization of one Context)",
        'mem impact forget "[instruction]" (preview complete in-place decisions; Source unchanged)',
        'mem impact forget "[instruction]" --context [context] (preview one exact direct Source)',
        "mem impact distill [context] --save-as [result_context] (preview fresh Result Memories; not created)",
        "mem impact resolve --context [context] (preview one verified candidate or the candidate choice)",
        "mem impact resolve --context [context] --candidate [full_id] (preview one exact effect set)",
        "mem impact meld (inspect a saved Meld Impact; APPLY? opens its Apply flow)",
        "mem impact meld --session [uid] (inspect an exact saved Meld Impact; APPLY? opens its Apply flow)",
        "mem impact sever (inspect a saved Sever Impact; APPLY? opens its Apply flow)",
        "mem impact sever --session [uid] (inspect an exact saved Sever Impact; APPLY? opens its Apply flow)",
        "mem impact update (inspect the saved Update Impact; APPLY? opens its Apply flow)",
        "mem impact update --session [uid] (inspect the exact saved Update Impact; APPLY? opens its Apply flow)",
        "mem impact --from [source_context] --to [target_context] (directional preview)",
        "mem impact -r --from [source_context] --to [target_context] (recursive endpoints)",
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
        "mem import memory [memory] --from-profile [source_profile] --context [source_context] (into current Context)",
        "mem import memory [memory] --from-profile [source_profile] --context [source_context] --into [target_context]",
        "mem import [profile_name] --from [store] (legacy clean-baseline Profile spelling)",
    ),
    "init": (
        "mem init (edit a suggested fresh Context name, create, and switch)",
        "mem init [context] (create and switch to one Context)",
        "mem init --parents (edit a suggested name and ensure its hierarchy)",
        "mem init [context] --parents (ensure its lexical hierarchy and switch)",
    ),
    "init-study": (
        "mem init-study (edit or generate a Study Profile name)",
        "mem init-study [profile_name] (use an explicit Study Profile name)",
        "mem init-study --from-profile [baseline_profile] (generated run name)",
        "mem init-study [profile_name] --from-profile [baseline_profile] (explicit baseline)",
    ),
    "list": (
        "mem list (enter the interactive Context browser in a TTY; print otherwise)",
        "mem list [context] (explicit Context listing)",
        "mem list -r (recursive current-Context listing; -R remains an alias)",
        "mem list [context] -R (recursive Context listing)",
        "mem list --copy (copy and stage the current listing)",
        "mem list [context] --copy (copy and stage an explicit listing)",
        "mem list --paste (reopen the frozen copied result)",
    ),
    "lock": (
        "mem lock (lock the current Context)",
        "mem lock -r (lock the current Context namespace)",
        "mem lock context [context] (lock an explicit Context)",
        "mem lock context [context] --recursive (lock an explicit Context namespace)",
        "mem lock memory [memory] (lock a direct Memory in the current Context)",
        "mem lock memory [memory] --context [context] (lock a direct Memory)",
        "mem lock profile (lock the active Profile)",
    ),
    "log": (
        "mem log (select a Context, then browse its checkpoints in a TTY; print otherwise)",
        'mem log "[query]" (semantic history search)',
        "mem log --memory [memory] (Memory-lineage view; canonical Trace route)",
        "mem log --memory [memory] --context [context] (explicit Context and Memory)",
        "mem log --operations (Profile command attempts)",
        "mem log --actions (current Study Profile action events)",
    ),
    "meld": (
        "mem meld (enter the interactive Meld session launcher)",
        "mem meld --sessions (enter the interactive Meld session launcher)",
        "mem meld [incoming_context] (directional into current Baseline)",
        "mem meld [incoming_context] [baseline_context] (directional)",
        "mem meld team/proposed-changes team/current-policy (example: directional Baseline)",
        "mem meld [peer_a] [peer_b] [result_context] (symmetric Result)",
        "mem meld team/draft-a team/draft-b team/merged-draft (example: symmetric Result)",
        "mem meld [peer_a] [peer_b] --to [result_context] (symmetric Result alias)",
        "mem meld [peer_a] [peer_b] [result_context] -r (both subtrees)",
        "mem meld [peer_a] [peer_b] [result_context] --left-descendants --right-descendants (symmetric readable subtrees)",
        "mem meld [incoming_context] --into [baseline_context] (directional alias)",
        "mem meld [incoming_context] --left-descendants --into [baseline_context] --right-descendants (directional selected subtrees with owner-aware baseline writes)",
        "mem meld --into [baseline_context] (current Context is incoming)",
        "mem meld --from [incoming_context] (current Context is baseline)",
    ),
    "merge": (
        "mem merge (choose a readable Source, CREATE-authorized Target, and reach in a TTY)",
        "mem merge [source_context] --into [target_context] --direct (explicit exact roots)",
        "mem merge [source_context] --into [target_context] --recursive (explicit path-aligned subtrees)",
        "mem merge [source_context] --direct (exact Source root into current Context; default)",
        "mem merge [source_context] --recursive (path-aligned descendants into current Context)",
        "mem merge [source_context] --keep-target-all (resolve every structural conflict by retaining Target)",
        "mem merge [source_context] --take-source-all (resolve every structural conflict with exact Source values)",
        "mem merge [source_context] --resolve [conflict_id]=keep-target (repeat one exact frozen decision per conflict)",
    ),
    "profile": (
        "mem profile (enter the interactive Profile selector in a TTY; list otherwise)",
        "mem profile [profile_name] (select through the concise alias)",
        "mem profile use [profile_name] (select explicitly)",
        "mem profile list (list registered Profiles)",
        "mem profile current (show the active Profile)",
        "mem profile rename [new_name] (rename the active Profile)",
        "mem profile rename [profile_name] [new_name] (rename an explicit Profile)",
        "mem profile remove [profile_name] (permanently delete one Profile store)",
        "mem profile remove-study [study_name] (permanently delete Study stores)",
        "mem profile import [profile_name] --from [store] (copy a complete store)",
        "mem profile import-study (bootstrap the editable Study baseline)",
        "mem profile refresh-study (refresh the editable Study baseline)",
        "mem profile archive-study [study_name] (detach a legacy split Study)",
        "mem profile grant list (list cross-Profile views)",
        "mem profile grant create [authority_profile] [grantee_profile] [source_context] --into [attachment_context] --allow [permission]",
        "mem profile grant create [authority_profile] [grantee_profile] [source_context] --into [attachment_context] --allow [permission] --recursive (freeze descendants)",
        "mem profile grant update [grant] --allow [permission]",
        "mem profile grant update [grant] --allow [permission] --refresh-scope (refreeze descendants)",
        "mem profile grant update [grant] --allow [permission] --root-only (freeze only the root)",
        "mem profile grant delete [grant] (revoke a view)",
    ),
    "provider": (
        "mem provider status (inspect the selection without connecting)",
        "mem provider use codex_chatgpt (select managed Codex defaults)",
        "mem provider use ollama --model [model] (select a local model)",
        "mem provider use openrouter --model [model] (select a routed model)",
        "mem provider probe (test the current selection)",
    ),
    "query": (
        "mem query (open the interactive Question, Source, and saved transcript workbench)",
        'mem query "[question]" (ask the direct current ordinary Context)',
        'mem query -r "[question]" (include descendants and embedded Contexts)',
        'mem query --context [context] "[question]" (ask an explicit ordinary Context)',
        "mem query [query_view] (browse opaque Memory handles)",
        'mem query [query_view] "[question]" (ask a query-only view)',
        'mem query [query_view]#[memory_handle] "[question]" (ask one opaque Memory)',
        'mem query [query_view] "[question]" --language [language] (explicit source language)',
        'mem query [query_view] "[question]" --session [session_name] (retain visible Q/A)',
        "mem query --sessions (list saved query transcripts)",
        "mem query --show-session [session_name] (show one saved transcript)",
    ),
    "rationale": (
        "mem rationale (open Recents or browse readable Contexts, then select a Memory)",
        "mem rationale [memory] (explain one current or historical Memory)",
        "mem rationale --context [context] (start Memory selection in one readable Context)",
        "mem rationale [memory] --context [context] (explicit Context and Memory)",
        "mem rationale [memory] --recorded-only (skip inference and its cache)",
    ),
    "reference": (
        "mem reference [memory] --from [source_context] (snapshot into current Context)",
        "mem reference [memory] --from [source_context] --into [target_context] (immutable snapshot)",
    ),
    "rename": (
        "mem rename [new_name] (rename the active Profile)",
        "mem rename [profile_name] [new_name] (rename an explicit Profile)",
    ),
    "redo": ("mem redo (redo the most recently undone Context command)",),
    "revert": (
        "mem revert (choose a local Context, checkpoint, and history policy interactively)",
        "mem revert --context [context] (open one Context's checkpoint and history-policy review)",
        "mem revert [checkpoint] (restore exact and discard newer checkpoints)",
        "mem revert [checkpoint] --context [context] (restore an exact checkpoint in one Context)",
        "mem revert [checkpoint] --keep (restore exact and preserve newer checkpoints)",
        'mem revert "[description]" (semantic lookup; discard newer when applied)',
    ),
    "review": (
        "mem review (enter the interactive Review session)",
        "mem review audit (open a saved three-finder Audit)",
        "mem review compare (open a saved Compare report)",
        "mem review meld (open a saved Meld report)",
        "mem review sever (open a saved Sever report)",
        "mem review update (open the saved Update report)",
        "mem review [kind] --session [uid] (exact Audit, Compare, Meld, Sever, or Update artifact)",
        "mem review atomize (open the current Context's saved Atomize analysis)",
        "mem review atomize --context [context] (Context-bound Atomize review)",
        "mem review ambiguities (analyze current-Context ambiguities)",
        "mem review ambiguities --context [context] (Context-bound Ambiguity review)",
    ),
    "sever": (
        "mem sever (enter the interactive Sever session launcher)",
        "mem sever --sessions (enter the interactive Sever session launcher)",
        "mem sever --source [source_context] --criteria [criteria_context] --save-as [result_context]",
        "mem sever -r --source [source_context] --criteria [criteria_context] --save-as [result_context]",
        "mem sever --criteria [criteria_context] --save-as [result_context] (current Context is source)",
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
        "mem show [item] (show one direct item)",
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
    ),
    "translate": (
        "mem translate (show/save a default-English view of the current Context)",
        "mem translate [memory] (show/save one default-English Memory view)",
        "mem translate --to [language] (show/save a current-Context view)",
        "mem translate [memory] --to [language] (show/save one Memory view)",
        "mem translate --save-as [result_context] (default-English new Context and switch)",
        "mem translate [memory] --save-as [result_context] (new Context replacing one Memory; switch)",
        "mem translate --to [language] --save-as [result_context] (new translated Context and switch)",
        "mem translate [memory] --to [language] --save-as [result_context] (new Context replacing one Memory; switch)",
        "mem translate --in-place (add default-English sibling Memories)",
        "mem translate [memory] --in-place (add one default-English sibling Memory)",
        "mem translate --to [language] --in-place (add translated sibling Memories)",
        "mem translate [memory] --to [language] --in-place (add one translated sibling Memory)",
    ),
    "trace": (
        "mem trace (open Recents or browse local Contexts, then select a Memory)",
        "mem trace [memory] (shorthand for mem log --memory [memory])",
        "mem trace --context [context] (start Memory selection in one local Context)",
        "mem trace [memory] --context [context] (explicit Context and Memory)",
        "mem trace [memory] --plain (print instead of opening History explorer)",
    ),
    "undo": ("mem undo (undo the latest recorded Context command)",),
    "unlock": (
        "mem unlock (unlock the current Context)",
        "mem unlock -r (unlock the current Context namespace)",
        "mem unlock context [context] (unlock an explicit Context)",
        "mem unlock context [context] --recursive (unlock an explicit Context namespace)",
        "mem unlock memory [memory] (unlock a direct Memory in the current Context)",
        "mem unlock memory [memory] --context [context] (unlock a direct Memory)",
        "mem unlock profile (unlock the active Profile)",
    ),
    "update": (
        "mem update (enter the interactive Update session launcher)",
        "mem update --from [source_context] --to [target_context] (explicit direction)",
        "mem update -r --from [source_context] --to [target_context] (both subtrees)",
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


def _entry_line(
    entry: CommandEntry,
    *,
    name_width: int,
) -> str:
    label = _entry_label(entry)
    return f"{label:<{name_width}} - {entry.description}"


_HELP_SIDE_BY_SIDE_MIN_BODY_WIDTH = 108
_HELP_WIDE_COLUMN_SEPARATOR = " │ "
_HELP_USE_WHEN_LABEL = "USE WHEN:"
_HELP_USE_WHEN_PREFIX = _HELP_USE_WHEN_LABEL + " "


def _wrapped_help_text(value: str, *, width: int) -> list[str]:
    return textwrap.wrap(
        display_escape_text(value),
        width=max(1, width),
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]


def _help_command_rows(
    entry: CommandEntry,
    *,
    command_prefix: str,
    content_width: int,
) -> list[tuple[str, str, int | None]]:
    """Project summary and use case beside each other when space permits."""

    body_width = max(1, content_width - len(command_prefix))
    best_for = None if entry.operation_help is None else entry.operation_help.best_for
    if best_for is None:
        summary_lines = _wrapped_help_text(entry.description, width=body_width)
        return [
            (
                command_prefix if index == 0 else " " * len(command_prefix),
                line.ljust(body_width),
                None,
            )
            for index, line in enumerate(summary_lines)
        ]

    if body_width >= _HELP_SIDE_BY_SIDE_MIN_BODY_WIDTH:
        # The divider makes the equal Summary and use-case columns readable as
        # distinct roles without adding another row to the wide inventory.
        column_width = content_width - len(_HELP_WIDE_COLUMN_SEPARATOR)
        left_width = column_width // 2
        summary_width = max(1, left_width - len(command_prefix))
        best_for_width = max(1, column_width - left_width)
        summary_lines = _wrapped_help_text(
            entry.description,
            width=summary_width,
        )
        best_for_lines = textwrap.wrap(
            _HELP_USE_WHEN_PREFIX + display_escape_text(best_for),
            width=best_for_width,
            subsequent_indent=" " * len(_HELP_USE_WHEN_PREFIX),
            break_long_words=True,
            break_on_hyphens=False,
        ) or [_HELP_USE_WHEN_LABEL]
        row_count = max(len(summary_lines), len(best_for_lines))
        rows: list[tuple[str, str, int | None]] = []
        for row_index in range(row_count):
            prefix = command_prefix if row_index == 0 else " " * len(command_prefix)
            summary = summary_lines[row_index] if row_index < len(summary_lines) else ""
            use_case = (
                best_for_lines[row_index] if row_index < len(best_for_lines) else ""
            )
            rows.append(
                (
                    prefix,
                    summary.ljust(summary_width)
                    + _HELP_WIDE_COLUMN_SEPARATOR
                    + use_case.ljust(best_for_width),
                    summary_width + len(_HELP_WIDE_COLUMN_SEPARATOR)
                    if row_index == 0
                    else None,
                )
            )
        return rows

    summary_lines = _wrapped_help_text(entry.description, width=body_width)
    rows = [
        (
            command_prefix if index == 0 else " " * len(command_prefix),
            line.ljust(body_width),
            None,
        )
        for index, line in enumerate(summary_lines)
    ]

    stacked_prefix = " " * min(
        len(command_prefix),
        max(0, content_width - 1),
    )
    use_case_prefix = stacked_prefix + _HELP_USE_WHEN_PREFIX
    best_for_lines = textwrap.wrap(
        use_case_prefix + display_escape_text(best_for),
        width=content_width,
        subsequent_indent=" " * len(use_case_prefix),
        break_long_words=True,
        break_on_hyphens=False,
    ) or [stacked_prefix + _HELP_USE_WHEN_LABEL]
    rows.extend(
        (
            "",
            line.ljust(content_width),
            len(stacked_prefix) if index == 0 else None,
        )
        for index, line in enumerate(best_for_lines)
    )
    return rows


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
    top = ("┏" if focused else "┌") + title_label
    top += horizontal * max(0, inner_width - len(title_label))
    top += "┓" if focused else "┐"
    fragments: list[tuple[str, str]] = [(border_style, top + "\n")]
    vertical = "┃" if focused else "│"
    category_description = HELP_CATEGORY_DESCRIPTIONS.get(title)
    if category_description is not None:
        classification, description = category_description
        prefix = f"{classification} · " if classification is not None else ""
        lines = textwrap.wrap(
            prefix + display_escape_text(description),
            width=content_width,
            subsequent_indent=" " * len(prefix),
            break_long_words=True,
            break_on_hyphens=False,
        ) or [prefix]
        for line_index, line in enumerate(lines):
            fragments.extend([(border_style, vertical), ("", " ")])
            if line_index == 0 and classification is not None:
                fragments.extend(
                    [
                        (
                            "class:help-category-description bold",
                            line[: len(classification)],
                        ),
                        (
                            "class:help-category-description",
                            line[len(classification) :],
                        ),
                    ]
                )
            else:
                fragments.append(("class:help-category-description", line))
            fragments.extend(
                [
                    ("", " " * (content_width - len(line) + 1)),
                    (border_style, vertical + "\n"),
                ]
            )
    labels = {
        index: display_escape_text(_entry_label(entry)) for index, entry in entries
    }
    name_width = max(len(label) for label in labels.values())
    for index, entry in entries:
        expanded = index == expanded_index
        owns_selection = index == selected_index
        command_focused = focused and owns_selection and selected_form is None
        if command_focused:
            fragments.append(("[SetCursorPosition]", ""))
        command_prefix = (
            f"{'▾' if expanded else '▸'} mem {labels[index]:<{name_width}}  "
        )
        for prefix, body, use_when_offset in _help_command_rows(
            entry,
            command_prefix=command_prefix,
            content_width=content_width,
        ):
            fragments.append((border_style, vertical))
            body_style = "class:help-command.selected" if command_focused else ""
            prefix_style = (
                "class:help-command.selected bold"
                if command_focused
                else "class:help-command"
            )
            fragments.append((prefix_style, f" {prefix}"))
            if use_when_offset is None:
                fragments.append((body_style, f"{body} "))
            else:
                label_end = use_when_offset + len(_HELP_USE_WHEN_LABEL)
                fragments.extend(
                    [
                        (body_style, body[:use_when_offset]),
                        (
                            f"{body_style} bold".strip(),
                            body[use_when_offset:label_end],
                        ),
                        (body_style, body[label_end:] + " "),
                    ]
                )
            fragments.append((border_style, vertical + "\n"))
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
            details = () if entry.operation_help is None else entry.operation_help.details
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
                if form_focused:
                    fragments.append(("[SetCursorPosition]", ""))
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
    """Return rows left after Help's fixed header, view, rule, and footer."""

    return max(2, terminal_rows - 6)


def _help_information_box_fragments(
    *,
    width: int,
    by_kind: bool,
    focused_concept_index: int | None = None,
    focused: bool = False,
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
        label_width = max(len(label) for label, _description in items)
        for item_index, (label, description) in enumerate(items):
            row_focused = selectable and focused and focused_concept_index == item_index
            prefix = f"{label:<{label_width}}  "
            lines = textwrap.wrap(
                display_escape_text(description),
                width=max(1, content_width - len(prefix)),
                break_long_words=True,
                break_on_hyphens=False,
            ) or [""]
            for line_index, line in enumerate(lines):
                if row_focused and line_index == 0:
                    fragments.append(("[SetCursorPosition]", ""))
                row_prefix = prefix if line_index == 0 else " " * len(prefix)
                padding = " " * max(
                    0,
                    content_width - len(row_prefix) - len(line),
                )
                fragments.extend(
                    [
                        (border_style, "┃" if guide_focused else "│"),
                        (
                            "class:selected" if row_focused else "",
                            " " + row_prefix + line + padding + " ",
                        )
                        if row_focused
                        else ("", " "),
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
        HELP_CORE_CONCEPTS,
        selectable=True,
        label_styles=HELP_CORE_CONCEPT_STYLES,
    )
    border("COMMON KEYS", middle=True)
    rows(HELP_COMMON_KEYS, selectable=False)
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
        if event.app.layout.has_focus(view_control):
            # A complete cycle must leave VIEW toward the opposite edge of the
            # list. Retaining the last group here would recreate the old
            # VIEW/last-group two-stop loop after one pass through the screen.
            focus_group(groups[0] if direction > 0 else groups[-1])
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
            )
        )
        if fragments:
            fragments.append(("", "\n"))
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
            else "Enter inspect form"
            if mode == "EXPLORE"
            else "Enter prefill command line"
        )
        detail_action = (
            f"H hide Help  Q return to {explore_return_label}"
            if mode == "EXPLORE"
            else "H full help"
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
            HSplit([header, view_frame, body, horizontal_rule(right_gutter=1), footer]),
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
