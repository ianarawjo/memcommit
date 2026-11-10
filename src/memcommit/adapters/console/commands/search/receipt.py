"""Static Find receipts in global rank order using shared Source References."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.application.capabilities.retrieval_corpus.candidates import (
    RetrievalArtifact,
)
from memcommit.application.operations.search.application import (
    SearchResponse,
    SearchResult,
)
from memcommit.source_projection.model import SourceReferenceRow
from memcommit.source_projection.presentation import render_source_reference_row


def _render_search_result(rank: int, result: SearchResult) -> None:
    content = result.content
    alias = None
    match = result.current_match
    if result.kind == "memory" and match is not None:
        memory_position_in_context = match.candidate.memory_position_in_context
        if memory_position_in_context is not None:
            alias = f"Memory {memory_position_in_context}"
    elif match is not None and isinstance(match.candidate.item, RetrievalArtifact):
        artifact = match.candidate.item
        content = f"{artifact.title} · {artifact.summary.strip() or artifact.title}"
        alias = artifact.artifact_kind
    elif result.kind == "artifact":
        alias = result.kind
    row = SourceReferenceRow(
        number=rank,
        content=content,
        uid=display_escape_text(result.uid),
        context_name=display_escape_text(result.context_name),
        alias=display_escape_text(alias) if alias is not None else None,
    )
    typer.echo(safe_terminal_text(render_source_reference_row(row)))


def render_search_receipt(response: SearchResponse) -> None:
    """Show the selected count and actual request limit without regrouping ranks."""

    count = len(response.results)
    noun = "result" if count == 1 else "results"
    typer.secho(
        f"FIND (entire Profile, by relevance, up to {response.request.limit}) · {count} {noun}",
        bold=True,
    )
    if not response.results:
        typer.echo("  (no matching items)")
        return
    if response.related_query:
        typer.secho("RELATED RESULTS", bold=True)
        typer.echo(
            "  No matching results for: " + display_escape_text(response.request.query)
        )
        typer.echo("  Broader search: " + display_escape_text(response.related_query))
        typer.echo()
    # Context grouping would reorder interleaved ranks and imply per-Context results.
    for rank, result in enumerate(response.results, 1):
        _render_search_result(rank, result)
    if response.related_query:
        typer.echo()
        typer.echo("Related results may not satisfy the original query.")
