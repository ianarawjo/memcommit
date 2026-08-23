import uuid
from typing import Annotated, Optional

import typer

from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import (
    ContextAccess,
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.readable_catalog import (
    freeze_readable_context_catalog,
)
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context import AutoCheckpoint
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore, context_record_digest


def _clear_recursive(
    active_store: MemoryStore,
    access: ContextAccess,
) -> tuple[int, int, int]:
    """Clear one frozen local lexical subtree as one Undoable command unit."""

    if access.is_granted:
        raise ProfileError(
            "Recursive clear cannot cross a granted Context boundary; "
            "clear granted Contexts exactly."
        )

    readable = freeze_readable_context_catalog(
        active_store,
        access,
        include_query_routes=False,
    )
    granted_descendants = readable.granted_names_below(access.display_name)
    if granted_descendants:
        raise ProfileError(
            "Recursive clear cannot cross granted Context boundaries: "
            + ", ".join(repr(name) for name in granted_descendants)
            + ". Clear those Contexts exactly."
        )

    store = access.store
    catalog_names = tuple(store.list_context_names())
    context_names = expand_lexical_context_names(
        ContextScope.create(
            (access.context_name,),
            include_descendants=True,
        ),
        catalog_names,
    )
    frames = []
    for name in context_names:
        context = store.load_direct(name)
        frames.append(
            (
                context,
                context_record_digest(context),
                len(context.memories),
            )
        )

    changed = tuple(frame for frame in frames if frame[2] > 0)
    if not changed:
        return 0, len(frames), 0

    operation_uid = str(uuid.uuid4())
    membership = [
        {"uid": context.uid, "name": context.name}
        for context, _digest, _count in changed
    ]
    total_count = sum(count for _context, _digest, count in changed)
    changed_count = len(changed)
    description = (
        f"Cleared {total_count} item(s) from {changed_count} Context(s) "
        f"under '{access.display_name}'"
    )
    tree_receipt = {
        "version": 1,
        "operation_uid": operation_uid,
        "root": access.display_name,
        "include_descendants": True,
    }

    entries = []
    unchanged_bindings = []
    for context, digest, count in frames:
        if count == 0:
            # Empty members still belong to the frozen complete subtree. Keep
            # them locked and digest-checked so a concurrent add cannot escape
            # this command merely because that Context needs no checkpoint.
            unchanged_bindings.append((context.name, context.uid, digest))
            continue
        context.clear()
        entries.append(
            (
                context,
                AutoCheckpoint(
                    command="clear",
                    args={
                        "count": count,
                        "context": context.name,
                        "recursive": True,
                        "clear_tree": tree_receipt,
                        "command_contexts": membership,
                    },
                    description=description,
                ),
                digest,
            )
        )

    store.save_context_command_batch(
        entries,
        source_bindings=unchanged_bindings,
        expected_context_catalog=catalog_names,
    )
    return total_count, len(frames), changed_count


def cmd(
    context_name: Annotated[
        Optional[str], typer.Argument(help="Context to clear (defaults to current)")
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "-R",
            "--recursive",
            help=(
                "Clear direct items from the selected local Context and every "
                "lexical descendant as one Undoable command."
            ),
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "-f",
            "--force",
            hidden=True,
        ),
    ] = False,
) -> None:
    active_store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(active_store)
    try:
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=snapshot.current_name,
            required_permission="DELETE",
        )
        store = access.store
        context_name = access.display_name
        ctx = None if recursive else store.load_direct(access.context_name)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    display_name = display_escape_text(context_name)
    # ``--force`` remains accepted for scripts written against the former
    # prompt, but clear itself is checkpointed and immediately Undoable. The
    # command invocation is therefore the complete approval boundary.
    del force

    if recursive:
        try:
            total_count, scope_count, changed_count = _clear_recursive(
                active_store,
                access,
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
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if total_count == 0:
            typer.secho(
                f"Context subtree '{display_name}' is already empty.",
                fg=typer.colors.YELLOW,
            )
            return
        scope = (
            f"{changed_count} Context(s)"
            if changed_count == scope_count
            else f"{changed_count} of {scope_count} Context(s)"
        )
        typer.secho(
            f"Cleared {total_count} item(s) from {scope} under "
            f"'{display_name}'. Undo can restore this command as one unit.",
            fg=typer.colors.GREEN,
        )
        return

    assert ctx is not None
    count = len(ctx.memories)

    if count == 0:
        typer.secho(
            f"Context '{display_name}' is already empty.",
            fg=typer.colors.YELLOW,
        )
        return

    ctx.clear()
    try:
        with authorized_context_mutation(
            access,
            required_permissions=("DELETE",),
        ):
            store.save(
                ctx,
                AutoCheckpoint(
                    command="clear",
                    args={
                        "count": count,
                        "context": context_name,
                        **grant_checkpoint_args(access),
                    },
                    description=f"Cleared all {count} item(s) from '{context_name}'",
                ),
            )
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.secho(
        f"Cleared {count} item(s) from '{display_name}'.",
        fg=typer.colors.GREEN,
    )
