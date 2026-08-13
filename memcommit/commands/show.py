import shlex
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.granted_context import (
    GrantedReadStore,
    attached_grants,
    context_access_display_facts,
    project_grants_into_context,
    resolve_context_access,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
    context_access_facts,
)
from memcommit.source_projection.presentation import (
    source_annotation_text,
    source_display_text,
    source_object_label,
)


def render_memory(memory: Memory, context_name: str) -> None:
    """Print one atomic memory in full."""
    label = source_object_label(SourceForm.MEMORY, title=True)
    typer.secho(f"{label}: {display_escape_text(memory.uid)}", bold=True)
    typer.echo(f"Context: {display_escape_text(context_name)}")
    typer.echo()
    typer.echo(safe_terminal_text(memory.content))


def render_memory_ref(memory_ref: MemoryRef, context_name: str) -> None:
    """Print one read-only Memory reference and its currently resolved content."""
    facts = SourceDisplayFacts(
        form=SourceForm.MEMORY_REF,
        states=(
            (SourceState.READ_ONLY,)
            if memory_ref.is_resolved
            else (SourceState.DANGLING,)
        ),
    )
    typer.secho(
        f"{source_object_label(facts, title=True)}: "
        f"{display_escape_text(memory_ref.uid)}",
        bold=True,
    )
    typer.echo(f"Context: {display_escape_text(context_name)}")
    typer.echo(f"State: {source_annotation_text(facts)}")
    typer.echo(
        f"Source: {display_escape_text(memory_ref.target_context_name)} "
        f"[{display_escape_text(memory_ref.target_context_uid[:8])}]"
    )
    typer.echo("Target Memory: " + display_escape_text(memory_ref.target_memory_uid))
    typer.echo()
    if memory_ref.target is None:
        typer.secho(
            "(memory ref target is unavailable)",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.echo(safe_terminal_text(memory_ref.target.content))


def render_query_context_ref(
    query_ref: QueryContextRef,
    context_name: str,
) -> None:
    """Print query-only metadata without opening or revealing its source."""
    label = source_object_label(SourceForm.QUERY_VIEW, title=True)
    typer.secho(f"{label}: {display_escape_text(query_ref.name)}", bold=True)
    typer.echo(f"Route: {display_escape_text(query_ref.uid)}")
    typer.echo(f"Parent Context: {display_escape_text(context_name)}")
    typer.echo("Mode: QUERY ONLY")
    typer.echo("Content: concealed from mem ls and mem show")
    typer.echo()
    command = shlex.join(["mem", "query", query_ref.name, "<question>"])
    typer.echo(f"Ask with: {display_escape_text(command)}")


def render_context(
    ctx: Context,
    *,
    context_facts: SourceDisplayFacts | None = None,
    item_facts: dict[str, SourceDisplayFacts] | None = None,
) -> None:
    """Print the full direct contents of one context (non-recursive)."""
    items = list(ctx.iter_items())
    memories = [v for v in items if isinstance(v, Memory)]
    references = [v for v in items if isinstance(v, MemoryRef)]
    query_contexts = [v for v in items if isinstance(v, QueryContextRef)]
    embedded = [v for v in items if isinstance(v, Context)]

    typer.secho(f"Context: {display_escape_text(ctx.name)}", bold=True)
    if context_facts is not None:
        annotation = source_display_text(context_facts)
        if annotation:
            typer.echo(f"Access: {annotation}")
    typer.echo(
        f"  Memories {len(memories)}"
        f"  |  Memory Refs {len(references)}"
        f"  |  Query Views {len(query_contexts)}"
        f"  |  Embedded Contexts {len(embedded)}"
    )

    if not items:
        typer.echo("\n  (no items)")
        return

    typer.secho("\nItems (in context order):", bold=True)
    for item in items:
        facts = (item_facts or {}).get(item.uid)
        if isinstance(item, Context):
            facts = facts or SourceDisplayFacts(reach=SourceReach.VIA_EMBED)
            annotation = source_annotation_text(facts)
            typer.echo(
                f"  [{source_object_label(SourceForm.CONTEXT)} "
                f"{display_escape_text(item.uid[:8])}] "
                f"{display_escape_text(item.name)}"
                + (f"  {annotation}" if annotation else "")
            )
        elif isinstance(item, QueryContextRef):
            facts = facts or SourceDisplayFacts(form=SourceForm.QUERY_VIEW)
            annotation = source_annotation_text(facts)
            typer.echo(
                f"  [{source_object_label(facts)} "
                f"{display_escape_text(item.uid[:8])}] "
                f"{display_escape_text(item.name)}"
                + (f"  {annotation}" if annotation else "")
            )
        elif isinstance(item, MemoryRef):
            facts = facts or SourceDisplayFacts(
                form=SourceForm.MEMORY_REF,
                states=(
                    (SourceState.READ_ONLY,)
                    if item.is_resolved
                    else (SourceState.DANGLING,)
                ),
            )
            annotation = source_annotation_text(facts)
            typer.echo(
                f"  [{source_object_label(facts)} "
                f"{display_escape_text(item.uid[:8])}] "
                f"{display_escape_text(item.target_context_name)}#"
                f"{display_escape_text(item.target_memory_uid[:8])}"
                + (f"  {annotation}" if annotation else "")
            )
            if item.target is not None:
                typer.secho(
                    f"           {safe_terminal_text(item.target.content)}",
                    dim=True,
                )
        elif isinstance(item, Memory):
            memory = item
            facts = facts or SourceDisplayFacts(form=SourceForm.MEMORY)
            annotation = source_annotation_text(facts)
            typer.echo(
                f"  [{source_object_label(facts)} "
                f"{display_escape_text(memory.uid[:8])}] ",
                nl=False,
            )
            typer.secho(safe_terminal_text(memory.content), dim=True)
            if annotation:
                typer.echo(f"    {annotation}")


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help="Item UID/prefix or exact embedded-context name; omit to show the whole context"
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Parent context to inspect (defaults to current)",
        ),
    ] = None,
) -> None:
    active_store = MemoryStore()
    try:
        current_name = active_store.current_context_name()
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=current_name,
            required_permission="READ",
        )
        item_facts: dict[str, SourceDisplayFacts] = {}
        if access.is_granted:
            ctx = GrantedReadStore(access).load(access.display_name)
        else:
            ctx = access.store.load(access.context_name)
            _, grants = attached_grants(access.context_name)
            if grants:
                ctx = project_grants_into_context(ctx, grants)
                for grant in grants:
                    if "READ" in grant.permissions:
                        item_facts[grant.resource_uid] = context_access_facts(
                            granted=True,
                            permission="READ",
                            permissions=grant.permissions,
                        )
                    elif "QUERY" in grant.permissions:
                        item_facts[grant.uid] = context_access_facts(
                            granted=True,
                            permission="QUERY",
                            permissions=grant.permissions,
                            form=SourceForm.QUERY_VIEW,
                        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if selector is None:
        render_context(
            ctx,
            context_facts=(
                context_access_display_facts(
                    access,
                    states=(SourceState.READ_ONLY,),
                )
                if access.is_granted
                else None
            ),
            item_facts=item_facts,
        )
        return

    try:
        item = ops.resolve(ctx, selector)
    except (KeyError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if isinstance(item, Memory):
        render_memory(item, ctx.name)
    elif isinstance(item, MemoryRef):
        render_memory_ref(item, ctx.name)
    elif isinstance(item, QueryContextRef):
        render_query_context_ref(item, ctx.name)
    elif isinstance(item, Context):
        render_context(item, context_facts=item_facts.get(item.uid))
