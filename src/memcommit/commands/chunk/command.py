from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.application.authority.access import (
    resolve_context_access,
)
from memcommit.application.operations.chunk.application import chunk
from memcommit.application.operations.chunk.domain import ChunkMethod, chunk_content
from memcommit.application.operations.chunk.runtime import apply_chunk_proposals
from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.context import Memory
from memcommit.core.context_targeting.loading import (
    resolve_local_context_memory_target,
    resolve_local_direct_memory_locator,
)
from memcommit.core.context_targeting.memory_focus import is_memory_uid_prefix
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectMemoryLocator,
    DirectMemoryTarget,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


def _preview_chunk(chunk_number: int, chunk_memory: Memory) -> None:
    lines = chunk_memory.content.splitlines() or [""]
    typer.secho(f"  {chunk_number:>2}  {lines[0][:60]}", fg=typer.colors.CYAN)
    for body_line in lines[1:6]:
        typer.secho(f"       {body_line[:60]}", dim=True)
    if len(lines) > 6:
        typer.secho("       …", dim=True)


def _chunk_settings(
    method: ChunkMethod,
    *,
    break_on: str | None,
    min_chars: int | None,
    max_chars: int | None,
) -> str:
    settings = [f"method={method.value}"]
    if break_on is not None:
        settings.append(f"break_on={break_on!r}")
    if min_chars is not None:
        settings.append(f"min_chars={min_chars}")
    if max_chars is not None:
        settings.append(f"max_chars={max_chars}")
    return ", ".join(settings)


