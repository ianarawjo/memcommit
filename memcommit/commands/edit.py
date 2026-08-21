from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.command_attempts import annotate_command_outcome
from memcommit.commands.batch_input import parse_edit_lines, read_text_input
from memcommit.authority.access import (
    ContextAccess,
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def _render_content(prefix: str, content: str, color: str) -> None:
    lines = content.splitlines() or [""]
    for line in lines:
        typer.secho(f"  {prefix} {line}", fg=color)


def _split_single_locator(
    selector: str,
    context_name: str | None,
) -> tuple[str | None, str]:
    """Separate an optional Context owner from one direct-Memory selector."""

    if "#" not in selector:
        return context_name, selector
    if context_name is not None:
        raise ValueError(
            "CONTEXT#UID cannot be combined with --context; choose one "
            "Context locator."
        )
    if selector.count("#") != 1:
        raise ValueError("Edit locator must use the form CONTEXT#UID.")
    owner_name, memory_selector = selector.split("#", 1)
    if not owner_name or not memory_selector:
        raise ValueError("Edit locator must use the form CONTEXT#UID.")
    return owner_name, memory_selector


def _resolve_single_target(
    active_store: MemoryStore,
    *,
    current_name: str | None,
    selector: str,
    context_name: str | None,
) -> tuple[ContextAccess, Context, str]:
    """Freeze one directly owned Memory target before Edit mutates it.

    A bare selector prefers the command-start current Context. Only when that
    Context has no matching item do we scan ordinary local Contexts. This
    preserves the familiar local shorthand while making a locator copied from
    a linked row executable without treating the link itself as writable.
    """

    owner_name, memory_selector = _split_single_locator(selector, context_name)
    if owner_name is not None:
        access = resolve_context_access(
            active_store,
            owner_name,
            current_name=current_name,
            required_permission="UPDATE",
        )
        ctx = access.store.load_direct(access.context_name)
        memory = ops.resolve_direct_memory(ctx, memory_selector)
        return access, ctx, memory.uid

    if current_name is not None and active_store.context_exists(current_name):
        access = resolve_context_access(
            active_store,
            current_name,
            current_name=current_name,
            required_permission="UPDATE",
        )
        ctx = access.store.load_direct(access.context_name)
        try:
            memory = ops.resolve_direct_memory(ctx, memory_selector)
        except KeyError:
            pass
        else:
            return access, ctx, memory.uid

    matches = []
    for candidate_name in sorted(active_store.list_context_names()):
        if candidate_name == current_name:
            continue
        candidate = active_store.load_direct(candidate_name)
        for uid, item in candidate.memories.items():
            if isinstance(item, Memory) and uid.startswith(memory_selector):
                matches.append((candidate_name, candidate, uid))

    if not matches:
        raise KeyError(
            "No directly owned Memory with uid starting with "
            f"'{memory_selector}' was found in local Contexts. Use "
            "CONTEXT#UID to name its owner explicitly."
        )
    if len(matches) > 1:
        choices = ", ".join(f"{name}#{uid[:8]}" for name, _, uid in matches)
        raise ValueError(
            f"Ambiguous Memory selector '{memory_selector}' matches "
            f"{len(matches)} local Contexts: {choices}. Use CONTEXT#UID."
        )

    owner_name, ctx, uid = matches[0]
    access = resolve_context_access(
        active_store,
        owner_name,
        current_name=current_name,
        required_permission="UPDATE",
    )
    return access, ctx, uid


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "UID (or unambiguous prefix) of a directly owned Memory, or "
                "CONTEXT#UID; a bare UID searches local Contexts when absent "
                "from the current Context"
            )
        ),
    ] = None,
    content: Annotated[
        Optional[str],
        typer.Argument(help="Replacement content for the Memory"),
    ] = None,
    input_source: Annotated[
        Optional[str],
        typer.Option(
            "--input",
            "-i",
            help=(
                "Edit one Memory per UTF-8 UID<TAB>content line; "
                "use '-' for stdin"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Local Context or granted view containing the Memory",
        ),
    ] = None,
) -> None:
    if input_source is None:
        if selector is None or content is None:
            typer.secho(
                "Error: provide SELECTOR and CONTENT, or use --input.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
    elif selector is not None or content is not None:
        typer.secho(
            "Error: --input cannot be combined with SELECTOR or CONTENT.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    active_store = MemoryStore()
    current_name = active_store.current_context_name()
    try:
        if input_source is None:
            assert selector is not None
            access, ctx, selector = _resolve_single_target(
                active_store,
                current_name=current_name,
                selector=selector,
                context_name=context_name,
            )
        else:
            access = resolve_context_access(
                active_store,
                context_name,
                current_name=current_name,
                required_permission="UPDATE",
            )
            ctx = access.store.load_direct(access.context_name)
        store = access.store
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        message = error.args[0] if isinstance(error, KeyError) else str(error)
        typer.secho(str(message), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if input_source is not None:
        try:
            edits = parse_edit_lines(read_text_input(input_source))
            changes = ops.edit_many(ctx, edits)
        except (KeyError, TypeError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        if not changes:
            annotate_command_outcome("NO_CHANGE")
            typer.secho(
                f"All {len(edits)} memories are unchanged.",
                fg=typer.colors.YELLOW,
            )
            return

        try:
            with authorized_context_mutation(access):
                store.save(
                    ctx,
                    AutoCheckpoint(
                        command="edit",
                        args={
                            "input": input_source,
                            "mode": "uid-tab-content",
                            "count": len(changes),
                            "uids": [edited.uid for _, edited in changes],
                            "edits": [
                                {"uid": edited.uid, "content": edited.content}
                                for _, edited in changes
                            ],
                            **grant_checkpoint_args(access),
                        },
                        description=(
                            f"Edited {len(changes)} memories from "
                            f"{'stdin' if input_source == '-' else repr(input_source)}"
                        ),
                    ),
                )
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        typer.secho(
            f"Edited {len(changes)} memories in '{ctx.name}':",
            fg=typer.colors.GREEN,
            bold=True,
        )
        for original, edited in changes:
            typer.secho(f"  [{edited.uid[:8]}]", bold=True)
            _render_content("-", original.content, typer.colors.RED)
            _render_content("+", edited.content, typer.colors.GREEN)

        unchanged = len(edits) - len(changes)
        if unchanged:
            typer.secho(
                f"{unchanged} unchanged "
                f"{'memory was' if unchanged == 1 else 'memories were'} skipped.",
                fg=typer.colors.YELLOW,
            )
        return

    assert selector is not None
    assert content is not None
    try:
        original = ops.edit(ctx, selector, content)
    except (KeyError, TypeError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if original.content == content:
        annotate_command_outcome("NO_CHANGE")
        typer.secho(
            f"Memory [{original.uid[:8]}] is unchanged.",
            fg=typer.colors.YELLOW,
        )
        return

    edited = ctx.memories[original.uid]
    assert isinstance(edited, Memory)
    try:
        with authorized_context_mutation(access):
            store.save(
                ctx,
                AutoCheckpoint(
                    command="edit",
                    args={
                        "uid": edited.uid,
                        "content": content,
                        **grant_checkpoint_args(access),
                    },
                    description=f"Edited memory [{edited.uid[:8]}]",
                ),
            )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.secho(
        f"Edited [{edited.uid[:8]}] in '{ctx.name}':",
        fg=typer.colors.GREEN,
        bold=True,
    )
    _render_content("-", original.content, typer.colors.RED)
    _render_content("+", edited.content, typer.colors.GREEN)
