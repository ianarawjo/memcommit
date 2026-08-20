from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.authority.access import (
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.chunking import ChunkMethod, chunk_content
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.context import AutoCheckpoint, Memory
from memcommit.interfaces.console.text import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


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
                "UID (or unambiguous prefix) of one direct Memory; omit to "
                "chunk every splittable direct Memory in the target Context"
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
            original, chunks = ops.chunk(
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
                original, chunks = ops.chunk(
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

    decision = typer.prompt(
        "Apply? [y/n]", default="", show_default=False
    ).strip().lower()
    if decision not in ("y", "yes"):
        typer.echo("Aborted — no changes made.")
        raise typer.Exit(0)

    split_records: list[dict[str, object]] = []
    for original, chunks in proposals:
        original_position = ctx.ordered_uids().index(original.uid)
        ctx.remove(original.uid)
        for offset, chunk_memory in enumerate(chunks):
            ctx.add(chunk_memory, position=original_position + offset)
        split_records.append(
            {
                "uid": original.uid,
                "chunk_uids": [chunk_memory.uid for chunk_memory in chunks],
            }
        )

    checkpoint_args: dict[str, object] = {
        "context": access.context_name,
        "method": method.value,
        **grant_checkpoint_args(access),
    }
    if break_on is not None:
        checkpoint_args["break_on"] = break_on
    if min_chars is not None:
        checkpoint_args["min_chars"] = min_chars
    if max_chars is not None:
        checkpoint_args["max_chars"] = max_chars
    if memory_selector is not None:
        checkpoint_args["uid"] = proposals[0][0].uid
    else:
        # Exact parent/child identities let Trace reconstruct every split in a
        # batch without guessing from repeated chunk contents.
        checkpoint_args["splits"] = split_records

    try:
        with authorized_context_mutation(
            access,
            required_permissions=("CREATE", "DELETE"),
        ):
            store.save(
                ctx,
                AutoCheckpoint(
                    command="chunk",
                    args=checkpoint_args,
                    description=(
                        f"Chunked {source_count} Memory(s) into {chunk_count} "
                        f"Memories ({settings})"
                    ),
                ),
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
