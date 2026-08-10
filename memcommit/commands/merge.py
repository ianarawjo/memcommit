from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.granted_context import (
    GrantedReadStore,
    authorized_context_operation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.derived_policy import authorize_derived_transfer
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore, context_record_digest
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import source_object_label


def _memory_only_source(source: Context) -> Context:
    """Copy portable Memory values without carrying cross-Profile pointers."""

    result = Context(uid=source.uid, name=source.name)
    for item in source.iter_items():
        if isinstance(item, Memory):
            result.add(Memory(uid=item.uid, content=item.content))
    return result


def cmd(
    other: Annotated[
        str, typer.Argument(help="Name of the context to merge into the current one")
    ]
) -> None:
    active_store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(active_store)
    current = snapshot.current_name
    if not current:
        typer.secho(
            "No current context. Run 'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    try:
        source_access = resolve_context_access(
            active_store,
            other,
            current_name=current,
            required_permission="READ",
        )
        target_access = resolve_context_access(
            active_store,
            None,
            current_name=current,
            required_permission="CREATE",
        )
        source_store = source_access.store
        target_store = target_access.store
        source = (
            GrantedReadStore(source_access).load(source_access.display_name)
            if source_access.is_granted
            else source_store.load_for_update(source_access.context_name)
        )
        target = target_store.load_for_update(target_access.context_name)
        authorize_derived_transfer(source_access, target_access)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if target.uid == source.uid and source_store.store_dir == target_store.store_dir:
        typer.secho(
            "Error: cannot merge a context into itself.", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(1)

    cross_profile = source_store.store_dir != target_store.store_dir
    merge_source = _memory_only_source(source) if cross_profile else source
    source_projection_digest = context_record_digest(source)

    try:
        added = ops.merge(merge_source, target)
    except ValueError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    mem_count = sum(1 for i in added if isinstance(i, Memory))
    ref_count = sum(1 for i in added if isinstance(i, MemoryRef))
    query_count = sum(1 for i in added if isinstance(i, QueryContextRef))
    ctx_count = sum(1 for i in added if isinstance(i, Context))
    parts = []
    if mem_count:
        parts.append(f"{mem_count} memor{'y' if mem_count == 1 else 'ies'}")
    if ref_count:
        label = source_object_label(SourceForm.MEMORY_REF)
        parts.append(f"{ref_count} {label}{'s' if ref_count != 1 else ''}")
    if query_count:
        label = source_object_label(SourceForm.QUERY_VIEW)
        parts.append(f"{query_count} {label}{'s' if query_count != 1 else ''}")
    if ctx_count:
        label = source_object_label(SourceForm.CONTEXT)
        parts.append(f"{ctx_count} embedded {label}{'s' if ctx_count != 1 else ''}")
    summary = ", ".join(parts) if parts else "nothing new"

    try:
        checkpoint = AutoCheckpoint(
            command="merge",
            args={
                "source": source_access.display_name,
                "cross_profile_memory_only": cross_profile,
                **grant_checkpoint_args(target_access),
            },
            description=(
                f"Merged '{source_access.display_name}' into "
                f"'{target_access.display_name}': added {summary}"
            ),
        )
        with authorized_context_operation(
            (
                (source_access, ("READ",)),
                (target_access, ("CREATE",)),
            )
        ):
            try:
                current_source = (
                    GrantedReadStore(source_access).load(source_access.display_name)
                    if source_access.is_granted
                    else source_store.load_for_update(source_access.context_name)
                )
            except FileNotFoundError as error:
                raise RuntimeError(
                    "The source Context no longer exists: "
                    f"'{source_access.context_name}'."
                ) from error
            if context_record_digest(current_source) != source_projection_digest:
                raise RuntimeError(
                    "The merge source changed before the target could be saved."
                )
            if cross_profile:
                target_store.save(
                    target,
                    checkpoint,
                    expected_context_digest=target._store_digest or "",
                )
            else:
                target_store.save_context_with_sources(
                    target,
                    checkpoint,
                    expected_context_digest=target._store_digest or "",
                    source_bindings=(
                        (
                            source_access.context_name,
                            source.uid,
                            source_projection_digest,
                        ),
                    ),
                )
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.secho(
        f"Merged '{display_escape_text(source_access.display_name)}' into "
        f"'{display_escape_text(target_access.display_name)}': added {summary}.",
        fg=typer.colors.GREEN,
    )
