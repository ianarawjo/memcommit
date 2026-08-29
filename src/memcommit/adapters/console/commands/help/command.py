"""Present the top-level Help command and wire its reusable browser backend."""

from __future__ import annotations

import shutil
import sys
from typing import Annotated

import typer

from memcommit.adapters.console.commands.help.command_handoff import (
    edit_help_command,
    run_help_command,
)
from memcommit.adapters.console.commands.help.inventory import (
    COMMAND_ANNOTATIONS,
    COMMAND_DISPLAY_ALIASES,
    COMMAND_FORMS,
    COMMAND_RELATED_FORMS,
    HELP_CATEGORY_BY_COMMAND,
    HELP_CATEGORY_DESCRIPTIONS,
    HELP_CATEGORY_GROUPS,
    HELP_CATEGORY_ORDER,
    HELP_COMMAND_ORDER,
    HELP_COMMON_KEYS,
    HELP_COMMON_LOCATORS,
    HELP_CORE_CONCEPT_STYLES,
    HELP_CORE_CONCEPTS,
    CommandEntry,
    HelpSelection,
    _selectable_form_line,
    command_entries,
)
from memcommit.adapters.console.commands.help.rendering import (
    _entry_label,
    _entry_label_lines,
    _entry_line,
    _help_command_rows,
    _help_group_fragments,
    _help_group_width,
    _help_information_box_fragments,
    _help_list_viewport_height,
    _help_section_heading_fragments,
    _ordered_help_entries,
    _render_plain_inventory,
    _wrap_prefixed_terminal_text,
    render_help_lookup_entries,
)
from memcommit.adapters.console.commands.help.selector import (
    NavigationAccelerator,
    bind_focused_frame_style,
    run_help_selector,
)
from memcommit.adapters.console.commands.help.study_copy_guard import (
    active_profile_is_study,
    authored_study_help_fields,
    find_study_help_copy_match,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.help.composer import compose_operation_help
from memcommit.application.operations.help.lookup_application import (
    HelpLookupError,
    execute_help_lookup,
    prepare_help_lookup,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.persistence.command_ledger.study_actions import (
    record_study_help_lookup_completed,
    record_study_help_lookup_submitted,
)
from memcommit.providers.operation_connections import connect_help_provider
from memcommit.providers.subscription import QueryProviderError


# The command module was the original owner of the complete Help implementation.
# Keep its imported names available while production callers migrate to the
# focused inventory, rendering, and selector modules.
__all__ = [
    "COMMAND_ANNOTATIONS",
    "COMMAND_DISPLAY_ALIASES",
    "COMMAND_FORMS",
    "COMMAND_RELATED_FORMS",
    "HELP_CATEGORY_BY_COMMAND",
    "HELP_CATEGORY_DESCRIPTIONS",
    "HELP_CATEGORY_GROUPS",
    "HELP_CATEGORY_ORDER",
    "HELP_COMMAND_ORDER",
    "HELP_COMMON_KEYS",
    "HELP_COMMON_LOCATORS",
    "HELP_CORE_CONCEPT_STYLES",
    "HELP_CORE_CONCEPTS",
    "CommandEntry",
    "HelpSelection",
    "NavigationAccelerator",
    "_entry_label",
    "_entry_label_lines",
    "_entry_line",
    "_help_command_rows",
    "_help_group_fragments",
    "_help_group_width",
    "_help_information_box_fragments",
    "_help_list_viewport_height",
    "_help_section_heading_fragments",
    "_ordered_help_entries",
    "_render_plain_inventory",
    "_selectable_form_line",
    "_wrap_prefixed_terminal_text",
    "bind_focused_frame_style",
    "cmd",
    "command_entries",
    "render_help_lookup_entries",
    "run_help_selector",
]


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

    if not _interactive_terminal():
        _render_plain_inventory(entries)
        return

    selection = run_help_selector(entries)
    if selection is None:
        return
    if not selection.show_help:
        try:
            argv = edit_help_command(
                selection.command_name,
                selection.command_line,
            )
            if argv is None:
                return
            exit_code = run_help_command(argv)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            typer.secho(
                f"Help error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1) from error
        if exit_code:
            raise typer.Exit(exit_code)
        return
    selected = next(entry for entry in entries if entry.name == selection.command_name)
    _show_selected_command_help(root, selected)


# The command owns Help inventory semantics; the reusable session component
# receives that behavior through an explicit adapter instead of importing a
# command module back upward.
from memcommit.adapters.console.terminal.components.session_help import (  # noqa: E402
    configure_session_help_backend,
)

configure_session_help_backend(
    entry_builder=command_entries,
    selector=run_help_selector,
)
