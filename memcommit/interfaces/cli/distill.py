"""Plain command-line projection for a typed Distill proposal."""

from __future__ import annotations

import typer

from memcommit.distill_application import DistillResult
from memcommit.interfaces.console.text import safe_terminal_text


def distill_result_lines(result: DistillResult) -> tuple[str, ...]:
    """Return the complete stable proposal without implying application."""

    if not isinstance(result, DistillResult):
        raise TypeError("Distill rendering requires a typed result.")
    analysis = result.analysis
    lines = [
        f"DISTILL · {safe_terminal_text(analysis.source.context_name)}",
        "STATUS · REVIEW ONLY · SOURCE UNCHANGED · "
        + ("RECURSIVE" if analysis.source.include_descendants else "DIRECT")
        + f" · {result.origin.replace('_', ' ')}",
        "",
        "GOAL · RELEVANCE FOCUS ONLY",
        safe_terminal_text(analysis.goal or "(none)"),
        "",
        "WHAT MEM UNDERSTOOD",
        safe_terminal_text(analysis.overview),
        "",
        f"PROPOSED RULES · {len(analysis.rules)}",
    ]
    for index, rule in enumerate(analysis.rules, 1):
        support = ", ".join(uid[:8] for uid in rule.support_memory_uids)
        boundary = ", ".join(uid[:8] for uid in rule.boundary_memory_uids) or "none"
        lines.extend(
            (
                "",
                f"{index}. [{rule.uid[:8]}] {safe_terminal_text(rule.content)}",
                f"   SUPPORT · {support}",
                f"   BOUNDARY · {boundary}",
                f"   WHY · {safe_terminal_text(rule.rationale)}",
            )
        )
    lines.extend(
        (
            "",
            f"OUTSIDE PROPOSED RULES · {len(analysis.outside_memory_uids)} Memories",
            "No Result Context or checkpoint has been created.",
        )
    )
    return tuple(lines)


def distill_result_text(result: DistillResult) -> str:
    return "\n".join(distill_result_lines(result))


def render_distill_plain(result: DistillResult) -> None:
    typer.echo(distill_result_text(result))


__all__ = [
    "distill_result_lines",
    "distill_result_text",
    "render_distill_plain",
]
