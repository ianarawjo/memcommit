"""Plain projection for typed Makemore proposals."""

from __future__ import annotations

import typer

from memcommit.application.operations.makemore.model import MakemoreMode
from memcommit.application.operations.makemore.application import MakemoreResult
from memcommit.adapters.console.terminal.components.content_row import render_numbered_content_row
from memcommit.adapters.console.terminal.core.text import safe_terminal_text


def makemore_result_lines(result: MakemoreResult) -> tuple[str, ...]:
    if not isinstance(result, MakemoreResult):
        raise TypeError("Makemore rendering requires a typed result.")
    analysis = result.analysis
    direction = (
        "GOAL → RULES"
        if analysis.mode is MakemoreMode.GOAL_TO_RULES
        else "RULES → CASES"
    )
    lines = [
        f"MAKEMORE · {direction}",
        "STATUS · REVIEW ONLY · SUGGESTED · UNVERIFIED · "
        f"{analysis.quality_policy.value.replace('_', ' ')} · "
        f"{result.origin.replace('_', ' ')}",
        "",
        "PROPOSAL OVERVIEW",
        safe_terminal_text(analysis.overview),
    ]
    if analysis.target_context is not None:
        lines.extend(
            (
                "",
                "TARGET AMBIENT · "
                f"{safe_terminal_text(analysis.target_context.context_name)} · "
                f"{len(analysis.target_context.items)} ITEMS",
            )
        )
        for item in analysis.target_context.items:
            if item.kind == "MEMORY":
                lines.append(
                    f"{item.alias} · MEMORY · "
                    f"{safe_terminal_text(item.context_name)} · "
                    f"{safe_terminal_text(item.content or '')}"
                )
            else:
                lines.append(
                    f"{item.alias} · QUERY ONLY · "
                    f"{safe_terminal_text(item.context_name)} · NAME ONLY"
                )
    if analysis.mode is MakemoreMode.GOAL_TO_RULES:
        lines.extend(("", f"PROPOSED RULES · {len(analysis.rules)}"))
        for index, rule in enumerate(analysis.rules, 1):
            lines.append(
                safe_terminal_text(
                    render_numbered_content_row(
                        index,
                        rule.content,
                        suffix="SUGGESTED · UNVERIFIED",
                    )
                )
            )
            if analysis.target_context is not None:
                lines.append(
                    "   TARGET USED · "
                    + (", ".join(rule.target_context_refs) or "NONE")
                )
    else:
        lines.extend(("", f"PROPOSED CASES · {len(analysis.cases)}"))
        for index, case in enumerate(analysis.cases, 1):
            lines.extend(
                (
                    "",
                    f"{index}. [{case.case_role}] [Suggested] [Unverified] "
                    f"{safe_terminal_text(case.proposition)}",
                    f"   RULE COVERAGE · ALL {len(case.rule_checks)}",
                    *(
                        "   RULE "
                        f"{check.source_rule_index} · {safe_terminal_text(check.evidence)}"
                        for check in case.rule_checks
                    ),
                    *(
                        (
                            "   SOURCE FIT · YES",
                            "   RULE CONFORMANCE · ALL "
                            f"{len(case.validation.conforming_source_rule_indexes)}",
                        )
                        if case.validation is not None
                        else ()
                    ),
                    f"   EXPECTED · {safe_terminal_text(case.expected or '(open)')}",
                    f"   WHY · {safe_terminal_text(case.rationale)}",
                    *(
                        (
                            "   TARGET USED · "
                            + (", ".join(case.target_context_refs) or "NONE"),
                        )
                        if analysis.target_context is not None
                        else ()
                    ),
                )
            )
    lines.extend(("", "PROPOSALS · SUGGESTED · UNVERIFIED"))
    return tuple(lines)


def makemore_result_text(result: MakemoreResult) -> str:
    return "\n".join(makemore_result_lines(result))


def render_makemore_plain(result: MakemoreResult) -> None:
    typer.echo(makemore_result_text(result))


__all__ = [
    "makemore_result_lines",
    "makemore_result_text",
    "render_makemore_plain",
]
