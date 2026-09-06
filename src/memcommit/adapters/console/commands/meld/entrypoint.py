"""Typer entrypoint and route selection for the Meld command."""

from __future__ import annotations

import sys
from typing import Annotated, Optional
import typer
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract import (
    MemoryRelationProviderError,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    legacy_root_only_option_alias,
)
from memcommit.adapters.console.commands.meld.endpoint_setup import choose_meld_setup
from memcommit.application.operations.meld.model import (
    MeldError,
)
from memcommit.application.operations.meld.provider.contract import (
    MeldProviderError,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.adapters.console.commands.meld.sessions import (
    MeldSessionCatalogError,
    list_meld_session_catalog,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    choose_session,
)
from memcommit.providers.subscription import (
    QueryProviderError,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import (
    ProfileError,
)
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
)

from memcommit.adapters.console.commands.meld.errors import MeldCommandError
from memcommit.adapters.console.commands.meld.interpretation import (
    InterpretedMeldCommand,
    MeldCommandInterpretationError,
    MeldCommandRequest,
    MeldSessionsCommand,
    MeldSetupCommand,
    interpret_meld_command,
)
from memcommit.adapters.console.commands.meld.presentation import (
    _meld_picker_entry,
)
from memcommit.adapters.console.commands.meld.workflow import (
    _resume_picked_meld,
    execute_meld_command,
)


def _browse_saved_meld_sessions(store: MemoryStore) -> None:
    """Select one saved Meld by metadata, then reopen its exact persisted route."""
    catalog = list_meld_session_catalog(store)
    if not catalog and not (sys.stdin.isatty() and sys.stdout.isatty()):
        typer.echo("No saved Meld sessions.")
        return
    by_key = {entry.key: entry for entry in catalog}
    receipt = choose_session(
        tuple(_meld_picker_entry(entry) for entry in catalog),
        title="MELD SESSIONS · RECENTLY MODIFIED",
        new_receipt=SessionNewReceipt(kind="meld", argv=("mem", "meld")),
    )
    if receipt is None:
        return
    if isinstance(receipt, SessionNewReceipt):
        if receipt.kind != "meld" or receipt.argv != ("mem", "meld"):
            raise MeldCommandError("Meld session picker returned an invalid receipt.")
        _start_new_meld_from_setup(store)
        return
    if not isinstance(receipt, SessionOpenReceipt) or receipt.kind != "meld":
        raise MeldCommandError("Meld session picker returned an invalid receipt.")
    entry = by_key.get(receipt.key)
    if entry is None or receipt.argv != entry.reopen_argv:
        raise MeldCommandError("Meld session picker returned an invalid receipt.")
    # The argv is a user-visible receipt, not an instruction to execute.  The
    # target UID reload below is authoritative and its saved frames are bound
    # again before any workbench is opened.
    _resume_picked_meld(store=store, entry=entry)


def _start_new_meld_from_setup(store: MemoryStore) -> None:
    """Collect one new Meld request without browsing saved sessions."""
    receipt = choose_meld_setup(store)
    if receipt is None:
        typer.echo("New Meld cancelled; no session was created.")
        return
    right = receipt.right_name

    def replaces_existing_target(target_name: str) -> bool:
        try:
            target = store.load_direct(target_name)
        except FileNotFoundError:
            return False
        return store.load_meld_session(target.uid) is not None

    if receipt.mode == "directional":
        restart_existing = replaces_existing_target(right)
        start_kwargs = {
            "into": right,
            "left_descendants": receipt.left_descendants,
            "right_descendants": receipt.right_descendants,
        }
        if receipt.inline_source_content is not None:
            start_kwargs["memory"] = receipt.inline_source_content
        else:
            start_kwargs["left"] = receipt.left_name
        if restart_existing:
            # Choosing New is the explicit replacement signal when setup
            # resolves to a target that already owns even an indistinguishable
            # saved request.
            start_kwargs["restart"] = True
        if receipt.left_memory_uid is not None:
            start_kwargs["incoming_memory"] = receipt.left_memory_uid
        if receipt.right_memory_uid is not None:
            start_kwargs["baseline_memory"] = receipt.right_memory_uid
        cmd(**start_kwargs)
        return

    if receipt.target_name is None:
        raise MeldCommandError("Symmetric Meld setup omitted result C.")
    if receipt.left_name is None:
        raise MeldCommandError("Symmetric Meld setup omitted Source A.")
    start_kwargs = {
        "left": receipt.left_name,
        "right": right,
        "to": receipt.target_name,
        "left_descendants": receipt.left_descendants,
        "right_descendants": receipt.right_descendants,
    }
    if replaces_existing_target(receipt.target_name):
        start_kwargs["restart"] = True
    cmd(**start_kwargs)


def cmd(
    left: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Directional INCOMING A, or symmetric PEER A when a third "
                "RESULT or two-source --to is supplied; an unambiguously "
                "non-Context sole sentence is inline Memory content"
            )
        ),
    ] = None,
    right: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Directional BASELINE B, or symmetric PEER B when a third "
                "RESULT or two-source --to is supplied"
            )
        ),
    ] = None,
    result: Annotated[
        Optional[str],
        typer.Argument(
            help=("Symmetric RESULT C; equivalent to --to and created when absent")
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help=(
                "Explicit directional BASELINE alias for 'mem meld INCOMING BASELINE'"
            ),
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help=(
                "Directional BASELINE when fewer than two positional sources "
                "are supplied; otherwise symmetric RESULT C, created when absent"
            ),
        ),
    ] = None,
    from_: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=(
                "Directional INCOMING Context or unambiguous inline Memory; "
                "--to may name BASELINE, otherwise current supplies it"
            ),
        ),
    ] = None,
    issue: Annotated[
        Optional[str],
        typer.Option(
            "--issue",
            help="Issue number or unique uid prefix for this comment",
        ),
    ] = None,
    choice: Annotated[
        Optional[int],
        typer.Option(
            "--choice",
            min=1,
            help="Choose one displayed reading for --issue",
        ),
    ] = None,
    comment: Annotated[
        Optional[str],
        typer.Option(
            "--comment",
            help="Explain one issue or guide all remaining relations",
        ),
    ] = None,
    expect_session: Annotated[
        Optional[str],
        typer.Option(
            "--expect-session",
            metavar="SHA256",
            help="Require the exact saved Meld revision reviewed for this turn",
        ),
    ] = None,
    preserve_all: Annotated[
        bool,
        typer.Option(
            "--preserve-all",
            help="Ask to retain every remaining source distinction",
        ),
    ] = False,
    defer_all: Annotated[
        bool,
        typer.Option(
            "--defer-all",
            help="Close as review-only without applying the target",
        ),
    ] = False,
    accept: Annotated[
        bool,
        typer.Option(
            "--accept",
            help="Apply the exact ready proposal without another model call",
        ),
    ] = False,
    restart: Annotated[
        bool,
        typer.Option(
            "--restart",
            help=(
                "Replace the saved review session after rechecking its bound Contexts"
            ),
        ),
    ] = False,
    revision: Annotated[
        Optional[str],
        typer.Option(
            "--revision",
            help="How the comment relates to prior dialogue",
        ),
    ] = None,
    revises_turn: Annotated[
        list[str] | None,
        typer.Option(
            "--revises-turn",
            help="Prior turn uid for a correction or retraction",
        ),
    ] = None,
    expand: Annotated[
        Optional[str],
        typer.Option(
            "--expand",
            help="Render one issue's complete options provider-free",
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Enter the interactive Meld session launcher",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Use only the selected LEFT/INCOMING and RIGHT/BASELINE roots",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both Meld roots",
        ),
    ] = False,
    left_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--left-descendants/--left-root-only",
            legacy_root_only_option_alias("left"),
            help="Include all readable descendants under PEER or INCOMING A",
        ),
    ] = None,
    right_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--right-descendants/--right-root-only",
            legacy_root_only_option_alias("right"),
            help=(
                "Include readable descendants under PEER B, or writable "
                "owner Contexts under directional BASELINE B"
            ),
        ),
    ] = None,
    memory: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            "-m",
            help=(
                "Use exact text as one process-local INCOMING Memory; the "
                "current Context, --into, or directional --to supplies BASELINE"
            ),
        ),
    ] = None,
    incoming_memory: Annotated[
        Optional[str],
        typer.Option(
            "--incoming-memory",
            metavar="UID_OR_PREFIX",
            help=(
                "In directional Meld, select one INCOMING Memory while its "
                "neighbors remain non-actionable context"
            ),
        ),
    ] = None,
    baseline_memory: Annotated[
        Optional[str],
        typer.Option(
            "--baseline-memory",
            metavar="UID_OR_PREFIX",
            help=(
                "In directional Meld, restrict mutation to one BASELINE Memory "
                "while its neighbors remain non-actionable context"
            ),
        ),
    ] = None,
) -> None:
    """Meld INCOMING Context/Memory into BASELINE; add RESULT for peers."""
    store = MemoryStore(create=False)
    try:
        interpreted = interpret_meld_command(
            MeldCommandRequest(
                left=left,
                right=right,
                result=result,
                into=into,
                to=to,
                from_=from_,
                issue=issue,
                choice=choice,
                comment=comment,
                expect_session=expect_session,
                preserve_all=preserve_all,
                defer_all=defer_all,
                accept=accept,
                restart=restart,
                revision=revision,
                revises_turn=tuple(revises_turn or ()),
                expand=expand,
                sessions=sessions,
                direct=direct,
                recursive=recursive,
                left_descendants=left_descendants,
                right_descendants=right_descendants,
                memory=memory,
                incoming_memory=incoming_memory,
                baseline_memory=baseline_memory,
            ),
            store=store,
        )
        if isinstance(interpreted, MeldSessionsCommand):
            _browse_saved_meld_sessions(store)
            return
        if isinstance(interpreted, MeldSetupCommand):
            _start_new_meld_from_setup(store)
            return
        if not isinstance(interpreted, InterpretedMeldCommand):
            raise MeldCommandError("Meld interpretation returned an invalid route.")
        execute_meld_command(
            store=store,
            request=interpreted,
        )
    except MeldCommandInterpretationError as error:
        typer.secho(
            f"Meld error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        MemoryRelationProviderError,
        ConcurrentContextUpdateError,
        MeldError,
        MeldProviderError,
        MeldCommandError,
        MeldSessionCatalogError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
    ) as error:
        typer.secho(f"Meld error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