def cmd(
    memory_selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Auto-typed existing Context, Memory UID/prefix, or "
                "CONTEXT:UID; omit to chunk the current Context"
            ),
        ),
    ] = None,
    method: Annotated[
        ChunkMethod,
        typer.Option(
            "--method",
            "-m",
            help=(
                "Chunking strategy: markdown_headers | paragraphs | sentences "
                "| clauses"
            ),
            show_default=True,
        ),
    ] = ChunkMethod.sentences,
    break_on: Annotated[
        Optional[str],
        typer.Option(
            "--break-on",
            metavar="PUNCTUATION",
            help=(
                "Also split after each literal punctuation or symbol character "
                "in this string"
            ),
        ),
    ] = None,
    min_chars: Annotated[
        Optional[int],
        typer.Option(
            "--min-chars",
            min=1,
            metavar="COUNT",
            help=(
                "Prefer chunks at least this many Unicode code points; a chunk "
                "may be shorter when it cannot merge within --max-chars"
            ),
        ),
    ] = None,
    max_chars: Annotated[
        Optional[int],
        typer.Option(
            "--max-chars",
            min=1,
            metavar="COUNT",
            help="Hard maximum Unicode-code-point count for every chunk",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            metavar="CONTEXT",
            help="Local Context or granted view containing the direct Memory or Memories",
        ),
    ] = None,
) -> None:
    active_store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(active_store)
    try:
        parsed_operand = (
            parse_auto_typed_context_memory_operand(
                memory_selector,
                explicit_memory_context=context_name,
            )
            if memory_selector is not None
            else None
        )
        if isinstance(parsed_operand, DirectMemoryLocator):
            if parsed_operand.context_locator is None:
                if (
                    snapshot.current_name is not None
                    and not active_store.context_exists(snapshot.current_name)
                ):
                    # A virtual current pointer is already an explicit public
                    # Grant selection. Preserve that authority-bearing owner;
                    # the ordinary-local global catalog cannot enumerate it.
                    context_name = snapshot.current_name
                    memory_selector = parsed_operand.memory_selector
                else:
                    target = resolve_local_direct_memory_locator(
                        active_store,
                        parsed_operand.memory_selector,
                        current=snapshot.current_name,
                    )
                    context_name = target.context_name
                    memory_selector = target.memory_uid
            else:
                context_name = parsed_operand.context_locator
                memory_selector = parsed_operand.memory_selector
        elif parsed_operand is not None:
            exact_access = None
            if is_memory_uid_prefix(memory_selector):
                try:
                    exact_access = resolve_context_access(
                        active_store,
                        parsed_operand.locator,
                        current_name=snapshot.current_name,
                        required_permission="DELETE",
                    )
                except FileNotFoundError:
                    pass
            if exact_access is not None:
                auto_target = ContextTarget(exact_access.display_name)
            else:
                try:
                    auto_target = resolve_local_context_memory_target(
                        active_store,
                        memory_selector,
                        current=snapshot.current_name,
                    )
                except FileNotFoundError:
                    auto_target = None
            if auto_target is not None:
                if isinstance(auto_target, DirectMemoryTarget):
                    context_name = auto_target.context_name
                    memory_selector = auto_target.memory_uid
                else:
                    assert isinstance(auto_target, ContextTarget)
                    context_name = auto_target.context_name
                    memory_selector = None
            elif (
                snapshot.current_name is not None
                and not active_store.context_exists(snapshot.current_name)
                and is_memory_uid_prefix(memory_selector)
            ):
                # A selected granted Context is an explicit owner even though
                # bare prefixes never enumerate arbitrary Grants.
                context_name = snapshot.current_name
            else:
                context_name = parsed_operand.locator
                memory_selector = None
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=snapshot.current_name,
            required_permission="DELETE",
        )
        store = access.store
        ctx = store.load_direct(access.context_name)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    settings = _chunk_settings(
        method,
        break_on=break_on,
        min_chars=min_chars,
        max_chars=max_chars,
    )
    try:
        # Validate optional boundaries even when the selected Context contains
        # no direct Memories and would otherwise skip every per-Memory call.
        chunk_content(
            "",
            method,
            break_on=break_on,
            min_chars=min_chars,
            max_chars=max_chars,
        )
        if memory_selector is not None:
            original, chunks = chunk(
                ctx,
                memory_selector,
                method,
                break_on=break_on,
                min_chars=min_chars,
                max_chars=max_chars,
            )
            proposals = [(original, chunks)] if len(chunks) > 1 else []
        else:
            # Context scope is deliberately direct-only. Embedded and referenced
            # content has a different owner and must not be mutated as a side
            # effect of mechanically refining this Context.
            proposals = []
            for item in ctx.iter_items():
                if not isinstance(item, Memory):
                    continue
                original, chunks = chunk(
                    ctx,
                    item.uid,
                    method,
                    break_on=break_on,
                    min_chars=min_chars,
                    max_chars=max_chars,
                )
                if len(chunks) > 1:
                    proposals.append((original, chunks))
    except (KeyError, TypeError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if not proposals:
        annotate_command_outcome("NO_CHANGE")
        if memory_selector is not None:
            typer.secho(
                f"Memory [{original.uid[:8]}] produced only {len(chunks)} chunk(s) "
                f"with {settings} — no changes made.",
                fg=typer.colors.YELLOW,
            )
        else:
            display_name = display_escape_text(access.display_name)
            typer.secho(
                f"Context '{display_name}' has no direct Memories that produce "
                f"multiple chunks with {settings} — no changes made.",
                fg=typer.colors.YELLOW,
            )
        raise typer.Exit(0)

    source_count = len(proposals)
    chunk_count = sum(len(chunks) for _original, chunks in proposals)
    typer.echo()
    if memory_selector is not None:
        original, chunks = proposals[0]
        display_name = display_escape_text(access.display_name)
        typer.secho(
            f"Proposed split of [{original.uid[:8]}] in Context "
            f"'{display_name}' → {len(chunks)} chunks ({settings})",
            bold=True,
        )
    else:
        display_name = display_escape_text(access.display_name)
        typer.secho(
            f"Proposed split in Context '{display_name}' → {source_count} direct "
            f"Memories / {chunk_count} chunks ({settings})",
            bold=True,
        )
    typer.echo("─" * 56)

    if min_chars is not None:
        below_minimum = sum(
            len(chunk_memory.content) < min_chars
            for _original, chunks in proposals
            for chunk_memory in chunks
        )
        if below_minimum:
            typer.secho(
                f"Note — {below_minimum} chunk(s) remain below "
                f"min_chars={min_chars}; merging them would exceed the hard "
                "maximum or no neighboring chunk exists.",
                fg=typer.colors.YELLOW,
            )
    for proposal_number, (original, chunks) in enumerate(proposals, 1):
        if memory_selector is None:
            if proposal_number > 1:
                typer.echo()
            typer.secho(
                f"Memory [{original.uid[:8]}] → {len(chunks)} chunks",
                bold=True,
            )
        for chunk_number, chunk_memory in enumerate(chunks, 1):
            _preview_chunk(chunk_number, chunk_memory)
    typer.echo("─" * 56)

    # Chunk is one checkpointed, Undoable command, so invoking it is the
    # approval boundary; only history-destroying deletion keeps a second prompt.
    try:
        apply_chunk_proposals(
            access=access,
            context=ctx,
            proposals=proposals,
            method=method,
            settings=settings,
            memory_selector=memory_selector,
            break_on=break_on,
            min_chars=min_chars,
            max_chars=max_chars,
        )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if memory_selector is not None:
        # Retain the established single-Memory receipt for script compatibility.
        display_name = display_escape_text(access.display_name)
        typer.secho(
            f"Done — {chunk_count} memories added in '{display_name}'.",
            fg=typer.colors.GREEN,
        )
    else:
        display_name = display_escape_text(access.display_name)
        typer.secho(
            f"Done — {source_count} Memory(s) replaced with {chunk_count} chunks "
            f"in '{display_name}'.",
            fg=typer.colors.GREEN,
        )
