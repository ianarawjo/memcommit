"""Present the top-level CLI command inventory."""
from __future__ import annotations

import sys
import textwrap
from dataclasses import dataclass
from typing import Annotated

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

from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    NavigationAccelerator,
    bind_focused_frame_style,
    display_escape_text,
    focus_in_order,
    horizontal_rule,
)
from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)


COMMAND_ANNOTATIONS = {
    "config": "legacy",
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

HELP_COMMON_KEYS = (
    ("↑/↓", "Move or scroll within the focused surface."),
    (
        "←/→",
        "Change a horizontal choice, expand, or go back according to focus.",
    ),
    ("Tab / Shift-Tab", "Move focus between visible surfaces."),
    ("Enter", "Open, select, or submit the focused action."),
    (
        "Esc / Backspace",
        "Go back one layer; Backspace edits text in writable fields.",
    ),
)

HELP_CATEGORY_GROUPS = (
    (
        "CONTEXTS",
        (
            "status", "contexts", "list", "ls", "show", "switch",
            "checkout", "init", "branch", "rename", "import", "embed",
            "reference",
        ),
    ),
    (
        "MEMORIES",
        (
            "add", "edit", "chunk", "forget", "remove", "delete", "clear",
        ),
    ),
    (
        "SEARCH & EXPLAIN",
        (
            "find", "query", "summarize", "trace", "rationale",
            "find-duplicates", "find-ambiguities", "find-conflicts",
        ),
    ),
    (
        "ANALYZE & TRANSFORM",
        (
            "atomize", "compare", "impact", "review", "meld", "update",
            "sever", "translate", "merge",
        ),
    ),
    (
        "HISTORY & RECOVERY",
        ("log", "diff", "checkpoint", "undo", "redo", "revert"),
    ),
    (
        "GROUND & EVALUATION",
        ("ground", "init-study", "eval"),
    ),
    (
        "PROFILE & SHARING",
        ("profile", "share", "lock", "unlock"),
    ),
    (
        "SYSTEM",
        ("help", "provider", "shell-init", "config"),
    ),
)

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
        "mem add --input [file] (add one Memory per non-empty line)",
        "mem add --paste (paste one or more Memories)",
        'mem add "[memory]" --context [context] (add to an explicit Context)',
        "mem add --input [file] --context [context] (batch-add to an explicit Context)",
        "mem add --paste --context [context] (paste into an explicit Context)",
    ),
    "atomize": (
        "mem atomize (enter the current Context's interactive Atomize session)",
        "mem atomize --context [context] (enter that Context's interactive Atomize session)",
        "mem atomize --sessions (enter the interactive Atomize session launcher)",
        'mem atomize --evaluate "[issue]" (directional atomic review)',
    ),
    "branch": (
        "mem branch (choose a local Source and edit a suggested branch name)",
        "mem branch [new_context] (branch the current Context and switch)",
    ),
    "checkout": (
        "mem checkout (enter the interactive Context picker; switch alias)",
        "mem checkout [context] (switch alias)",
        "mem checkout -b (interactive branch-and-checkout)",
        "mem checkout -b [new_context] (branch-and-checkout)",
    ),
    "checkpoint": (
        "mem checkpoint (save without a message)",
        'mem checkpoint "[message]" (describe the saved checkpoint)',
    ),
    "chunk": (
        "mem chunk [memory] (preview a paragraph split, then confirm)",
        "mem chunk [memory] --method [method] (markdown_headers, paragraphs, or sentences)",
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
    "edit": (
        'mem edit [memory] "[new_content]" (replace one direct Memory)',
        "mem edit --input [file] (replace Memories from a batch file)",
        'mem edit [memory] "[new_content]" --context [context] (explicit Context)',
        "mem edit --input [file] --context [context] (batch-edit an explicit Context)",
    ),
    "embed": (
        "mem embed [source_context] --into [target_context]",
    ),
    "eval": (
        "mem eval semantic status (show retained semantic campaign status)",
        "mem eval semantic run [campaign] (run a semantic evaluation campaign)",
    ),
    "find": (
        "mem find (interactive search, multi-target, and scope selector)",
        'mem find "[query]" (current Context, namespace descendants, and embedded Contexts)',
        'mem find "[temporal_query]" (retained history when the query explicitly asks about time)',
        'mem find --context [context] "[query]" (explicit Context root, descendants, and embeds)',
        'mem find --direct "[query]" (selected Context only; no descendants or embeds)',
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
        "mem impact meld (inspect a saved Meld Impact; APPLY? opens its Apply flow)",
        "mem impact meld --session [uid] (inspect an exact saved Meld Impact; APPLY? opens its Apply flow)",
        "mem impact sever (inspect a saved Sever Impact; APPLY? opens its Apply flow)",
        "mem impact sever --session [uid] (inspect an exact saved Sever Impact; APPLY? opens its Apply flow)",
        "mem impact update (inspect the saved Update Impact; APPLY? opens its Apply flow)",
        "mem impact update --session [uid] (inspect the exact saved Update Impact; APPLY? opens its Apply flow)",
        "mem impact --from [source_context] --to [target_context] (directional preview)",
        "mem impact --from [source_context] (current Context is target)",
        "mem impact --to [target_context] (current Context is source)",
    ),
    "import": (
        "mem import profile [profile_name] --from [store] (clean baseline from an external store)",
        "mem import profile [profile_name] --from-profile [source_profile] (clean baseline from a registered Profile)",
        "mem import context [source_context] --from-profile [source_profile] (one Context root)",
        "mem import context [source_context] --from-profile [source_profile] --as [new_root] (renamed Context root)",
        "mem import context [source_context] --from-profile [source_profile] --recursive (Context tree)",
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
        "mem list -R (recursive current-Context listing)",
        "mem list [context] -R (recursive Context listing)",
        "mem list --copy (copy and stage the current listing)",
        "mem list [context] --copy (copy and stage an explicit listing)",
        "mem list --paste (reopen the frozen copied result)",
    ),
    "lock": (
        "mem lock (lock the current Context)",
        "mem lock --recursive (lock the current Context namespace)",
        "mem lock context [context] (lock an explicit Context)",
        "mem lock context [context] --recursive (lock an explicit Context namespace)",
        "mem lock memory [memory] (lock a direct Memory in the current Context)",
        "mem lock memory [memory] --context [context] (lock a direct Memory)",
        "mem lock profile (lock the active Profile)",
    ),
    "log": (
        "mem log (select a Context, then browse its checkpoints in a TTY; print otherwise)",
        'mem log "[query]" (semantic history search)',
        "mem log --operations (Profile command attempts)",
    ),
    "ls": (
        "mem ls (enter the interactive Context browser in a TTY; print otherwise)",
        "mem ls [context] (explicit Context listing)",
        "mem ls -R (recursive current-Context listing)",
        "mem ls [context] -R (recursive Context listing)",
        "mem ls --copy (copy and stage the current listing)",
        "mem ls [context] --copy (copy and stage an explicit listing)",
        "mem ls --paste (reopen the frozen copied result)",
    ),
    "meld": (
        "mem meld (enter the interactive Meld session launcher)",
        "mem meld --sessions (enter the interactive Meld session launcher)",
        "mem meld [context1] [context2] (symmetric into current empty Context)",
        "mem meld [context1] [context2] --to [result_context] (symmetric new Result)",
        "mem meld [context1] [context2] --left-descendants --right-descendants --to [result_context] (symmetric readable subtrees)",
        "mem meld [incoming_context] --into [baseline_context] (directional)",
        "mem meld [incoming_context] --left-descendants --into [baseline_context] (directional incoming subtree)",
        "mem meld --into [baseline_context] (current Context is incoming)",
        "mem meld --from [incoming_context] (current Context is baseline)",
    ),
    "merge": (
        "mem merge [source_context] (merge into the current Context)",
    ),
    "profile": (
        "mem profile (enter the interactive Profile selector in a TTY; list otherwise)",
        "mem profile [profile_name] (select through the concise alias)",
        "mem profile use [profile_name] (select explicitly)",
        "mem profile list (list registered Profiles)",
        "mem profile current (show the active Profile)",
        "mem profile rename [new_name] (rename the active Profile)",
        "mem profile rename [profile_name] [new_name] (rename an explicit Profile)",
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
        'mem query "[question]" (ask the current ordinary Context)',
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
        "mem rationale (open recent Rationale targets or select a Memory)",
        "mem rationale [memory] (explain one current or historical Memory)",
        "mem rationale --context [context] (open Recents; Memory selection starts there)",
        "mem rationale [memory] --context [context] (explicit Context and Memory)",
        "mem rationale [memory] --recorded-only (skip inference and its cache)",
    ),
    "reference": (
        "mem reference [memory] --from [source_context] (add to current Context)",
        "mem reference [memory] --from [source_context] --into [target_context]",
    ),
    "remove": (
        "mem remove [item] (delete a Context or current direct item)",
        "mem remove (select a Context or direct item interactively)",
        "mem remove [item] --context [context] (explicit direct-item scope)",
    ),
    "rename": (
        "mem rename [existing_context] [new_context]",
    ),
    "redo": ("mem redo (redo the most recently undone Context command)",),
    "revert": (
        "mem revert (enter the interactive checkpoint picker; discard newer when applied)",
        "mem revert [checkpoint] (restore exact and discard newer checkpoints)",
        "mem revert [checkpoint] --keep (restore exact and preserve newer checkpoints)",
        'mem revert "[description]" (semantic lookup; discard newer when applied)',
    ),
    "review": (
        "mem review (enter the interactive Review session)",
        "mem review compare (open a saved Compare report)",
        "mem review meld (open a saved Meld report)",
        "mem review sever (open a saved Sever report)",
        "mem review update (open the saved Update report)",
        "mem review [kind] --session [uid] (exact Compare, Meld, Sever, or Update artifact)",
        "mem review atomize (open the current Context's saved Atomize analysis)",
        "mem review atomize --context [context] (Context-bound Atomize review)",
        "mem review ambiguities (analyze current-Context ambiguities)",
        "mem review ambiguities --context [context] (Context-bound Ambiguity review)",
    ),
    "sever": (
        "mem sever (enter the interactive Sever session launcher)",
        "mem sever --sessions (enter the interactive Sever session launcher)",
        "mem sever --source [source_context] --criteria [criteria_context] --save-as [result_context]",
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
    ),
    "summarize": (
        "mem summarize (recursive summary of the current Context)",
        "mem summarize [context] (recursive summary of an explicit Context)",
        "mem summarize --direct (direct Memories in the current Context)",
        "mem summarize [context] --direct (direct Memories in an explicit Context)",
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
        "mem trace (open recent Trace targets or select a Memory)",
        "mem trace [memory] (trace one current or historical Memory)",
        "mem trace --context [context] (open Recents; Memory selection starts there)",
        "mem trace [memory] --context [context] (explicit Context and Memory)",
    ),
    "undo": ("mem undo (undo the latest recorded Context command)",),
    "unlock": (
        "mem unlock (unlock the current Context)",
        "mem unlock --recursive (unlock the current Context namespace)",
        "mem unlock context [context] (unlock an explicit Context)",
        "mem unlock context [context] --recursive (unlock an explicit Context namespace)",
        "mem unlock memory [memory] (unlock a direct Memory in the current Context)",
        "mem unlock memory [memory] --context [context] (unlock a direct Memory)",
        "mem unlock profile (unlock the active Profile)",
    ),
    "update": (
        "mem update (enter the interactive Update session launcher)",
        "mem update --from [source_context] --to [target_context] (explicit direction)",
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


def _command_entries(root: typer.Context) -> list[CommandEntry]:
    commands = _visible_commands(root)
    visible_names = {name for name, _ in commands}
    configured_names = (
        COMMAND_ANNOTATIONS.keys()
        | COMMAND_FORMS.keys()
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
    uncategorized = sorted(visible_names - HELP_CATEGORY_BY_COMMAND.keys())
    if uncategorized:
        typer.secho(
            "Help inventory error: command category missing: "
            + ", ".join(uncategorized),
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
            forms=COMMAND_FORMS.get(name, _default_command_forms(name, command)),
        )
        for name, command in commands
    ]


def _entry_line(
    entry: CommandEntry,
    *,
    name_width: int,
) -> str:
    label = entry.name
    if entry.annotation:
        label += f" ({entry.annotation})"
    return f"{label:<{name_width}} - {entry.description}"


def _render_plain_inventory(entries: list[CommandEntry]) -> None:
    typer.secho("mem command inventory", bold=True)
    typer.echo()

    name_width = max(
        len(entry.name) + (len(entry.annotation) + 3 if entry.annotation else 0)
        for entry in entries
    )
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
    labels = {
        index: display_escape_text(
            entry.name
            + (f" ({entry.annotation})" if entry.annotation else "")
        )
        for index, entry in entries
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
        description_lines = textwrap.wrap(
            display_escape_text(entry.description),
            width=max(1, content_width - len(command_prefix)),
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        for description_index, line in enumerate(description_lines):
            prefix = (
                command_prefix
                if description_index == 0
                else " " * len(command_prefix)
            )
            padding = " " * max(0, content_width - len(prefix) - len(line))
            fragments.append((border_style, vertical))
            if command_focused:
                fragments.append(
                    ("class:selected", f" {prefix}{line}{padding} ")
                )
            else:
                fragments.extend(
                    [
                        ("class:help-command", f" {prefix}"),
                        ("", f"{line}{padding} "),
                    ]
                )
            fragments.append((border_style, vertical + "\n"))
        if expanded:
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
                                "class:selected"
                                if form_focused
                                else "class:form",
                                f" {line:<{content_width}} ",
                            ),
                            (border_style, vertical + "\n"),
                        ]
                    )
    fragments.append(
        (
            border_style,
            ("┗" if focused else "└")
            + horizontal * inner_width
            + ("┛" if focused else "┘")
            + "\n",
        )
    )
    return fragments


def _help_group_width(terminal_columns: int) -> int:
    """Use the complete Help viewport except its one-column scrollbar."""
    return max(36, terminal_columns - 1)


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
    ) -> None:
        label_width = max(len(label) for label, _description in items)
        for item_index, (label, description) in enumerate(items):
            row_focused = (
                selectable
                and focused
                and focused_concept_index == item_index
            )
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
                            (label_style if line_index == 0 else "", row_prefix),
                            ("", line + padding + " "),
                        ]
                    )
                fragments.append(
                    (border_style, ("┃" if guide_focused else "│") + "\n")
                )

    border("CORE CONCEPTS", middle=False)
    rows(HELP_CORE_CONCEPTS, selectable=True)
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
) -> HelpSelection | None:
    """Return the command selected in the terminal, or ``None`` on cancel."""
    if not entries:
        return None
    if require_tty and (
        not sys.stdin.isatty() or not sys.stdout.isatty()
    ):
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
    bindings = KeyBindings()
    navigation_accelerator = NavigationAccelerator()
    app_ref: dict[str, Application[HelpSelection | None]] = {}

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

    def render_entries():
        fragments: list[tuple[str, str]] = []
        app = app_ref.get("app")
        list_focused = app is not None and app.layout.has_focus(list_control)
        terminal_columns = app.output.get_size().columns if app is not None else 80
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
        indexed_entries = list(enumerate(visible_entries["value"]))
        groups: list[tuple[str, list[tuple[int, CommandEntry]]]] = []
        if by_kind:
            for index, entry in indexed_entries:
                category = HELP_CATEGORY_BY_COMMAND.get(entry.name, "OTHER")
                if not groups or groups[-1][0] != category:
                    groups.append((category, []))
                groups[-1][1].append((index, entry))
        else:
            groups.append(("A–Z", indexed_entries))
        for group_index, (title, group_entries) in enumerate(groups):
            group_focused = list_focused and any(
                index == selected_index["value"] for index, _entry in group_entries
            ) and not concept_focus_active()
            fragments.extend(
                _help_group_fragments(
                    group_entries,
                    title=title,
                    width=card_width,
                    focused=group_focused,
                    selected_index=selected_index["value"],
                    expanded_index=expanded_index["value"],
                    selected_form=selected_form["value"],
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
        if (
            concept_focus_active()
            and selected_concept_index["value"] == 0
        ):
            navigation_accelerator.reset()
            focus_in_order(
                event.app,
                (view_control, list_control),
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
            focus_in_order(
                event.app,
                (view_control, list_control),
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
            len(HELP_CORE_CONCEPTS)
            if view_state.selected_uid == "CATEGORY"
            else 0
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
            len(HELP_CORE_CONCEPTS)
            if view_state.selected_uid == "CATEGORY"
            else 0
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
            event.app.invalidate()
            return
        entry = visible_entries["value"][index]
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

    @bindings.add("h", filter=has_focus(list_control))
    def _open_full_help(event) -> None:
        navigation_accelerator.reset()
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
        focus_in_order(
            event.app,
            (view_control, list_control),
            1,
            wrap=False,
        )
        event.app.invalidate()

    @bindings.add("tab")
    def _next_surface(event) -> None:
        navigation_accelerator.reset()
        focus_in_order(
            event.app,
            (view_control, list_control),
            1,
            wrap=True,
        )
        event.app.invalidate()

    @bindings.add("s-tab")
    def _previous_surface(event) -> None:
        navigation_accelerator.reset()
        focus_in_order(
            event.app,
            (view_control, list_control),
            -1,
            wrap=True,
        )
        event.app.invalidate()

    @bindings.add("q", eager=True)
    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(
            [
                ("class:title", " mem help · command inventory"),
            ]
        ),
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
    footer = Window(
        FormattedTextControl(
            lambda: (
                " VIEW: ←/→ choose · ↓ list · Tab surface · Q cancel"
                if app_ref.get("app") is not None
                and app_ref["app"].layout.has_focus(view_control)
                else " ↑/↓ move (hold accelerates)  Tab surface "
                if concept_focus_active()
                else " ↑/↓ move (hold accelerates)  → expand/forms  ← back  "
                + (
                    "Enter open forms  "
                    if selected_form["value"] is None
                    else "Enter prefill command line  "
                )
                + "H full help "
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    application: Application[HelpSelection | None] = Application(
        layout=Layout(
            HSplit([header, view_frame, body, horizontal_rule(), footer]),
            focused_element=list_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=merge_styles(
            [
                MEMCOMMIT_TUI_STYLE,
                Style.from_dict(
                    {
                        "title": "bold",
                        "selected": "fg:#10242f bg:#8bd5ff bold",
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
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return None


def _show_selected_command_help(
    root: typer.Context,
    entry: CommandEntry,
) -> None:
    """Render syntax help without invoking the selected command callback."""
    typer.secho(f"Command: mem {entry.name}", bold=True)
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

    entries = _command_entries(root)
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
    selected = next(
        entry for entry in entries if entry.name == selection.command_name
    )
    _show_selected_command_help(root, selected)
