from dataclasses import dataclass
from typing import Annotated, Any

import typer

from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.commands.log import render_checkpoint_rows
from memcommit.commands.readable_context_catalog import (
    ReadableContextCatalog,
    freeze_readable_context_catalog,
)
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    ContextTraversal,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore
from memcommit.source_projection.model import SourceState
from memcommit.source_projection.presentation import source_display_text


@dataclass(frozen=True)
class _ContextStatus:
    context: Context
    access: ContextAccess
    memories: tuple[Memory, ...]
    references: tuple[MemoryRef, ...]
    query_contexts: tuple[QueryContextRef, ...]
    embedded: tuple[Context, ...]
    checkpoints: tuple[dict[str, Any], ...]


def _snapshot_status(
    context: Context,
    *,
    access: ContextAccess,
    store: MemoryStore,
) -> _ContextStatus:
    items = tuple(context.iter_items())
    return _ContextStatus(
        context=context,
        access=access,
        memories=tuple(item for item in items if isinstance(item, Memory)),
        references=tuple(item for item in items if isinstance(item, MemoryRef)),
        query_contexts=tuple(
            item for item in items if isinstance(item, QueryContextRef)
        ),
        embedded=tuple(item for item in items if isinstance(item, Context)),
        # READ grants expose the current projection, not authority history.
        checkpoints=(
            ()
            if access.is_granted
            else tuple(store.list_checkpoints(access.context_name))
        ),
    )


def _load_status_scope(
    catalog: ReadableContextCatalog,
    root_name: str,
    *,
    traversal: ContextTraversal,
    store: MemoryStore,
) -> tuple[_ContextStatus, ...]:
    """Load each readable Context in scope once by durable identity."""

    scope = ContextScope.create(
        (root_name,),
        include_descendants=traversal.include_descendants,
    )
    names = expand_lexical_context_names(
        scope,
        sorted(catalog.list_context_names(), key=str.casefold),
    )
    contexts: list[Context] = []
    seen_uids: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in seen_uids:
            return
        seen_uids.add(context.uid)
        contexts.append(context)
        if not traversal.follow_embeds:
            return
        for item in context.iter_items():
            if isinstance(item, Context):
                visit(item)

    for name in names:
        visit(catalog.load(name))

    return tuple(
        _snapshot_status(
            context,
            access=catalog.access_for(context.name),
            store=store,
        )
        for context in contexts
    )


def _profile_name(store: MemoryStore) -> str:
    """Name the active Profile only when it owns this exact store boundary."""

    registry = load_profile_registry()
    if profile_store_dir(registry.active).resolve() == store.store_dir.resolve():
        return registry.active.name
    return "standalone"


def _lineage(name: str) -> str:
    return " > ".join(name.split("/"))


def _access_label(access: ContextAccess) -> str:
    if access.is_granted and access.view is not None:
        return (
            source_display_text(
                context_access_display_facts(
                    access,
                    states=(SourceState.READ_ONLY,),
                ),
                include_permissions=True,
            )
            + f" · {access.view.grant.uid[:8]} r{access.view.grant.revision}"
        )
    return "OWNED"


def _counts(status: _ContextStatus, *, separator: str) -> str:
    return separator.join(
        (
            f"Memories {len(status.memories)}",
            f"Memory Refs {len(status.references)}",
            f"Query Views {len(status.query_contexts)}",
            f"Embedded Contexts {len(status.embedded)}",
            f"Checkpoints {len(status.checkpoints)}",
        )
    )


def _recursive_totals(statuses: tuple[_ContextStatus, ...]) -> str:
    return "  |  ".join(
        (
            f"Contexts {len(statuses)}",
            f"Memories {sum(len(status.memories) for status in statuses)}",
            f"Memory Refs {sum(len(status.references) for status in statuses)}",
            f"Query Views {sum(len(status.query_contexts) for status in statuses)}",
            "Embedded Contexts "
            + str(sum(len(status.embedded) for status in statuses)),
            f"Checkpoints {sum(len(status.checkpoints) for status in statuses)}",
        )
    )


