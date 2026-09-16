"""Static Search receipts: ranked results, references, and completed saves."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar
import shlex

import typer

from memcommit.application.operations.search.application import SearchResponse
from memcommit.application.operations.search.ranking import SearchMatch
from memcommit.application.capabilities.retrieval_corpus.candidates import (
    RetrievalArtifact,
)
from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextFromSelectionResult,
)
from memcommit.core.context import Memory, MemoryRef, QueryContextRef
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceState,
)
from memcommit.source_projection.presentation import (
    source_annotation_text,
    source_object_label,
)

from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
    display_escape_text,
)


T = TypeVar("T")


@dataclass(frozen=True)
class SearchResultViewRow:
    context_name: str
    label: str
    content: str


@dataclass(frozen=True)
class SearchResultGroup:
    context_name: str
    rows: tuple[SearchResultViewRow, ...]


def group_search_items(
    items: Sequence[T],
    *,
    context_name: Callable[[T], str],
) -> tuple[tuple[str, tuple[T, ...]], ...]:
    """Group in first-owner order while preserving ranking inside each owner."""

    grouped: dict[str, list[T]] = {}
    for item in items:
        grouped.setdefault(context_name(item), []).append(item)
    return tuple((name, tuple(values)) for name, values in grouped.items())


def group_search_result_rows(
    rows: Sequence[SearchResultViewRow],
) -> tuple[SearchResultGroup, ...]:
    return tuple(
        SearchResultGroup(name, values)
        for name, values in group_search_items(
            rows,
            context_name=lambda row: row.context_name,
        )
    )


def render_grouped_search_results(
    rows: Sequence[SearchResultViewRow],
    *,
    related_query: str = "",
    empty_message: str = "(no matching items)",
) -> str:
    """Render one common primary/related header and Context-grouped result body."""

    if not rows:
        return f"SEARCH RESULTS\n  {safe_terminal_text(empty_message)}"
    lines: list[str] = []
    if related_query:
        lines.extend(
            [
                "PRIMARY MATCHES",
                "  (none)",
                "",
                "RELATED RESULTS",
                "  Broader search: " + safe_terminal_text(related_query),
                "  Related items do not satisfy the original query.",
                "",
            ]
        )
    else:
        lines.append("SEARCH RESULTS")
    for group_index, group in enumerate(group_search_result_rows(rows)):
        if group_index:
            lines.append("")
        lines.append(safe_terminal_text(group.context_name))
        for row in group.rows:
            label = safe_terminal_text(row.label)
            content_lines = safe_terminal_text(row.content).splitlines() or [""]
            lines.append(f"  {label} {content_lines[0]}")
            indent = " " * (len(label) + 3)
            lines.extend(f"{indent}{line}" for line in content_lines[1:])
    return "\n".join(lines)


def _render_labeled_content(label: str, content: str) -> None:
    """Render the first content line beside its item and align continuations."""
    lines = safe_terminal_text(content).splitlines() or [""]
    typer.echo(f"{label} {lines[0]}")
    continuation = " " * (len(label) + 1)
    for line in lines[1:]:
        typer.echo(f"{continuation}{line}")


def _render_match(match: SearchMatch) -> None:
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        item_label = source_object_label(SourceForm.MEMORY)
        relevance = " · RELATED" if match.relevance == "related" else ""
        _render_labeled_content(
            f"[{item_label} {item.uid[:8]}]{relevance}",
            item.content,
        )
    elif isinstance(item, MemoryRef):
        facts = SourceDisplayFacts(
            form=SourceForm.MEMORY_REF,
            states=(
                (SourceState.READ_ONLY,)
                if item.target is not None
                else (SourceState.DANGLING,)
            ),
        )
        item_label = source_object_label(facts)
        annotations = [
            *(("RELATED",) if match.relevance == "related" else ()),
            source_annotation_text(facts),
        ]
        annotation = " · ".join(value for value in annotations if value)
        label = (
            f"[{item_label} {item.uid[:8]}]"
            + (f" · {annotation}" if annotation else "")
            + " "
            + f"-> {display_escape_text(item.target_context_name)}#"
            f"{display_escape_text(item.target_memory_uid[:8])}"
        )
        if item.target is not None:
            _render_labeled_content(label, item.target.content)
        else:
            typer.echo(label)
    elif isinstance(item, QueryContextRef):
        item_label = source_object_label(SourceForm.QUERY_VIEW)
        relevance = " · RELATED" if match.relevance == "related" else ""
        label = f"[{item_label} {item.uid[:8]}]{relevance}"
        typer.echo(f"{label} {display_escape_text(item.name)}")
        command = shlex.join(
            [
                "mem",
                "query",
                item.name,
                "<question>",
                "--context",
                candidate.context_name,
            ]
        )
        typer.echo(f"{' ' * (len(label) + 1)}Ask with: {display_escape_text(command)}")
    elif isinstance(item, RetrievalArtifact):
        label = (
            f"[related {item.artifact_kind} {item.uid[:8]}]"
            if match.relevance == "related"
            else f"[{item.artifact_kind} {item.uid[:8]}]"
        )
        summary = item.summary.strip() or item.title
        _render_labeled_content(label, f"{item.title} · {summary}")


def render_search_receipt(
    response: SearchResponse,
    *,
    target_names: tuple[str, ...],
    all_readable_contexts: bool = False,
) -> None:
    """Present one typed application result without rerunning its search."""

    heading = (
        "ALL READABLE CONTEXTS"
        if all_readable_contexts
        else " + ".join(display_escape_text(name) for name in target_names)
    )
    if not response.results:
        typer.secho(heading, bold=True)
        typer.echo("  (no matching items)")
        return
    if response.related_query:
        if len(target_names) == 1:
            typer.secho(heading, bold=True)
            typer.echo("  (no primary matches)")
            typer.echo()
        typer.secho("RELATED RESULTS", bold=True)
        typer.echo(
            "  No matching results for: " + display_escape_text(response.request.query)
        )
        typer.echo("  Broader search: " + display_escape_text(response.related_query))
        typer.echo()
    groups = group_search_items(
        response.results,
        context_name=lambda result: result.context_name,
    )
    for group_index, (owner_name, results) in enumerate(groups):
        if group_index or response.related_query:
            typer.echo()
        typer.secho(display_escape_text(owner_name), bold=True)
        for result in results:
            if result.current_match is not None:
                _render_match(result.current_match)
                continue
            related = " · RELATED" if result.relevance == "related" else ""
            _render_labeled_content(
                f"[{result.kind} {result.uid[:8]}]{related}",
                result.content,
            )
    if response.related_query:
        typer.echo()
        typer.echo("Related results may not satisfy the original query.")


def render_save_receipt(saved: SaveContextFromSelectionResult) -> None:
    """Report the existing save capability's committed result."""

    typer.secho(
        f"Saved {len(saved.item_uids)} checked Search result(s) as "
        f"{saved.mode} in new Context "
        f"'{display_escape_text(saved.context_name)}' "
        f"[{saved.context_uid[:8]}]; sources unchanged.",
        fg=typer.colors.GREEN,
    )
