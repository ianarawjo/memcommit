from typing import Annotated

import typer

from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.commands.granted_context import (
    GrantedReadStore,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.commands.log import render_checkpoint_rows
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore
from memcommit.source_projection.model import SourceState
from memcommit.source_projection.presentation import source_display_text


def _profile_name(store: MemoryStore) -> str:
    """Name the active Profile only when it owns this exact store boundary."""

    registry = load_profile_registry()
    if profile_store_dir(registry.active).resolve() == store.store_dir.resolve():
        return registry.active.name
    return "standalone"


def _lineage(name: str) -> str:
    return " > ".join(name.split("/"))


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
) -> None:
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
        ctx = (
            GrantedReadStore(access).load(access.display_name)
            if access.is_granted
            else store.load(access.context_name)
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
    items = list(ctx.iter_items())
    memories = [v for v in items if isinstance(v, Memory)]
    references = [v for v in items if isinstance(v, MemoryRef)]
    query_contexts = [v for v in items if isinstance(v, QueryContextRef)]
    embedded = [v for v in items if isinstance(v, Context)]
    # READ grants expose the current projection, not authority history.
    checkpoints = [] if access.is_granted else store.list_checkpoints(name)

    profile_name = _profile_name(store) if branch else None
    access_label = (
        source_display_text(
            context_access_display_facts(
                access,
                states=(SourceState.READ_ONLY,),
            ),
            include_permissions=True,
        )
        + f" · {access.view.grant.uid[:8]} r{access.view.grant.revision}"
        if access.is_granted and access.view is not None
        else "OWNED"
    )
    counts = (
        f"Memories {len(memories)} · Memory Refs {len(references)} · "
        f"Query Views {len(query_contexts)} · Embedded Contexts {len(embedded)} · "
        f"Checkpoints {len(checkpoints)}"
    )
    if short:
        prefix = (
            f"## {profile_name} :: {_lineage(name)}"
            if branch
            else name
        )
        typer.echo(f"{prefix} [{access_label}] · {counts}")
        return

    if branch:
        typer.secho(f"Profile: {profile_name}", bold=True)
        typer.echo(f"Context lineage: {_lineage(name)}")

    typer.secho(f"On context: {name}", bold=True)
    if access.is_granted:
        typer.secho(
            "  Access: "
            + source_display_text(
                context_access_display_facts(
                    access,
                    states=(SourceState.READ_ONLY,),
                ),
                include_permissions=True,
            ),
            dim=True,
        )
    typer.echo(
        f"  Memories {len(memories)}"
        f"  |  Memory Refs {len(references)}"
        f"  |  Query Views {len(query_contexts)}"
        f"  |  Embedded Contexts {len(embedded)}"
        f"  |  Checkpoints {len(checkpoints)}"
    )

    if embedded:
        typer.secho("\nVIA EMBED Contexts:", bold=True)
        for ec in embedded:
            typer.echo(f"  [{ec.uid[:8]}] {ec.name}")

    if query_contexts:
        typer.secho("\nQUERY VIEWS:", bold=True)
        for query_context in query_contexts:
            typer.echo(
                f"  [{query_context.uid[:8]}] {query_context.name}"
            )

    if references:
        typer.secho("\nMEMORY REFS:", bold=True)
        for ref in references:
            state = "READ ONLY" if ref.is_resolved else "DANGLING"
            typer.echo(
                f"  [{ref.uid[:8]}] "
                f"{ref.target_context_name}#{ref.target_memory_uid[:8]} · {state}"
            )

    if memories:
        typer.secho("\nRecent memories:", bold=True)
        for mem in memories[-5:]:
            typer.echo(f"  [{mem.uid[:8]}] ", nl=False)
            lines = mem.content.splitlines()
            preview = "\n         ".join(lines[:5])
            suffix = "\n         …" if len(lines) > 5 else ""
            typer.secho(f"{preview}{suffix}", dim=True)
    else:
        typer.echo("\n  (no memories yet)")

    if checkpoints:
        typer.secho("\nRecent checkpoints:", bold=True)
        render_checkpoint_rows(checkpoints, limit=5)
    else:
        typer.echo("\n  (no checkpoints yet)")
