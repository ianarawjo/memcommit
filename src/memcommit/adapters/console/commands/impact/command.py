"""Preview new effects or inspect saved operation-owned Impact artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional

import typer

from memcommit.models.context import Context

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.adapters.console.coordination.command_group import CanonicalCommandGroup

from memcommit.adapters.console.commands.atomize.impact import (
    open_saved_atomize_impact as _saved_atomize_impact,
    run_atomize_impact as _atomize_impact,
)
from memcommit.application.operations.atomize.domain import AtomizeImpactError
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.adapters.console.commands.impact.catalog import choose_impact_session
from memcommit.adapters.console.commands.distill.impact import (
    distill_cmd as distill_impact_cmd,
)
from memcommit.adapters.console.commands.elaborate.impact import (
    elaborate_cmd as elaborate_impact_cmd,
)
from memcommit.adapters.console.commands.makemore.impact import (
    makemore_cmd as makemore_impact_cmd,
)
from memcommit.adapters.console.commands.impact.registry import (
    install_impact_routes,
)
from memcommit.adapters.console.commands.sever.impact import (
    open_saved_sever_impact as _saved_sever_impact,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.application.capabilities.local_target_lookup import (
    DirectMemoryAmbiguityError,
    resolve_local_context_memory_target,
)
from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.core.context_targeting.uid_locator import is_memory_uid_prefix
from memcommit.core.context_targeting.model import DirectMemoryLocator
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.persistence.store import ProfileStore


app = typer.Typer(
    cls=CanonicalCommandGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    help=(
        "Preview operation-owned effects without applying them, "
        "or browse saved Impact analyses with --sessions."
    ),
)


class ImpactOperation(str, Enum):
    """Saved Impact operations supported by the shared launcher."""

    atomize = "atomize"
    sever = "sever"


def _usage_error(message: str) -> None:
    typer.secho(f"Impact error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(2)


def _operation_session_impact(
    *,
    operation: ImpactOperation,
    session_uid: str | None,
    show_all: bool = False,
) -> None:
    try:
        store = ProfileStore(create=False)
        runners = {
            ImpactOperation.sever: _saved_sever_impact,
        }
        if operation is ImpactOperation.atomize:
            _saved_atomize_impact(
                store,
                session_uid=session_uid,
                show_all=show_all,
            )
        else:
            runners[operation](store, session_uid=session_uid)
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def _browse_impact_sessions(
    *,
    operation: ImpactOperation | None = None,
    show_all: bool = False,
) -> None:
    """Select a durable Impact artifact, then enter its exact saved route."""

    try:
        store = ProfileStore(create=False)
        receipt = choose_impact_session(
            store,
            kinds=(None if operation is None else (operation.value,)),
            title=(
                "MEM IMPACT · SAVED ANALYSES"
                if operation is None
                else f"MEM IMPACT · {operation.value.upper()} ANALYSES"
            ),
        )
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if receipt is None:
        annotate_command_outcome("CANCELLED")
        typer.echo("Impact selection cancelled; no analysis was opened.")
        return
    _operation_session_impact(
        operation=ImpactOperation(receipt.kind),
        session_uid=receipt.key,
        show_all=show_all,
    )


def _dispatch_impact(
    *,
    operation: ImpactOperation,
    session_uid: str | None = None,
    sessions: bool = False,
    context_name: str | None = None,
    memory_selector: str | None = None,
    show_all: bool = False,
    refresh: bool = False,
    auto_context_memory_operand: str | None = None,
) -> None:
    """Prepare Atomize or open an operation-owned saved Impact artifact."""
    if operation is not ImpactOperation.atomize:
        _operation_session_impact(operation=operation, session_uid=session_uid)
        return
    if sessions and session_uid is not None:
        _usage_error(
            "use either '--sessions' to browse saved Atomize analyses or "
            "'--session UID' to reopen one exact analysis."
        )

    if sessions or session_uid is not None:
        if (
            context_name is not None
            or memory_selector is not None
            or auto_context_memory_operand is not None
            or refresh
        ):
            _usage_error(
                "saved Atomize Impact selection cannot be combined with "
                "Context, Memory, or reanalysis options."
            )
        if sessions:
            _browse_impact_sessions(
                operation=ImpactOperation.atomize, show_all=show_all
            )
        else:
            _operation_session_impact(
                operation=ImpactOperation.atomize,
                session_uid=session_uid,
                show_all=show_all,
            )
        return

    try:
        store = ProfileStore(create=False)
        context_snapshot = ContextOperandSnapshot.capture(store)
        if auto_context_memory_operand is not None:
            auto_target = resolve_local_context_memory_target(
                store,
                auto_context_memory_operand,
                current=context_snapshot.current_name,
            )
            canonical_context_name = (
                auto_target.name
                if isinstance(auto_target, Context)
                else auto_target[0].name
            )
            if isinstance(auto_target, tuple):
                memory_selector = auto_target[1].uid
            else:
                assert isinstance(auto_target, Context)
        else:
            canonical_context_name = (
                resolve_existing_context_operand(
                    freeze_local_context_operand_candidates(store),
                    context_name,
                    current=context_snapshot.current_name,
                ).name
                if context_name is not None
                else context_snapshot.current_name
            )
        if not canonical_context_name:
            raise AtomizeImpactError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    _atomize_impact(
        store=store,
        context_name=canonical_context_name,
        show_all=show_all,
        refresh=refresh,
        memory_selector=memory_selector,
    )

    return


@app.callback(invoke_without_command=True)
def cmd(
    ctx: typer.Context,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Browse every saved analysis inspectable through Impact",
        ),
    ] = False,
) -> None:
    """Choose an operation or browse its saved Impact artifacts."""
    if ctx.invoked_subcommand is not None:
        if sessions:
            _usage_error(
                "root '--sessions' cannot be combined with a named Impact "
                "operation; put operation-specific options after its name."
            )
        return
    if sessions:
        _browse_impact_sessions()
        return
    _usage_error(
        "choose an Impact operation or browse saved analyses with '--sessions'."
    )


def merge_impact_cmd() -> None:
    """Describe deferred Merge Impact without preparing or loading anything."""
    # TODO(merge-impact): Build a validated KEEP_BOTH result through Merge's
    # preparation/Resolve contracts and reuse its Preview projection read-only.
    # Keep this auxiliary view here; it must not become another Apply pipeline.
    typer.echo(
        "IMPACT MERGE · NOT IMPLEMENTED\n"
        "Planned: Source + Target → KEEP BOTH → Merge Preview.\n"
        "Show the complete result and changes with Context:Memory identifiers.\n"
        "Read-only preview; no Apply or saving."
    )


def atomize_impact_cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="TARGET",
            help=(
                "Auto-typed existing Context, Memory UID/prefix, or "
                "CONTEXT:UID (defaults to current Context)"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to analyze (defaults to current)",
        ),
    ] = None,
    memory_selector: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            "-m",
            metavar="UID_OR_PREFIX",
            help="Analyze one direct Memory with its neighbors as context",
        ),
    ] = None,
    show_all: Annotated[
        bool,
        typer.Option("--all", help="Include unchanged ATOMIC Memories"),
    ] = False,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Replace the saved analysis with a new semantic completion",
        ),
    ] = False,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Browse saved Atomize analyses in the Impact launcher",
        ),
    ] = False,
    session_uid: Annotated[
        Optional[str],
        typer.Option(
            "--session",
            help="Saved Atomize analysis uid or unambiguous prefix",
        ),
    ] = None,
) -> None:
    """Preview one Context's exhaustive Atomize classification and splits."""

    try:
        parsed_operand = (
            parse_auto_typed_context_memory_operand(context_operand)
            if context_operand is not None
            else None
        )
        if (
            isinstance(parsed_operand, str)
            and context_name is None
            and is_memory_uid_prefix(context_operand)
        ):
            early_store = ProfileStore(create=False)
            early_snapshot = ContextOperandSnapshot.capture(early_store)
            try:
                early_target = resolve_local_context_memory_target(
                    early_store,
                    context_operand,
                    current=early_snapshot.current_name,
                )
            except FileNotFoundError:
                early_target = None
            except DirectMemoryAmbiguityError:
                # Keep this in Memory mode so duplicate options and saved-
                # session conflicts are rejected before the runtime replays
                # the complete ambiguity diagnostic.
                parsed_operand = DirectMemoryLocator(context_operand)
                early_target = None
            if isinstance(early_target, tuple):
                parsed_operand = DirectMemoryLocator(
                    early_target[1].uid,
                    early_target[0].name,
                )
        if isinstance(parsed_operand, DirectMemoryLocator):
            if context_name is not None:
                raise ValueError(
                    "Auto-typed Memory cannot be combined with --context; use "
                    "CONTEXT:UID or --context CONTEXT --memory UID."
                )
            if memory_selector is not None:
                raise ValueError(
                    "Memory was supplied both positionally and with --memory."
                )
            context_name = parsed_operand.context_locator
            memory_selector = parsed_operand.memory_selector
        else:
            context_name = choose_context_operand(
                parsed_operand if isinstance(parsed_operand, str) else None,
                option=context_name,
            )
    except ValueError as error:
        _usage_error(str(error))

    _dispatch_impact(
        operation=ImpactOperation.atomize,
        session_uid=session_uid,
        sessions=sessions,
        context_name=context_name,
        memory_selector=memory_selector,
        auto_context_memory_operand=context_operand,
        show_all=show_all,
        refresh=refresh,
    )


def _saved_impact_cmd(operation: ImpactOperation, session_uid: str | None) -> None:
    _dispatch_impact(operation=operation, session_uid=session_uid)


def sever_impact_cmd(
    session_uid: Annotated[
        Optional[str],
        typer.Option("--session", help="Saved Sever artifact uid or unique prefix"),
    ] = None,
) -> None:
    """Inspect one exact saved Sever result."""

    _saved_impact_cmd(ImpactOperation.sever, session_uid)


# Registry installation is deliberately last: every public named route must
# have exactly one operation adapter, while the callback remains the separate
# saved-artifact launcher.
install_impact_routes(
    app,
    {
        "atomize": atomize_impact_cmd,
        "distill": distill_impact_cmd,
        "elaborate": elaborate_impact_cmd,
        "makemore": makemore_impact_cmd,
        "merge": merge_impact_cmd,
        "sever": sever_impact_cmd,
    },
)