def _render_recursive_overview(statuses: tuple[_ContextStatus, ...]) -> None:
    typer.secho("\nRecursive scope:", bold=True)
    typer.echo("  " + _recursive_totals(statuses))
    typer.secho("\nContext status:", bold=True)
    for index, status in enumerate(statuses):
        current = " · CURRENT" if index == 0 else ""
        typer.echo(
            f"  {status.context.name} [{_access_label(status.access)}]{current}"
        )
        typer.echo("    " + _counts(status, separator="  |  "))


def _render_short_status(
    status: _ContextStatus,
    *,
    branch: bool,
    profile_name: str | None,
) -> None:
    prefix = (
        f"## {profile_name} :: {_lineage(status.context.name)}"
        if branch
        else status.context.name
    )
    typer.echo(
        f"{prefix} [{_access_label(status.access)}] · "
        + _counts(status, separator=" · ")
    )


def cmd(
    short: Annotated[
        bool,
        typer.Option(
            "-s",
            "--short",
            help="Show the current Context and counts on one line",
        ),
    ] = False,
    branch: Annotated[
        bool,
        typer.Option(
            "-b",
            "--branch",
            help="Include the active Profile and Context lineage",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Show only the current Context",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help=(
                "Include readable namespace descendants and embedded Contexts"
            ),
        ),
    ] = False,
) -> None:
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
    except ValueError as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    traversal = resolve_context_traversal(preset=preset)

    store = MemoryStore()
    name = store.current_context_name()
    if not name:
        typer.secho("No current context. Run 'mem init <name>' to get started.", fg=typer.colors.YELLOW)
        return

    try:
        access = resolve_context_access(
            store,
            None,
            current_name=name,
            required_permission="READ",
        )
        if preset is ContextScopePreset.DIRECT:
            context = (
                GrantedReadStore(access).load(access.display_name)
                if access.is_granted
                else store.load(access.context_name)
            )
            statuses = (
                _snapshot_status(context, access=access, store=store),
            )
        else:
            catalog = freeze_readable_context_catalog(store, access)
            statuses = _load_status_scope(
                catalog,
                access.display_name,
                traversal=traversal,
                store=store,
            )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(f"Status error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    current = statuses[0]

    profile_name = _profile_name(store) if branch else None
    if short:
        for status in statuses:
            _render_short_status(
                status,
                branch=branch,
                profile_name=profile_name,
            )
        return

    if branch:
        typer.secho(f"Profile: {profile_name}", bold=True)
        typer.echo(f"Context lineage: {_lineage(name)}")

    typer.secho(f"On context: {name}", bold=True)
    if current.access.is_granted:
        typer.secho(
            "  Access: "
            + source_display_text(
                context_access_display_facts(
                    current.access,
                    states=(SourceState.READ_ONLY,),
                ),
                include_permissions=True,
            ),
            dim=True,
        )
    typer.echo(
        "  " + _counts(current, separator="  |  ")
    )

    if preset is ContextScopePreset.RECURSIVE:
        _render_recursive_overview(statuses)

    if current.embedded:
        typer.secho("\nVIA EMBED Contexts:", bold=True)
        for ec in current.embedded:
            typer.echo(f"  [{ec.uid[:8]}] {ec.name}")

    if current.query_contexts:
        typer.secho("\nQUERY VIEWS:", bold=True)
        for query_context in current.query_contexts:
            typer.echo(
                f"  [{query_context.uid[:8]}] {query_context.name}"
            )

    if current.references:
        typer.secho("\nMEMORY REFS:", bold=True)
        for ref in current.references:
            state = "READ ONLY" if ref.is_resolved else "DANGLING"
            typer.echo(
                f"  [{ref.uid[:8]}] "
                f"{ref.target_context_name}#{ref.target_memory_uid[:8]} · {state}"
            )

    if current.memories:
        typer.secho("\nRecent memories:", bold=True)
        for mem in current.memories[-5:]:
            typer.echo(f"  [{mem.uid[:8]}] ", nl=False)
            lines = mem.content.splitlines()
            preview = "\n         ".join(lines[:5])
            suffix = "\n         …" if len(lines) > 5 else ""
            typer.secho(f"{preview}{suffix}", dim=True)
    else:
        typer.echo("\n  (no memories yet)")

    if current.checkpoints:
        typer.secho("\nRecent checkpoints:", bold=True)
        render_checkpoint_rows(current.checkpoints, limit=5)
    else:
        typer.echo("\n  (no checkpoints yet)")
