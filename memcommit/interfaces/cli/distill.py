"""Plain command-line projection for a typed Distill proposal."""

from __future__ import annotations

import typer

from memcommit.distill_application import DistillResult
from memcommit.interfaces.console.content_row import render_numbered_content_row
from memcommit.interfaces.console.text import safe_terminal_text


def distill_result_lines(result: DistillResult) -> tuple[str, ...]:
    """Return the complete stable proposal without implying application."""

    if not isinstance(result, DistillResult):
        raise TypeError("Distill rendering requires a typed result.")
    analysis = result.analysis
    lines = [
        f"DISTILL · {safe_terminal_text(analysis.source.context_name)}",
        "STATUS · EVIDENCE-BOUND PROPOSAL · "
        + ("RECURSIVE" if analysis.source.include_descendants else "DIRECT")
        + f" · {result.origin.replace('_', ' ')}",
        "",
        "GOAL · RELEVANCE FOCUS ONLY",
        safe_terminal_text(analysis.goal or "(none)"),
        "",
        "SOURCE OVERVIEW",
        safe_terminal_text(analysis.overview),
        "",
        f"PROPOSED RULES · {len(analysis.rules)}",
    ]
    for index, rule in enumerate(analysis.rules, 1):
        lines.append(
            safe_terminal_text(
                render_numbered_content_row(
                    index,
                    rule.content,
                    suffix=(
                        f"SUPPORT {len(rule.support_memory_uids)} · "
                        f"BOUNDARY {len(rule.boundary_memory_uids)}"
                    ),
                )
            )
        )
    lines.extend(
        (
            "",
            f"OUTSIDE PROPOSED RULES · {len(analysis.outside_memory_uids)} Memories",
            "PROPOSAL · EVIDENCE-BOUND",
        )
    )
    return tuple(lines)


def distill_result_text(result: DistillResult) -> str:
    return "\n".join(distill_result_lines(result))


def render_distill_plain(result: DistillResult) -> None:
    typer.echo(distill_result_text(result))


def render_distill_receipt(result: DistillResult) -> None:
    """Return a bounded proposal result while keeping detail explicitly opt-in."""

    analysis = result.analysis
    overview = " ".join(safe_terminal_text(analysis.overview).split())
    if len(overview) > 280:
        overview = overview[:279].rstrip() + "…"
    typer.echo(
        "\n".join(
            [
                f"DISTILL PROPOSAL · {safe_terminal_text(analysis.source.context_name)}",
                f"UNDERSTOOD · {overview}",
                f"PROPOSED · {len(analysis.rules)} rules",
                f"ATTENTION · {len(analysis.outside_memory_uids)} source Memories outside proposed Rules",
                "DETAILS · rerun with --plain or --tui",
                "SOURCE · UNCHANGED",
            ]
        )
    )


__all__ = [
    "distill_result_lines",
    "distill_result_text",
    "render_distill_plain",
    "render_distill_receipt",
]
