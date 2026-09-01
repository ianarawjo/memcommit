"""Preview new effects or inspect saved operation-owned Impact artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional

import typer

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
from memcommit.adapters.console.commands.forget.impact import (
    forget_cmd as forget_impact_cmd,
)
from memcommit.adapters.console.commands.resolve.impact import (
    resolve_cmd as resolve_impact_cmd,
)
from memcommit.adapters.console.commands.impact.registry import (
    install_impact_routes,
)
from memcommit.adapters.console.commands.meld.impact import (
    open_saved_meld_impact as _saved_meld_impact,
)
from memcommit.adapters.console.commands.sever.impact import (
    open_saved_sever_impact as _saved_sever_impact,
)
from memcommit.adapters.console.commands.update.impact import (
    open_saved_update_impact as _saved_update_impact,
    run_directional_update_impact as _directional_impact,
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
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectMemoryLocator,
    DirectMemoryTarget,
    ExistingContextOperand,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.persistence.store import MemoryStore
from memcommit.adapters.console.commands.update.endpoint_operands import (
    choose_update_endpoint_operands,
)


app = typer.Typer(
    cls=CanonicalCommandGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    help=(
        "Preview operation-owned effects without applying them, or omit the "
        "operation for a directional Update preview."
    ),
)


class ImpactOperation(str, Enum):
    """Internal discriminator used by the legacy dispatcher behind the registry."""

    atomize = "atomize"
    meld = "meld"
    sever = "sever"
    update = "update"


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
        store = MemoryStore(create=False)
        runners = {
            ImpactOperation.meld: _saved_meld_impact,
            ImpactOperation.sever: _saved_sever_impact,
            ImpactOperation.update: _saved_update_impact,
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
        store = MemoryStore(create=False)
        receipt = choose_impact_session(
            store,
            kinds=None if operation is None else (operation.value,),
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
        typer.echo("Impact selection cancelled; no analysis was opened.")
        return
    _operation_session_impact(
        operation=ImpactOperation(receipt.kind),
        session_uid=receipt.key,
        show_all=show_all,
    )


def _dispatch_impact(
    operation: Annotated[
        Optional[ImpactOperation],
        typer.Argument(
            help=(
                "Impact operation: atomize, meld, sever, or update; omit for "
                "a directional Update preview"
            ),
        ),
    ] = None,
    session_uid: Annotated[
        Optional[str],
        typer.Option(
            "--session",
            help="Saved Meld, Sever, or Update artifact uid or unique prefix",
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Browse saved Impact analyses in an interactive launcher",
        ),
    ] = False,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=("Source Context A; if --to is omitted, current supplies B"),
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help=("Target Context B; if --from is omitted, current supplies A"),
        ),
    ] = None,
    source_memory: Annotated[
        Optional[str],
        typer.Option(
            "--source-memory",
            metavar="UID_OR_PREFIX",
            help="With directional Update, focus one Source Memory",
        ),
    ] = None,
    target_memory: Annotated[
        Optional[str],
        typer.Option(
            "--target-memory",
            metavar="UID_OR_PREFIX",
            help="With directional Update, focus one Target Memory",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Use only explicit directional Update endpoint roots",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both directional Update endpoints",
        ),
    ] = False,
    source_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--source-descendants/--source-root-only",
            legacy_root_only_option_alias("source"),
            help="Refine directional Update Source reach",
        ),
    ] = None,
    target_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--target-descendants/--target-root-only",
            legacy_root_only_option_alias("target"),
            help="Refine directional Update Target reach",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context for a unary impact operation (defaults to current)",
        ),
    ] = None,
    memory_selector: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            metavar="UID_OR_PREFIX",
            help=(
                "With atomize, analyze one direct Memory while its neighbors "
                "remain non-actionable context"
            ),
        ),
    ] = None,
    show_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Include unchanged ATOMIC Memories in atomize output",
        ),
    ] = False,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help=(
                "Explicitly replace the saved analysis with one new unframed "
                "semantic completion"
            ),
        ),
    ] = False,
    auto_context_memory_operand: str | None = None,
) -> None:
    """Preview a new plan or inspect saved Impact before an optional Apply handoff."""
    scope_flags_supplied = (
        direct
        or recursive
        or source_descendants is not None
        or target_descendants is not None
    )
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        source_descendants, target_descendants = resolve_descendant_scopes(
            preset=preset,
            explicit=(source_descendants, target_descendants),
        )
    except (TypeError, ValueError) as error:
        _usage_error(str(error))
    if operation is ImpactOperation.atomize:
        if scope_flags_supplied:
            _usage_error(
                "Context scope presets apply to directional Update Impact; "
                "atomize remains direct-only."
            )
        if sessions and session_uid is not None:
            _usage_error(
                "use either '--sessions' to browse saved Atomize analyses or "
                "'--session UID' to reopen one exact analysis."
            )
        if sessions or session_uid is not None:
            if (
                source_name is not None
                or target_name is not None
                or context_name is not None
                or memory_selector is not None
                or auto_context_memory_operand is not None
                or source_memory is not None
                or target_memory is not None
                or refresh
            ):
                _usage_error(
                    "saved Atomize Impact selection cannot be combined with "
                    "Context, Memory, directional, or reanalysis options."
                )
            if sessions:
                _browse_impact_sessions(
                    operation=ImpactOperation.atomize,
                    show_all=show_all,
                )
            else:
                _operation_session_impact(
                    operation=ImpactOperation.atomize,
                    session_uid=session_uid,
                    show_all=show_all,
                )
            return
        if source_name is not None or target_name is not None:
            _usage_error(
                "'atomize' cannot be combined with '--from' or '--to'. "
                "Use either 'mem impact atomize' or "
                "a directional 'mem impact --from SOURCE' / "
                "'--to TARGET' form."
            )
        if source_memory is not None or target_memory is not None:
            _usage_error(
                "'--source-memory' and '--target-memory' select directional "
                "Update inputs, not atomize inputs; use '--memory' for atomize."
            )
        try:
            store = MemoryStore(create=False)
            context_snapshot = ContextOperandSnapshot.capture(store)
            if auto_context_memory_operand is not None:
                auto_target = resolve_local_context_memory_target(
                    store,
                    auto_context_memory_operand,
                    current=context_snapshot.current_name,
                )
                canonical_context_name = auto_target.context_name
                if isinstance(auto_target, DirectMemoryTarget):
                    memory_selector = auto_target.memory_uid
                else:
                    assert isinstance(auto_target, ContextTarget)
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

    if operation is not None:
        if (
            source_name is not None
            or target_name is not None
            or context_name is not None
            or memory_selector is not None
            or source_memory is not None
            or target_memory is not None
            or show_all
            or refresh
            or sessions
            or scope_flags_supplied
        ):
            _usage_error(
                f"'mem impact {operation.value}' opens a saved session and "
                "cannot be combined with directional or atomize options."
            )
        _operation_session_impact(
            operation=operation,
            session_uid=session_uid,
        )
        return

    if source_name is None and target_name is None:
        _usage_error(
            "choose an endpoint with '--from SOURCE' or '--to TARGET', "
            "preview atomization with 'mem impact atomize', or inspect a "
            "saved 'meld', 'sever', or 'update' Impact."
        )
    if (
        session_uid is not None
        or sessions
        or context_name is not None
        or memory_selector is not None
        or show_all
        or refresh
    ):
        _usage_error(
            "'--session' and '--sessions' require a saved-session operation; "
            "'--context', '--memory', '--all', and '--refresh' are only "
            "valid with 'mem impact atomize'."
        )
    try:
        store = MemoryStore()
        context_snapshot = ContextOperandSnapshot.capture(store)
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    _directional_impact(
        store=store,
        current_name=context_snapshot.current_name,
        source_name=source_name,
        target_name=target_name,
        source_memory=source_memory,
        target_memory=target_memory,
        source_descendants=source_descendants,
        target_descendants=target_descendants,
    )


@app.callback(invoke_without_command=True)
def cmd(
    ctx: typer.Context,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Source Context A; if --to is omitted, current supplies B",
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Target Context B; if --from is omitted, current supplies A",
        ),
    ] = None,
    source_memory: Annotated[
        Optional[str],
        typer.Option(
            "--source-memory",
            metavar="UID_OR_PREFIX",
            help="Focus one Source Memory",
        ),
    ] = None,
    target_memory: Annotated[
        Optional[str],
        typer.Option(
            "--target-memory",
            metavar="UID_OR_PREFIX",
            help="Focus one Target Memory",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Use only explicit endpoint roots"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both endpoints",
        ),
    ] = False,
    source_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--source-descendants/--source-root-only",
            legacy_root_only_option_alias("source"),
            help="Refine Source reach",
        ),
    ] = None,
    target_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--target-descendants/--target-root-only",
            legacy_root_only_option_alias("target"),
            help="Refine Target reach",
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Browse every saved analysis inspectable through Impact",
        ),
    ] = False,
) -> None:
    """Preview directional Update effects when no named operation is supplied."""

    directional_options = (
        source_name is not None
        or target_name is not None
        or source_memory is not None
        or target_memory is not None
        or direct
        or recursive
        or source_descendants is not None
        or target_descendants is not None
    )
    if ctx.invoked_subcommand is not None:
        if directional_options:
            _usage_error(
                "directional Update options cannot be combined with a named "
                "Impact operation."
            )
        if sessions:
            _usage_error(
                "root '--sessions' cannot be combined with a named Impact "
                "operation; put operation-specific options after its name."
            )
        return
    if sessions:
        if directional_options:
            _usage_error(
                "'--sessions' cannot be combined with directional Update "
                "endpoints or reach options."
            )
        _browse_impact_sessions()
        return
    _dispatch_impact(
        operation=None,
        source_name=source_name,
        target_name=target_name,
        source_memory=source_memory,
        target_memory=target_memory,
        direct=direct,
        recursive=recursive,
        source_descendants=source_descendants,
        target_descendants=target_descendants,
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
            isinstance(parsed_operand, ExistingContextOperand)
            and context_name is None
            and is_memory_uid_prefix(context_operand)
        ):
            early_store = MemoryStore(create=False)
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
            if isinstance(early_target, DirectMemoryTarget):
                parsed_operand = DirectMemoryLocator(
                    early_target.memory_uid,
                    early_target.context_name,
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
                (
                    parsed_operand.locator
                    if isinstance(parsed_operand, ExistingContextOperand)
                    else None
                ),
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


def meld_impact_cmd(
    session_uid: Annotated[
        Optional[str],
        typer.Option("--session", help="Saved Meld artifact uid or unique prefix"),
    ] = None,
) -> None:
    """Inspect one exact saved Meld assessment."""

    _saved_impact_cmd(ImpactOperation.meld, session_uid)


def sever_impact_cmd(
    session_uid: Annotated[
        Optional[str],
        typer.Option("--session", help="Saved Sever artifact uid or unique prefix"),
    ] = None,
) -> None:
    """Inspect one exact saved Sever result."""

    _saved_impact_cmd(ImpactOperation.sever, session_uid)


def update_impact_cmd(
    contexts: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="SOURCE TARGET",
            help="Explicit Source and Target Contexts for a new preview",
        ),
    ] = None,
    session_uid: Annotated[
        Optional[str],
        typer.Option("--session", help="Saved Update artifact uid or unique prefix"),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Source Context; current supplies Target when --to is omitted",
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Target Context; current supplies Source when --from is omitted",
        ),
    ] = None,
    source_memory: Annotated[
        Optional[str],
        typer.Option(
            "--source-memory",
            metavar="UID_OR_PREFIX",
            help="Focus one Source Memory",
        ),
    ] = None,
    target_memory: Annotated[
        Optional[str],
        typer.Option(
            "--target-memory",
            metavar="UID_OR_PREFIX",
            help="Focus one Target Memory",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Use only explicit endpoint roots"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both endpoints",
        ),
    ] = False,
    source_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--source-descendants/--source-root-only",
            legacy_root_only_option_alias("source"),
            help="Refine Source reach",
        ),
    ] = None,
    target_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--target-descendants/--target-root-only",
            legacy_root_only_option_alias("target"),
            help="Refine Target reach",
        ),
    ] = None,
) -> None:
    """Preview a directional Update or inspect one saved Update plan."""

    try:
        source_name, target_name = choose_update_endpoint_operands(
            contexts,
            source_option=source_name,
            target_option=target_name,
        )
    except ValueError as error:
        _usage_error(str(error))

    planning_requested = (
        source_name is not None
        or target_name is not None
        or source_memory is not None
        or target_memory is not None
        or direct
        or recursive
        or source_descendants is not None
        or target_descendants is not None
    )
    if session_uid is not None and planning_requested:
        _usage_error(
            "--session cannot be combined with a new directional Update preview."
        )
    if not planning_requested:
        _saved_impact_cmd(ImpactOperation.update, session_uid)
        return

    _dispatch_impact(
        operation=None,
        source_name=source_name,
        target_name=target_name,
        source_memory=source_memory,
        target_memory=target_memory,
        direct=direct,
        recursive=recursive,
        source_descendants=source_descendants,
        target_descendants=target_descendants,
    )


# Registry installation is deliberately last: every public named route must
# have exactly one operation adapter, while the callback remains the separate
# directional Update form.
install_impact_routes(
    app,
    {
        "atomize": atomize_impact_cmd,
        "forget": forget_impact_cmd,
        "distill": distill_impact_cmd,
        "elaborate": elaborate_impact_cmd,
        "makemore": makemore_impact_cmd,
        "resolve": resolve_impact_cmd,
        "meld": meld_impact_cmd,
        "sever": sever_impact_cmd,
        "update": update_impact_cmd,
    },
)
