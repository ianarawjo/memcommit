"""Browse implementation levels for the top-level CLI."""
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


IMPLEMENTATION_LEVELS = {
    "add": "implemented",
    "atomize": "implemented",
    "branch": "implemented",
    "checkout": "alias",
    "checkpoint": "implemented",
    "chunk": "implemented",
    "clear": "implemented",
    "compare": "implemented",
    "config": "legacy",
    "contexts": "implemented",
    "delete": "implemented",
    "diff": "partial",
    "edit": "implemented",
    "embed": "implemented",
    "find": "implemented",
    "find-ambiguities": "implemented",
    "find-conflicts": "implemented",
    "find-duplicates": "implemented",
    "forget": "legacy",
    "ground": "partial",
    "help": "implemented",
    "impact": "partial",
    "init": "implemented",
    "integrate": "legacy",
    "list": "implemented",
    "lock": "implemented",
    "log": "implemented",
    "ls": "implemented",
    "meld": "partial",
    "merge": "partial",
    "profile": "implemented",
    "query": "implemented",
    "rationale": "implemented",
    "reference": "implemented",
    "rename": "implemented",
    "remove": "implemented",
    "revert": "implemented",
    "review": "partial",
    "shell-init": "implemented",
    "show": "implemented",
    "status": "implemented",
    "switch": "implemented",
    "trace": "implemented",
    "translate": "implemented",
    "undo": "implemented",
    "unlock": "implemented",
    "update": "partial",
}

LEVEL_DESCRIPTIONS = (
    "implemented = advertised behavior is available",
    "partial = only a bounded subset is available",
    "legacy = older path outside the current workflow",
    "alias = alternate name for another command",
)


@dataclass(frozen=True)
class CommandEntry:
    """One visible command and the inventory metadata used to present it."""

    name: str
    level: str
    description: str
    command: object


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
    missing = sorted(visible_names - IMPLEMENTATION_LEVELS.keys())
    stale = sorted(IMPLEMENTATION_LEVELS.keys() - visible_names)
    if missing or stale:
        details = []
        if missing:
            details.append("unclassified: " + ", ".join(missing))
        if stale:
            details.append("not registered: " + ", ".join(stale))
        typer.secho(
            "Help inventory error: " + "; ".join(details),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    return [
        CommandEntry(
            name=name,
            level=IMPLEMENTATION_LEVELS[name],
            description=" ".join(
                (getattr(command, "help", None) or "No description.").split()
            ),
            command=command,
        )
        for name, command in commands
    ]


def _entry_line(
    entry: CommandEntry,
    *,
    name_width: int,
    level_width: int,
) -> str:
    return (
        f"{entry.name:<{name_width}} - "
        f"{entry.level:<{level_width}} - "
        f"{entry.description}"
    )


def _render_plain_inventory(entries: list[CommandEntry]) -> None:
    typer.secho("mem command inventory", bold=True)
    typer.echo("Levels: " + "; ".join(LEVEL_DESCRIPTIONS))
    typer.echo()

    name_width = max(len(entry.name) for entry in entries)
    level_width = max(len(entry.level) for entry in entries)
    for entry in entries:
        typer.echo(
            _entry_line(
                entry,
                name_width=name_width,
                level_width=level_width,
            )
        )


def run_help_selector(
    entries: list[CommandEntry],
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Return the command selected in the terminal, or ``None`` on cancel."""
    if not entries:
        return None
    if require_tty and (
        not sys.stdin.isatty() or not sys.stdout.isatty()
    ):
        raise ValueError("Interactive help requires a terminal.")

    selected_index = {"value": 0}
    name_width = max(len(entry.name) for entry in entries)
    level_width = max(len(entry.level) for entry in entries)
    bindings = KeyBindings()

    def render_entries():
        fragments: list[tuple[str, str]] = []
        for index, entry in enumerate(entries):
            selected = index == selected_index["value"]
            if selected:
                # This marker lets prompt-toolkit scroll the long inventory so
                # the selected row remains visible in short terminals.
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    "class:selected" if selected else "",
                    ("› " if selected else "  ")
                    + _entry_line(
                        entry,
                        name_width=name_width,
                        level_width=level_width,
                    )
                    + "\n",
                )
            )
        return fragments

    def move(delta: int) -> None:
        selected_index["value"] = max(
            0,
            min(
                selected_index["value"] + delta,
                len(entries) - 1,
            ),
        )

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
        move(10)
        event.app.invalidate()

    @bindings.add("pageup")
    def _previous_page(event) -> None:
        move(-10)
        event.app.invalidate()

    @bindings.add("home")
    def _first_command(event) -> None:
        selected_index["value"] = 0
        event.app.invalidate()

    @bindings.add("end")
    def _last_command(event) -> None:
        selected_index["value"] = len(entries) - 1
        event.app.invalidate()

    @bindings.add("enter")
    def _show_command_help(event) -> None:
        event.app.exit(result=entries[selected_index["value"]].name)

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
                ("class:title", " mem help · command inventory\n"),
                ("", " implemented · partial · legacy · alias"),
            ]
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    body = Window(
        list_control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    footer = Window(
        FormattedTextControl(
            " ↑/↓ move  PgUp/PgDn jump  Enter command help  q/Esc cancel "
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    application: Application[str | None] = Application(
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
    """Browse command levels and open syntax help for a selection."""
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
        selected_name = run_help_selector(
            entries,
            app_output=_selection_output(),
            require_tty=False,
        )
        if selected_name is not None:
            typer.echo(selected_name)
        return

    if not _interactive_terminal():
        _render_plain_inventory(entries)
        return

    selected_name = run_help_selector(entries)
    if selected_name is None:
        return
    selected = next(
        entry for entry in entries if entry.name == selected_name
    )
    _show_selected_command_help(root, selected)
