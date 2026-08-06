"""Browse the top-level CLI command inventory."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Annotated

import typer
from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.output.defaults import create_output
from prompt_toolkit.styles import Style


COMMAND_ANNOTATIONS = {
    "config": "legacy",
    "integrate": "legacy",
}

COMMAND_FORMS = {
    "add": (
        'mem add "[memory]" (add one Memory to the current Context)',
        "mem add --input [file] (add one Memory per non-empty line)",
        "mem add --paste (paste one or more Memories)",
        'mem add "[memory]" --context [context] (add to an explicit Context)',
    ),
    "atomize": (
        "mem atomize (analyze the current Context)",
        "mem atomize --context [context] (analyze one Context)",
        "mem atomize --sessions (browse saved work)",
        'mem atomize --evaluate "[issue]" (directional atomic review)',
    ),
    "branch": (
        "mem branch [new_context] (branch the current Context)",
    ),
    "checkout": (
        "mem checkout [context] (switch alias)",
        "mem checkout -b [new_context] (branch alias)",
    ),
    "checkpoint": (
        'mem checkpoint "[message]" (describe the saved checkpoint)',
    ),
    "compare": (
        "mem compare (interactive saved-work view)",
        "mem compare --to [context2] (current Context is context1)",
        "mem compare --from [context1] --to [context2] (explicit Contexts)",
    ),
    "diff": (
        "mem diff (render the active update)",
        "mem diff --raw (exact unified diff)",
        "mem diff --stat (summary only)",
    ),
    "edit": (
        'mem edit [memory] "[new_content]" (replace one direct Memory)',
        "mem edit --input [file] (replace Memories from a batch file)",
    ),
    "embed": (
        "mem embed [source_context] --into [target_context]",
    ),
    "find": (
        'mem find "[query]" (current projection)',
        'mem find --history "[query]" (retained history)',
    ),
    "forget": (
        'mem forget "[memory_description]" (select matching Memories)',
    ),
    "ground": (
        "mem ground (interactive Ground picker)",
        "mem ground [ground_name] (open or create a named Ground)",
        'mem ground --request "[request]" (start from a natural-language request)',
    ),
    "help": ("mem help (interactive command inventory)",),
    "impact": (
        "mem impact --from [source_context] --to [target_context] (directional preview)",
        "mem impact atomize --context [context] (atomization preview)",
    ),
    "integrate": (
        'mem integrate "[memory]" (legacy semantic integration)',
    ),
    "list": (
        "mem list (interactive current-Context browser)",
        "mem list [context] (explicit Context listing)",
        "mem list [context] -R (recursive Context listing)",
    ),
    "log": (
        "mem log (interactive checkpoint history)",
        'mem log "[query]" (semantic history search)',
        "mem log --operations (Profile command attempts)",
    ),
    "ls": (
        "mem ls (interactive current-Context browser)",
        "mem ls [context] (explicit Context listing)",
        "mem ls [context] -R (recursive Context listing)",
    ),
    "meld": (
        "mem meld (interactive saved-work view)",
        "mem meld [context1] [context2] (symmetric)",
        "mem meld [context1] [context2] --to [result_context] (symmetric new Result)",
        "mem meld [incoming_context] --into [baseline_context] (directional)",
        "mem meld --from [incoming_context] (current Context is baseline)",
    ),
    "merge": (
        "mem merge [source_context] (merge into the current Context)",
    ),
    "query": (
        'mem query "[question]" (ask the current ordinary Context)',
        'mem query --context [context] "[question]" (ask an explicit ordinary Context)',
        'mem query [query_view] "[question]" (ask a query-only view)',
        "mem query --sessions (list saved query transcripts)",
    ),
    "reference": (
        "mem reference [memory] --from [source_context] (add to current Context)",
        "mem reference [memory] --from [source_context] --into [target_context]",
    ),
    "remove": (
        "mem remove [memory] (remove from the current Context)",
        "mem remove [memory] --context [context] (remove from an explicit Context)",
    ),
    "rename": (
        "mem rename [current_context] [new_context]",
    ),
    "revert": (
        "mem revert (interactive checkpoint picker)",
        "mem revert [checkpoint] (exact UID or prefix)",
        'mem revert "[description]" (semantic checkpoint lookup)',
    ),
    "review": (
        "mem review (interactive saved-review picker)",
        "mem review [kind] (open an operation report)",
        "mem review [kind] --session [uid] (exact saved artifact)",
    ),
    "sever": (
        "mem sever (interactive saved-work view)",
        "mem sever --source [source_context] --criteria [criteria_context] --save-as [result_context]",
        "mem sever --resume [uid] (resume exact saved work)",
    ),
    "share": (
        "mem share (interactive Source and endpoint selection)",
        "mem share [source_context] --to [endpoint] (explicit delivery)",
    ),
    "switch": (
        "mem switch (interactive Context picker)",
        "mem switch [context] (explicit Context)",
    ),
    "translate": (
        "mem translate --to [language] (current Context)",
        "mem translate [memory] --to [language] (one direct Memory)",
        "mem translate --to [language] --save-as [result_context] (new translated Context)",
    ),
    "update": (
        "mem update --from [source_context] --to [target_context] (explicit direction)",
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
    for parameter in getattr(command, "params", ()):
        if getattr(parameter, "param_type_name", "") != "argument":
            continue
        label = str(
            getattr(parameter, "metavar", None)
            or getattr(parameter, "human_readable_name", "VALUE")
        ).lower()
        if getattr(parameter, "nargs", 1) != 1:
            label += "..."
        operands.append(f"[{label}]")
    suffix = " " + " ".join(operands) if operands else ""
    return (f"mem {name}{suffix}",)


def _visible_commands(ctx: typer.Context) -> list[tuple[str, object]]:
    """Return visible root commands in the same canonical order as Click."""
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
    return commands


def _command_entries(root: typer.Context) -> list[CommandEntry]:
    commands = _visible_commands(root)
    visible_names = {name for name, _ in commands}
    stale = sorted(
        (COMMAND_ANNOTATIONS.keys() | COMMAND_FORMS.keys()) - visible_names
    )
    if stale:
        typer.secho(
            "Help inventory error: annotated command not registered: "
            + ", ".join(stale),
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

    selected_index = {"value": 0}
    expanded_index: dict[str, int | None] = {"value": None}
    selected_form: dict[str, int | None] = {"value": None}
    name_width = max(
        len(entry.name) + (len(entry.annotation) + 3 if entry.annotation else 0)
        for entry in entries
    )
    bindings = KeyBindings()

    def render_entries():
        fragments: list[tuple[str, str]] = []
        for index, entry in enumerate(entries):
            command_selected = (
                index == selected_index["value"]
                and selected_form["value"] is None
            )
            expanded = index == expanded_index["value"]
            if command_selected:
                # This marker lets prompt-toolkit scroll the long inventory so
                # the selected row remains visible in short terminals.
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    "class:selected" if command_selected else "",
                    ("▾ " if expanded else "▸ ")
                    + _entry_line(
                        entry,
                        name_width=name_width,
                    )
                    + "\n",
                )
            )
            if not expanded:
                continue
            for form_index, form in enumerate(entry.forms):
                form_selected = (
                    index == selected_index["value"]
                    and selected_form["value"] == form_index
                )
                if form_selected:
                    fragments.append(("[SetCursorPosition]", ""))
                fragments.append(
                    (
                        "class:selected" if form_selected else "class:form",
                        f"    FORM {form_index + 1} · {form}\n",
                    )
                )
        return fragments

    def move(delta: int) -> None:
        form_index = selected_form["value"]
        if form_index is not None:
            forms = entries[selected_index["value"]].forms
            candidate = form_index + delta
            if candidate < 0:
                selected_form["value"] = None
            elif candidate < len(forms):
                selected_form["value"] = candidate
            else:
                selected_form["value"] = None
                expanded_index["value"] = None
                selected_index["value"] = min(
                    selected_index["value"] + 1,
                    len(entries) - 1,
                )
            return
        previous = selected_index["value"]
        selected_index["value"] = max(
            0,
            min(
                selected_index["value"] + delta,
                len(entries) - 1,
            ),
        )
        if selected_index["value"] != previous:
            expanded_index["value"] = None

    @bindings.add("down")
    def _next_command(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up")
    def _previous_command(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("pagedown")
    def _next_page(event) -> None:
        selected_form["value"] = None
        expanded_index["value"] = None
        selected_index["value"] = min(
            selected_index["value"] + 10,
            len(entries) - 1,
        )
        event.app.invalidate()

    @bindings.add("pageup")
    def _previous_page(event) -> None:
        selected_form["value"] = None
        expanded_index["value"] = None
        selected_index["value"] = max(selected_index["value"] - 10, 0)
        event.app.invalidate()

    @bindings.add("home")
    def _first_command(event) -> None:
        selected_form["value"] = None
        expanded_index["value"] = None
        selected_index["value"] = 0
        event.app.invalidate()

    @bindings.add("end")
    def _last_command(event) -> None:
        selected_form["value"] = None
        expanded_index["value"] = None
        selected_index["value"] = len(entries) - 1
        event.app.invalidate()

    @bindings.add("enter")
    def _select_row(event) -> None:
        index = selected_index["value"]
        form_index = selected_form["value"]
        if form_index is None:
            command_line = f"mem {entries[index].name}"
        else:
            command_line = _selectable_form_line(entries[index].forms[form_index])
        event.app.exit(
            result=HelpSelection(
                command_name=entries[index].name,
                command_line=command_line,
            )
        )

    @bindings.add("right")
    def _expand(event) -> None:
        index = selected_index["value"]
        if expanded_index["value"] != index:
            expanded_index["value"] = index
            selected_form["value"] = 0
        elif selected_form["value"] is None:
            selected_form["value"] = 0
        event.app.invalidate()

    @bindings.add("left")
    def _collapse(event) -> None:
        if selected_form["value"] is not None:
            selected_form["value"] = None
        elif expanded_index["value"] == selected_index["value"]:
            expanded_index["value"] = None
        event.app.invalidate()

    @bindings.add("h")
    def _open_full_help(event) -> None:
        entry = entries[selected_index["value"]]
        event.app.exit(
            result=HelpSelection(
                command_name=entry.name,
                command_line=f"mem {entry.name}",
                show_help=True,
            )
        )

    @bindings.add("q", eager=True)
    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    list_control = FormattedTextControl(
        text=render_entries,
        focusable=True,
        show_cursor=False,
    )
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
    footer = Window(
        FormattedTextControl(
            " ↑/↓ move  → expand/forms  ← back  Enter select  H full help "
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    application: Application[HelpSelection | None] = Application(
        layout=Layout(
            HSplit([header, body, footer]),
            focused_element=list_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=Style.from_dict(
            {
                "title": "bold",
                "selected": "reverse",
                "form": "fg:#cad3f5",
            }
        ),
    )
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
    """Browse commands and open syntax help for a selection."""
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
