"""Shared evidence-to-outcome detail grammar for semantic workbenches."""

from __future__ import annotations

from memcommit.commands.tui_primitives import safe_terminal_text
from memcommit.resolution_workbench import ResolutionMemoryRow
from memcommit.result_workbench import ResultRef


def semantic_ref_text(reference: ResultRef) -> str:
    return (
        f"{safe_terminal_text(reference.kind)}:"
        f"{safe_terminal_text(reference.key)}"
    )


def semantic_refs_text(refs: tuple[ResultRef, ...]) -> str:
    return ", ".join(semantic_ref_text(reference) for reference in refs)


def semantic_detail_header_fragments(
    *,
    label: str,
    title: str,
    why_heading: str,
    why: str,
) -> list[tuple[str, str]]:
    """Render the common report-style identity and review rationale."""

    return [
        ("class:section", f"\n {safe_terminal_text(label)}\n"),
        ("class:case-title", f" {safe_terminal_text(title)}\n"),
        ("class:detail-heading", f"\n {safe_terminal_text(why_heading)}\n"),
        ("", f" {safe_terminal_text(why)}\n"),
        ("class:detail-heading", "\n OPERATION DETAIL\n"),
    ]


def semantic_detail_block_fragments(
    *,
    heading: str,
    text: str,
    refs: tuple[ResultRef, ...] = (),
    memory_rows: tuple[ResolutionMemoryRow, ...] = (),
) -> list[tuple[str, str]]:
    """Render one operation-authored block without reordering its meaning."""

    fragments = [("class:block-heading", f" {safe_terminal_text(heading)}\n")]
    if text:
        fragments.append(("", f" {safe_terminal_text(text)}\n"))
    for row in memory_rows:
        fragments.append(
            (
                "class:memory-object",
                f" [{row.ordinal}] {safe_terminal_text(row.content)}\n",
            )
        )
        if row.evidence:
            fragments.append(
                (
                    "",
                    "     Evidence · "
                    + " | ".join(safe_terminal_text(span) for span in row.evidence)
                    + "\n",
                )
            )
    if refs:
        fragments.append(
            ("class:reference", f" refs · {semantic_refs_text(refs)}\n")
        )
    return fragments


def semantic_memory_row_fragments(
    row: ResolutionMemoryRow,
    *,
    expanded: bool,
) -> list[tuple[str, str]]:
    """Render one Memory on one row and disclose evidence only on demand."""

    fragments: list[tuple[str, str]] = [
        (
            "class:memory-object",
            f" [{row.ordinal}] {safe_terminal_text(row.content)}\n",
        )
    ]
    if expanded and row.evidence:
        fragments.append(
            (
                "",
                "     Evidence · "
                + " | ".join(safe_terminal_text(span) for span in row.evidence)
                + "\n",
            )
        )
    return fragments


def semantic_trace_fragments(
    *,
    evidence_refs: tuple[ResultRef, ...],
    judgment_refs: tuple[ResultRef, ...],
    outcome_refs: tuple[ResultRef, ...] = (),
    unresolved_refs: tuple[ResultRef, ...] = (),
) -> list[tuple[str, str]]:
    """Render the canonical evidence-to-judgment terminal trace."""

    fragments: list[tuple[str, str]] = [
        ("class:detail-heading", "\n TRACE\n"),
        (
            "class:trace",
            f" EVIDENCE   · {semantic_refs_text(evidence_refs)}\n",
        ),
        (
            "class:trace",
            f" → JUDGMENT · {semantic_refs_text(judgment_refs)}\n",
        ),
    ]
    if outcome_refs:
        fragments.append(
            (
                "class:trace",
                f" → OUTCOME  · {semantic_refs_text(outcome_refs)}\n",
            )
        )
    if unresolved_refs:
        fragments.append(
            (
                "class:trace",
                f" → UNRESOLVED · {semantic_refs_text(unresolved_refs)}\n",
            )
        )
    return fragments
