"""Console command composition for immutable Memory or Context References."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.application.capabilities.operand_resolution import (
    ContextOperandNotFoundError,
    ResolvedExistingContextOperand,
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
    try_resolve_context_access_or_local_memory,
)
from memcommit.application.capabilities.durable_uid_resolution import (
    is_unresolved_uid_selector,
)
from memcommit.application.capabilities.local_target_lookup import (
    DirectMemoryNotFoundError,
)
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectMemoryLocator,
    DirectMemoryTarget,
)
from memcommit.adapters.console.coordination.endpoint_operand import (
    choose_endpoint_operand,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    is_interactive_terminal,
)
from memcommit.adapters.console.commands.reference.workbench import (
    choose_reference_setup,
)
from memcommit.application.operations.reference.application import (
    ContextReferenceRequest,
    ContextReferenceResult,
    FrozenContextReferencePlan,
    FrozenReferencePlan,
    ReferenceRequest,
    ReferenceResult,
    run_context_reference,
    run_reference,
)
from memcommit.application.operations.reference.runtime import MemoryStoreReferencePort
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


def render_reference_plain(
    result: ReferenceResult | ContextReferenceResult,
) -> None:
    if isinstance(result, ContextReferenceResult):
        scope = "recursive" if result.include_descendants else "direct"
        typer.secho(
            f"Referenced {scope} Context snapshot "
            f"'{display_escape_text(result.source_name)}' "
            f"({result.context_count} Context"
            f"{'s' if result.context_count != 1 else ''}) as "
            f"[{result.reference_uid[:8]}] in "
            f"'{display_escape_text(result.into_name)}'.",
            fg=typer.colors.GREEN,
        )
        return
    typer.secho(
        f"Referenced snapshot [{result.memory_uid[:8]}] from "
        f"'{display_escape_text(result.source_name)}' as "
        f"[{result.reference_uid[:8]}] in "
        f"'{display_escape_text(result.into_name)}'.",
        fg=typer.colors.GREEN,
    )


def cmd(
    item: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Source Context, unique local Memory UID/prefix, or CONTEXT:UID; "
                "omit all operands in a terminal for interactive setup"
            ),
        ),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            metavar="SOURCE_CONTEXT",
            help=(
                "Source Context when ITEM is omitted; otherwise the owner "
                "Context for an explicit Memory selector"
            ),
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            metavar="TARGET_CONTEXT",
            help="Local Context to retain the snapshot (defaults to current)",
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            metavar="TARGET_CONTEXT",
            help="Compatibility alias for --into",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Snapshot only the selected Context's direct contents",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Snapshot descendants and authorized embedded Contexts",
        ),
    ] = False,
) -> None:
    try:
        target_option = choose_endpoint_operand(
            None,
            role="Target",
            options=(("--into", into), ("--to", to)),
        )
    except ValueError as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    try:
        scope = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
    except (TypeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore()
    port = MemoryStoreReferencePort.capture(
        store,
        allow_granted_sources=True,
    )
    frozen_plan: FrozenReferencePlan | FrozenContextReferencePlan | None = None
    source_from_option = item is None and source_name is not None
    source_item = source_name if source_from_option else item
    memory_owner = None if source_from_option else source_name
    if source_item is None:
        if target_option is not None or direct or recursive:
            typer.secho(
                "Error: run 'mem reference' with no operands for interactive "
                "setup, or pass a Context or Memory item.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        if not is_interactive_terminal():
            typer.secho(
                "Error: provide a Source Context, MEMORY, or CONTEXT:MEMORY "
                "outside a terminal; run bare 'mem reference' in a terminal "
                "for interactive setup.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            frozen_plan = choose_reference_setup(port)
        except (
            FileNotFoundError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if frozen_plan is None:
            typer.echo("Reference cancelled — no Context was changed.")
            return
        request = frozen_plan.request
    else:
        explicit_memory_request: ReferenceRequest | None = None
        try:
            context_candidates = freeze_profile_context_access_candidates(
                store,
                current_name=port.current_context_name,
            )
            if target_option is not None:
                try:
                    target_option = resolve_existing_context_operand(
                        freeze_local_context_operand_candidates(store),
                        target_option,
                        current=port.current_context_name,
                    ).name
                except ContextOperandNotFoundError as error:
                    raise FileNotFoundError(
                        f"Target Context {target_option!r} does not exist locally."
                    ) from error
            if source_from_option and (
                target_option is not None or port.current_context_name is not None
            ):
                source_item = resolve_existing_context_access(
                    store,
                    source_item,
                    current_name=port.current_context_name,
                    required_permission="READ",
                    candidates=context_candidates,
                ).name
            parsed_source = (
                parse_auto_typed_context_memory_operand(
                    source_item,
                    explicit_memory_context=memory_owner,
                )
                if not source_from_option
                else None
            )
            auto_target = None
            explicitly_qualified_memory = (
                isinstance(parsed_source, DirectMemoryLocator)
                and parsed_source.context_locator is not None
            )
            if parsed_source is not None and not explicitly_qualified_memory:
                resolved = try_resolve_context_access_or_local_memory(
                    store,
                    source_item,
                    current_name=port.current_context_name,
                    candidates=context_candidates,
                )
                if isinstance(resolved, ResolvedExistingContextOperand):
                    auto_target = ContextTarget(resolved.name)
                elif isinstance(resolved, DirectMemoryTarget):
                    auto_target = resolved
                elif is_unresolved_uid_selector(source_item):
                    raise DirectMemoryNotFoundError(
                        f"No directly owned Memory or readable Context has a UID "
                        f"starting with {source_item!r}."
                    )
            memory_mode = explicitly_qualified_memory or isinstance(
                auto_target, DirectMemoryTarget
            )
            if memory_mode:
                if direct or recursive:
                    typer.secho(
                        "Error: --direct/-d and --recursive/-r apply only to a "
                        "Context Reference; Memory Reference is always one exact "
                        "Memory.",
                        fg=typer.colors.RED,
                        err=True,
                    )
                    raise typer.Exit(2)
                if (
                    explicitly_qualified_memory
                ):
                    # An explicit owner is the safe Grant boundary. Let the
                    # Reference runtime resolve that exact public Context and
                    # authorize retention. Bare UID lookup remains confined to
                    # the complete ordinary-local catalog below.
                    memory_owner_access = resolve_existing_context_access(
                        store,
                        parsed_source.context_locator,
                        current_name=port.current_context_name,
                        required_permission="READ",
                        candidates=context_candidates,
                    )
                    explicit_memory_request = ReferenceRequest(
                        memory_selector=parsed_source.memory_selector,
                        source_locator=memory_owner_access.name,
                        into_locator=target_option,
                    )
                    memory_target = None
                else:
                    assert isinstance(auto_target, DirectMemoryTarget)
                    memory_target = auto_target
            else:
                memory_target = None
        except (
            FileNotFoundError,
            OSError,
            ProfileError,
            TypeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Error: {safe_terminal_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

        if explicit_memory_request is not None:
            request = explicit_memory_request
        elif memory_target is not None:
            request = ReferenceRequest(
                memory_selector=memory_target.memory_uid,
                source_locator=memory_target.context_name,
                into_locator=target_option,
            )
        else:
            recursive_scope = scope is ContextScopePreset.RECURSIVE
            request = ContextReferenceRequest(
                source_locator=(
                    auto_target.context_name if auto_target is not None else source_item
                ),
                into_locator=target_option,
                include_descendants=recursive_scope,
                follow_embeds=recursive_scope,
            )
    try:
        result = (
            run_context_reference(
                request,
                port=port,
                frozen_plan=(
                    frozen_plan
                    if isinstance(frozen_plan, FrozenContextReferencePlan)
                    else None
                ),
            )
            if isinstance(request, ContextReferenceRequest)
            else run_reference(
                request,
                port=port,
                frozen_plan=(
                    frozen_plan
                    if isinstance(frozen_plan, FrozenReferencePlan)
                    else None
                ),
            )
        )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    render_reference_plain(result)


__all__ = ["cmd", "render_reference_plain"]
